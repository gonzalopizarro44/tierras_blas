"""
==============================================================================
SERVICIO DE COMPRAS - Compras Service
==============================================================================

Centraliza TODA la lógica de negocio del módulo compras_web:
- Filtros avanzados
- Creación de proveedores
- Creación de órdenes de compra
- Confirmación de órdenes (con incremento de stock)
- Cancelación de órdenes

Este modelo es ABSTRACTO y no genera tablas en BD.
Se instancia desde los controllers para acceder a los métodos de negocio.

Uso:
    compras_service = self.env['compras.service']
    domain = compras_service.construir_domain_filtros(kwargs)
    proveedor = compras_service.crear_proveedor_rapido(nombre)
    orden = compras_service.crear_orden_compra(proveedor_id, lineas)
    compras_service.confirmar_orden_compra(orden_id)

==============================================================================
"""

from odoo import models, api
from datetime import datetime, timedelta


class ComprasService(models.AbstractModel):
    """Servicio centralizado de lógica de negocio para compras_web"""
    
    _name = 'compras.service'
    _description = 'Servicio de Compras Web'

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 1: FILTROS AVANZADOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def construir_domain_filtros(self, kwargs):
        """
        Construye un domain (filtro ORM) basado en parámetros GET.
        
        Soporta:
        - proveedor: búsqueda por nombre en partner_id (ilike)
        - producto: búsqueda en order_line.product_id (ilike)
        - fecha_desde / fecha_hasta: rango de date_order
        - monto_min / monto_max: rango de amount_total
        - categoria: product_id.categ_id (ID exacto)
        - estado: state ('draft', 'purchase', 'cancel')
        
        Args:
            kwargs (dict): Parámetros GET del request
        
        Returns:
            list: Domain Odoo para search()
        """
        domain = []

        # ── Filtro: Proveedor (name) ──
        proveedor = kwargs.get('proveedor', '').strip()
        if proveedor:
            domain.append(('partner_id.name', 'ilike', proveedor))

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

        # ── Filtro: Estado ──
        estado = kwargs.get('estado', '').strip()
        if estado in ('draft', 'purchase', 'cancel'):
            domain.append(('state', '=', estado))

        return domain

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 2: GESTIÓN DE PROVEEDORES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def crear_proveedor_rapido(self, nombre):
        """
        Crea un proveedor rápidamente o retorna uno existente.
        
        Verifica:
        - Si ya existe un proveedor con el mismo nombre
        - Si no existe, lo crea
        
        Args:
            nombre (str): Nombre del proveedor (obligatorio)
        
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
                'message': 'El nombre del proveedor es obligatorio.',
            }

        try:
            ResPartner = self.env['res.partner']
            
            # ── Buscar proveedor existente ──
            proveedor_existente = ResPartner.sudo().search(
                [('name', '=', nombre), ('supplier_rank', '>', 0)],
                limit=1
            )
            
            if proveedor_existente:
                return {
                    'success': True,
                    'id': proveedor_existente.id,
                    'nombre': proveedor_existente.name,
                    'es_nuevo': False,
                    'message': 'Proveedor ya existe.',
                }

            # ── Crear nuevo proveedor ──
            proveedor_nuevo = ResPartner.sudo().create({
                'name': nombre,
                'supplier_rank': 1,  # Marcar como proveedor
                'type': 'invoice',  # Dirección de facturación
            })

            return {
                'success': True,
                'id': proveedor_nuevo.id,
                'nombre': proveedor_nuevo.name,
                'es_nuevo': True,
                'message': 'Proveedor creado exitosamente.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear proveedor: {str(e)}',
            }

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 3: GESTIÓN DE ÓRDENES DE COMPRA
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def crear_orden_compra(self, proveedor_id, lineas):
        """
        Crea una nueva orden de compra con líneas de productos.
        
        IMPORTANTE: La orden se crea en estado DRAFT sin modificar stock.
        El stock solo se incrementa en la confirmación.
        
        FLUJO:
        1. Valida proveedor
        2. Valida líneas
        3. Crea purchase.order en DRAFT
        4. Crea purchase.order.line para cada producto
        
        Args:
            proveedor_id (int): ID del proveedor (res.partner)
            lineas (list): [{'product_id': int, 'cantidad': float, 'precio_unitario': float}, ...]
        
        Returns:
            dict: {
                'success': bool,
                'orden_id': int,
                'nombre_orden': str,
                'message': str,
                'url': str
            }
        """
        try:
            # ── Validar proveedor ──
            proveedor = self.env['res.partner'].sudo().browse(int(proveedor_id))
            if not proveedor.exists():
                return {
                    'success': False,
                    'message': 'Proveedor no encontrado.',
                }

            # ── Validar líneas ──
            if not lineas or not isinstance(lineas, list):
                return {
                    'success': False,
                    'message': 'Debe agregar al menos un producto.',
                }

            # ── Crear orden (DRAFT) ──
            orden_vals = {
                'partner_id': proveedor.id,
                'state': 'draft',
                'date_order': datetime.now(),
            }

            orden_compra = self.env['purchase.order'].sudo().create(orden_vals)

            # ── Crear líneas de compra ──
            self._crear_lineas_compra(orden_compra, lineas)

            return {
                'success': True,
                'orden_id': orden_compra.id,
                'nombre_orden': orden_compra.name,
                'message': f'Orden {orden_compra.name} creada exitosamente.',
                'url': '/compras',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear la compra: {str(e)}',
            }

    @api.model
    def _crear_lineas_compra(self, orden, lineas):
        """
        Crea las líneas de orden de compra.
        
        Ignora líneas mal formadas sin causar fallo general.
        
        Args:
            orden (purchase.order): Orden ya creada
            lineas (list): [{'product_id': int, 'cantidad': float, 'precio_unitario': float}, ...]
        """
        for linea_data in lineas:
            try:
                product_id = int(linea_data.get('product_id', 0))
                cantidad = float(linea_data.get('cantidad', 1))
                precio_unt = float(linea_data.get('precio_unitario', 0))

                # Validaciones
                if product_id <= 0 or cantidad <= 0 or precio_unt < 0:
                    continue

                producto = self.env['product.product'].sudo().browse(product_id)
                if not producto.exists():
                    continue

                # Crear línea con precio unitario
                self.env['purchase.order.line'].sudo().create({
                    'order_id': orden.id,
                    'product_id': producto.id,
                    'product_qty': cantidad,
                    'price_unit': precio_unt,
                })

            except (ValueError, TypeError, Exception):
                # Ignorar líneas mal formadas; continuar con las siguientes
                continue

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 4: CONFIRMACIÓN DE ÓRDENES (CON INCREMENTO DE STOCK)
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def confirmar_orden_compra(self, orden_id):
        """
        Confirma una orden de compra e INCREMENTA STOCK.
        
        PROCESO:
        1. Ejecuta button_confirm() de Odoo (estado DRAFT → PURCHASE)
        2. Busca ubicación interna (WH/Stock)
        3. Para cada línea, incrementa stock.quant en ubicación
        
        IMPORTANTE: Evita confirmaciones duplicadas verificando estado
        
        Args:
            orden_id (int): ID de la purchase.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        try:
            orden = self.env['purchase.order'].sudo().browse(int(orden_id))

            # ── Validar existencia ──
            if not orden.exists():
                return {
                    'success': False,
                    'message': 'Orden no encontrada.',
                }

            # ── Validar estado (solo confirmar si está en DRAFT) ──
            if orden.state != 'draft':
                return {
                    'success': False,
                    'message': f'Solo se pueden confirmar órdenes en DRAFT. Estado actual: {orden.state}',
                }

            # ── PASO 1: Confirmar orden (DRAFT → PURCHASE) ──
            try:
                orden.button_confirm()
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Error al confirmar orden: {str(e)}',
                }

            # ── PASO 2: Incrementar stock en WH/Stock ──
            resultado_stock = self._incrementar_stock_compra(orden)
            if not resultado_stock['success']:
                return resultado_stock  # Retornar error

            return {
                'success': True,
                'message': f'Orden {orden.name} confirmada. Stock incrementado.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error inesperado: {str(e)}',
            }

    @api.model
    def _incrementar_stock_compra(self, orden):
        """
        Incrementa el stock para cada línea de la orden de compra.
        
        IMPORTANTE: Solo incrementa stock para productos tipo 'product'.
        Ignora consumibles y servicios automáticamente.
        
        Busca la ubicación interna (WH/Stock) y actualiza stock.quant
        
        Args:
            orden (purchase.order): Orden ya confirmada
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            # Buscar ubicación interna (WH/Stock)
            ubicacion_stock = self.env['stock.location'].sudo().search(
                [('usage', '=', 'internal')],
                limit=1
            )

            if not ubicacion_stock:
                return {
                    'success': False,
                    'message': 'No se encontró una ubicación de inventario válida (WH/Stock).',
                }

            # Incrementar stock para cada línea de compra
            productos_ignorados = 0
            for linea in orden.order_line:
                if linea.product_id and linea.product_qty > 0:
                    # ── VALIDAR: Solo productos tipo 'product' tienen stock ──
                    if linea.product_id.type != 'product':
                        # Ignorar consumibles y servicios
                        productos_ignorados += 1
                        continue
                    
                    self._actualizar_quant_compra(
                        linea.product_id,
                        ubicacion_stock,
                        linea.product_qty
                    )

            return {
                'success': True,
                'message': 'Stock incrementado exitosamente.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al actualizar stock: {str(e)}',
            }

    @api.model
    def _actualizar_quant_compra(self, producto, ubicacion, cantidad):
        """
        Actualiza o crea stock.quant para un producto en una ubicación.
        
        PRECONDICIÓN: El producto DEBE ser tipo 'product'.
        Esta función NO valida el tipo (se valida en _incrementar_stock_compra).
        
        Si el producto ya existe en la ubicación, suma la cantidad.
        Si no existe, crea un nuevo registro.
        
        Args:
            producto (product.product): Producto a actualizar (type='product')
            ubicacion (stock.location): Ubicación de stock
            cantidad (float): Cantidad a sumar
        """
        Quant = self.env['stock.quant'].sudo()
        
        # Buscar quant existente
        quant = Quant.search([
            ('product_id', '=', producto.id),
            ('location_id', '=', ubicacion.id)
        ], limit=1)

        if quant:
            # Actualizar cantidad existente
            quant.write({
                'inventory_quantity': quant.inventory_quantity + cantidad
            })
        else:
            # Crear nuevo quant
            Quant.create({
                'product_id': producto.id,
                'location_id': ubicacion.id,
                'inventory_quantity': cantidad,
            })

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 5: CANCELACIÓN DE ÓRDENES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def cancelar_orden_compra(self, orden_id):
        """
        Cancela una orden de compra.
        
        IMPORTANTE: NO modifica stock bajo ninguna circunstancia.
        - Si la orden NO fue confirmada: No hay stock que revertir
        - Si ya fue confirmada: El usuario es responsable de reversión manual
        
        Args:
            orden_id (int): ID de la purchase.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        try:
            orden = self.env['purchase.order'].sudo().browse(int(orden_id))

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
            orden.button_cancel()

            return {
                'success': True,
                'message': f'Orden {orden.name} cancelada. No se modificó stock.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al cancelar: {str(e)}',
            }
