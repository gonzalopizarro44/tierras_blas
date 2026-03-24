"""
==============================================================================
SERVICIO DE VENTAS - Sales Service
==============================================================================

Centraliza TODA la lógica de negocio del módulo ventas_web:
- Filtros avanzados
- Creación de clientes
- Creación de órdenes
- Confirmación y cancelación

Este modelo es ABSTRACTO y no genera tablas en BD.
Se instancia desde los controllers para acceder a los métodos de negocio.

Uso:
    sales_service = self.env['sales.service']
    domain = sales_service.build_sale_filters(kwargs)
    cliente = sales_service.create_quick_customer(nombre, dni)
    orden = sales_service.create_sale_order(cliente_id, lineas, origen)

==============================================================================
"""

from odoo import models, api
from datetime import datetime, timedelta


class SalesService(models.AbstractModel):
    """Servicio centralizado de lógica de negocio para ventas_web"""
    
    _name = 'sales.service'
    _description = 'Servicio de Ventas Web'

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 1: FILTROS AVANZADOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def build_sale_filters(self, kwargs):
        """
        Construye un domain (filtro ORM) basado en parámetros GET.
        
        Soporta:
        - cliente: búsqueda por nombre en partner_id (ilike)
        - producto: búsqueda en order_line.product_id (ilike)
        - fecha_desde / fecha_hasta: rango de date_order
        - monto_min / monto_max: rango de amount_total
        - categoria: product_id.categ_id (ID exacto)
        - estado: state ('confirmada' → 'sale', 'cancelada' → 'cancel')
        - origen: sales_origin (exacto)
        
        Args:
            kwargs (dict): Parámetros GET del request
        
        Returns:
            list: Domain Odoo para search()
        """
        domain = []

        # ── Filtro: Cliente (name, DNI) ──
        cliente = kwargs.get('cliente', '').strip()
        if cliente:
            domain.append(('partner_id.name', 'ilike', cliente))

        # ── Filtro: Producto (order_line.product_id) ──
        producto = kwargs.get('producto', '').strip()
        if producto:
            domain.append(('order_line.product_id.name', 'ilike', producto))

        # ── Filtro: Rango de fechas (fecha_desde) ──
        fecha_desde = kwargs.get('fecha_desde', '').strip()
        if fecha_desde:
            try:
                dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
                domain.append(('date_order', '>=', dt))
            except ValueError:
                pass  # Ignorar formato inválido

        # ── Filtro: Rango de fechas (fecha_hasta) ──
        fecha_hasta = kwargs.get('fecha_hasta', '').strip()
        if fecha_hasta:
            try:
                dt = datetime.strptime(fecha_hasta, '%Y-%m-%d')
                # Incluir todo el día: sumar 1 día
                dt_fin = dt + timedelta(days=1)
                domain.append(('date_order', '<', dt_fin))
            except ValueError:
                pass

        # ── Filtro: Monto total (monto_min) ──
        monto_min = kwargs.get('monto_min', '').strip()
        if monto_min:
            try:
                domain.append(('amount_total', '>=', float(monto_min)))
            except (ValueError, TypeError):
                pass

        # ── Filtro: Monto total (monto_max) ──
        monto_max = kwargs.get('monto_max', '').strip()
        if monto_max:
            try:
                domain.append(('amount_total', '<=', float(monto_max)))
            except (ValueError, TypeError):
                pass

        # ── Filtro: Categoría de producto ──
        categoria = kwargs.get('categoria', '').strip()
        if categoria:
            try:
                domain.append(('order_line.product_id.categ_id', '=', int(categoria)))
            except (ValueError, TypeError):
                pass

        # ── Filtro: Estado (confirmada / cancelada) ──
        estado = kwargs.get('estado', '').strip()
        if estado == 'confirmada':
            domain.append(('state', '=', 'sale'))
        elif estado == 'cancelada':
            domain.append(('state', '=', 'cancel'))

        # ── Filtro: Origen de venta ──
        origen = kwargs.get('origen', '').strip()
        if origen:
            domain.append(('sales_origin', '=', origen))

        return domain

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 2: GESTIÓN DE CLIENTES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def create_quick_customer(self, nombre, dni=None):
        """
        Crea un cliente rápidamente o retorna uno existente.
        
        Verifica:
        - Si ya existe un cliente con el mismo nombre
        - Si no existe, lo crea
        
        Args:
            nombre (str): Nombre completo del cliente (obligatorio)
            dni (str): DNI o documento (opcional, se guarda en 'vat')
        
        Returns:
            dict: {
                'success': bool,
                'id': int,
                'nombre': str,
                'es_nuevo': bool,
                'message': str
            }
        """
        # ── Validación de datos ──
        nombre = (nombre or '').strip()
        if not nombre:
            return {
                'success': False,
                'message': 'El nombre del cliente es obligatorio.',
            }

        try:
            ResPartner = self.env['res.partner']
            
            # ── Buscar cliente existente ──
            cliente_existente = ResPartner.sudo().search(
                [('name', '=', nombre), ('customer_rank', '>', 0)],
                limit=1
            )
            
            if cliente_existente:
                return {
                    'success': True,
                    'id': cliente_existente.id,
                    'nombre': cliente_existente.name,
                    'es_nuevo': False,
                    'message': 'Cliente ya existe.',
                }

            # ── Crear nuevo cliente ──
            cliente_nuevo = ResPartner.sudo().create({
                'name': nombre,
                'vat': dni or '',
                'customer_rank': 1,  # Marcar como cliente
                'type': 'invoice',  # Dirección de facturación
            })

            return {
                'success': True,
                'id': cliente_nuevo.id,
                'nombre': cliente_nuevo.name,
                'es_nuevo': True,
                'message': 'Cliente creado exitosamente.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear cliente: {str(e)}',
            }

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 3: GESTIÓN DE ÓRDENES DE VENTA
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def create_sale_order(self, cliente_id, lineas, origen='admin', journal_id=None):
        """
        Crea una nueva orden de venta con líneas de productos.
        
        FLUJO:
        1. Valida cliente
        2. Valida líneas
        3. Crea sale.order en DRAFT
        4. Crea sale.order.line para cada producto
        5. Confirma automáticamente → action_confirm()
        6. El stock se descuenta automáticamente
        
        Args:
            cliente_id (int): ID del cliente (res.partner)
            lineas (list): [{'product_id': int, 'quantity': float}, ...]
            origen (str): 'admin', 'cliente_web', 'integracion', etc.
            journal_id (int): ID del journal de pago (opcional)
        
        Returns:
            dict: {
                'success': bool,
                'order_id': int,
                'order_name': str,
                'message': str,
                'url': str
            }
        """
        try:
            # ── Validar cliente ──
            cliente = self.env['res.partner'].sudo().browse(int(cliente_id))
            if not cliente.exists():
                return {
                    'success': False,
                    'message': 'Cliente no encontrado.',
                }

            # ── Validar líneas ──
            if not lineas or not isinstance(lineas, list):
                return {
                    'success': False,
                    'message': 'Debe agregar al menos un producto.',
                }

            # ── Crear orden (DRAFT) ──
            order_vals = {
                'partner_id': cliente.id,
                'sales_origin': origen,
                'state': 'draft',
                'date_order': datetime.now(),
            }

            # Si se proporciona journal_id, asignarlo
            if journal_id:
                try:
                    order_vals['journal_id'] = int(journal_id)
                except (ValueError, TypeError):
                    pass

            orden = self.env['sale.order'].sudo().create(order_vals)

            # ── Crear líneas de orden ──
            self._create_sale_order_lines(orden, lineas)

            # ── CONFIRMACIÓN AUTOMÁTICA ──
            # Llamamos a action_confirm() que dispara:
            # - Validación de cantidades y stock
            # - Generación de movimientos de stock
            # - Cambio de estado a 'sale'
            self._confirm_order_with_error_handling(orden)

            return {
                'success': True,
                'order_id': orden.id,
                'order_name': orden.name,
                'message': f'Orden {orden.name} creada y confirmada exitosamente.',
                'url': '/ventas',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear la venta: {str(e)}',
            }

    @api.model
    def _create_sale_order_lines(self, orden, lineas):
        """
        Crea las líneas de orden de venta.
        
        Ignora líneas mal formadas sin causar fallo general.
        
        Args:
            orden (sale.order): Orden ya creada
            lineas (list): [{'product_id': int, 'quantity': float}, ...]
        """
        for linea_data in lineas:
            try:
                product_id = int(linea_data.get('product_id', 0))
                cantidad = float(linea_data.get('quantity', 1))

                # Validaciones
                if product_id <= 0 or cantidad <= 0:
                    continue

                producto = self.env['product.product'].sudo().browse(product_id)
                if not producto.exists():
                    continue

                # Crear línea con list_price como tarifa por defecto
                self.env['sale.order.line'].sudo().create({
                    'order_id': orden.id,
                    'product_id': producto.id,
                    'product_uom_qty': cantidad,
                    'price_unit': producto.list_price,
                })

            except (ValueError, TypeError, Exception):
                # Ignorar líneas mal formadas; continuar con las siguientes
                continue

    @api.model
    def _confirm_order_with_error_handling(self, orden):
        """
        Confirma una orden llamando a action_confirm().
        
        Si falla, registra el error pero NO cancela la creación de la orden.
        
        Args:
            orden (sale.order): Orden a confirmar
        """
        try:
            orden.action_confirm()
        except Exception as e:
            # Log pero no propagate; la orden existe aunque no se haya confirmado
            print(f"[VENTAS_WEB] Error al confirmar orden {orden.name}: {str(e)}")

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 4: CONFIRMACIÓN DE ÓRDENES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def confirm_sale_order(self, order_id):
        """
        Confirma una orden de venta existente (DRAFT → SALE).
        
        Verifica:
        - Orden existe
        - Orden está en estado DRAFT (no puede confirmar si ya está confirmada)
        
        Luego:
        - Llama a action_confirm() que genera movimientos de stock
        
        Args:
            order_id (int): ID de la sale.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        try:
            orden = self.env['sale.order'].sudo().browse(int(order_id))

            # ── Validar existencia ──
            if not orden.exists():
                return {
                    'success': False,
                    'message': 'Orden no encontrada.',
                }

            # ── Validar estado ──
            if orden.state != 'draft':
                return {
                    'success': False,
                    'message': f'Solo se pueden confirmar órdenes en DRAFT. Estado actual: {orden.state}',
                }

            # ── Confirmar ──
            orden.action_confirm()

            return {
                'success': True,
                'message': f'Orden {orden.name} confirmada. Stock descontado.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al confirmar: {str(e)}',
            }

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 5: CANCELACIÓN DE ÓRDENES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def cancel_sale_order(self, order_id):
        """
        Cancela una orden de venta.
        
        Si la orden estaba confirmada:
        - Revierte los movimientos de stock
        
        Verifica:
        - Orden existe
        - Orden no está ya cancelada
        
        Args:
            order_id (int): ID de la sale.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        try:
            orden = self.env['sale.order'].sudo().browse(int(order_id))

            # ── Validar existencia ──
            if not orden.exists():
                return {
                    'success': False,
                    'message': 'Orden no encontrada.',
                }

            # ── Validar que no esté ya cancelada ──
            if orden.state == 'cancel':
                return {
                    'success': False,
                    'message': 'Esta orden ya está cancelada.',
                }

            # ── Cancelar ──
            orden.action_cancel()

            return {
                'success': True,
                'message': f'Orden {orden.name} cancelada.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al cancelar: {str(e)}',
            }
