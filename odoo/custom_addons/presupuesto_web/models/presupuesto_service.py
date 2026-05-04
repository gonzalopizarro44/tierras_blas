"""
==============================================================================
SERVICIO DE PRESUPUESTOS - Presupuesto Service
==============================================================================

Centraliza TODA la lógica de negocio del módulo presupuesto_web:
- Filtros avanzados del panel
- Creación de clientes rápidos
- Creación de presupuestos (cotizaciones draft en Odoo)
- Cancelación de presupuestos

Los presupuestos se guardan como sale.order en estado DRAFT (cotización).
NO se confirman automáticamente — permanecen como cotizaciones.

Uso:
    service = self.env['presupuesto.service']
    domain = service.build_presupuesto_filters(kwargs)
    presupuesto = service.create_presupuesto(cliente_id, lineas)

==============================================================================
"""

from odoo import models, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class PresupuestoService(models.AbstractModel):
    """Servicio centralizado de lógica de negocio para presupuesto_web"""

    _name = 'presupuesto.service'
    _description = 'Servicio de Presupuestos Web'

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 1: FILTROS AVANZADOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def build_presupuesto_filters(self, kwargs):
        """
        Construye un domain (filtro ORM) para presupuestos.

        Los presupuestos son sale.order con presupuesto_origin = 'presupuesto_web'.
        
        Soporta:
        - cliente: búsqueda por nombre (ilike)
        - producto: búsqueda en order_line.product_id (ilike)
        - fecha_desde / fecha_hasta: rango de date_order
        - monto_min / monto_max: rango de amount_total
        
        Args:
            kwargs (dict): Parámetros GET del request
        
        Returns:
            list: Domain Odoo para search()
        """
        # Solo mostrar cotizaciones creadas desde presupuesto_web que estén pendientes
        domain = [
            ('presupuesto_origin', '=', 'presupuesto_web'),
            ('state', 'in', ['draft', 'sent']),
        ]

        # ── Filtro: Cliente ──
        cliente = kwargs.get('cliente', '').strip()
        if cliente:
            domain.append(('partner_id.name', 'ilike', cliente))

        # ── Filtro: Producto ──
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
                pass

        # ── Filtro: Rango de fechas (fecha_hasta) ──
        fecha_hasta = kwargs.get('fecha_hasta', '').strip()
        if fecha_hasta:
            try:
                dt = datetime.strptime(fecha_hasta, '%Y-%m-%d')
                dt_fin = dt + timedelta(days=1)
                domain.append(('date_order', '<', dt_fin))
            except ValueError:
                pass

        # ── Filtro: Monto mínimo ──
        monto_min = kwargs.get('monto_min', '').strip()
        if monto_min:
            try:
                domain.append(('amount_total', '>=', float(monto_min)))
            except (ValueError, TypeError):
                pass

        # ── Filtro: Monto máximo ──
        monto_max = kwargs.get('monto_max', '').strip()
        if monto_max:
            try:
                domain.append(('amount_total', '<=', float(monto_max)))
            except (ValueError, TypeError):
                pass

        return domain

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 2: GESTIÓN DE CLIENTES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def create_quick_customer(self, nombre, dni=None):
        """
        Crea un cliente rápidamente o retorna uno existente.
        
        Args:
            nombre (str): Nombre completo del cliente (obligatorio)
            dni (str): DNI o documento (opcional, se guarda en 'vat')
        
        Returns:
            dict: {'success': bool, 'id': int, 'nombre': str, 'es_nuevo': bool, 'message': str}
        """
        nombre = (nombre or '').strip()
        if not nombre:
            return {
                'success': False,
                'message': 'El nombre del cliente es obligatorio.',
            }

        try:
            ResPartner = self.env['res.partner']

            # Buscar cliente existente
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

            # Crear nuevo cliente
            cliente_nuevo = ResPartner.sudo().create({
                'name': nombre,
                'vat': dni or '',
                'customer_rank': 1,
                'type': 'invoice',
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
    # SECCIÓN 3: CREACIÓN DE PRESUPUESTOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def create_presupuesto(self, cliente_id, lineas):
        """
        Crea un presupuesto (cotización draft en Odoo).
        
        A diferencia de ventas, NO se confirma automáticamente.
        Los precios unitarios son los que el usuario definió en el formulario.
        
        FLUJO:
        1. Valida cliente
        2. Valida líneas
        3. Crea sale.order en DRAFT con presupuesto_origin = 'presupuesto_web'
        4. Crea sale.order.line para cada producto con el precio indicado
        
        Args:
            cliente_id (int): ID del cliente (res.partner)
            lineas (list): [{'product_id': int, 'quantity': float, 'price_unit': float}, ...]
        
        Returns:
            dict: {'success': bool, 'order_id': int, 'order_name': str, 'message': str, 'url': str}
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

            # ── Crear orden (DRAFT = cotización) ──
            orden = self.env['sale.order'].sudo().create({
                'partner_id': cliente.id,
                'presupuesto_origin': 'presupuesto_web',
                'state': 'draft',
                'date_order': datetime.now(),
            })

            # ── Crear líneas de orden ──
            for linea_data in lineas:
                try:
                    product_id = int(linea_data.get('product_id', 0))
                    cantidad = float(linea_data.get('quantity', 1))
                    precio = float(linea_data.get('price_unit', 0))

                    if product_id <= 0 or cantidad <= 0:
                        continue

                    producto = self.env['product.product'].sudo().browse(product_id)
                    if not producto.exists():
                        continue

                    # Usar el precio que definió el usuario (editable)
                    if precio <= 0:
                        precio = producto.list_price

                    self.env['sale.order.line'].sudo().create({
                        'order_id': orden.id,
                        'product_id': producto.id,
                        'product_uom_qty': cantidad,
                        'price_unit': precio,
                    })

                except (ValueError, TypeError, Exception):
                    continue

            _logger.info(f"[PRESUPUESTO_WEB] Presupuesto {orden.name} creado para cliente {cliente.name}")

            return {
                'success': True,
                'order_id': orden.id,
                'order_name': orden.name,
                'message': f'Presupuesto {orden.name} creado exitosamente.',
                'url': '/presupuestos',
            }

        except Exception as e:
            _logger.error(f"[PRESUPUESTO_WEB] Error al crear presupuesto: {str(e)}")
            return {
                'success': False,
                'message': f'Error al crear el presupuesto: {str(e)}',
            }

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 4: CANCELACIÓN DE PRESUPUESTOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def cancelar_presupuesto(self, order_id):
        """
        Cancela un presupuesto (cotización).
        
        Args:
            order_id (int): ID de la sale.order
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            orden = self.env['sale.order'].sudo().browse(int(order_id))

            if not orden.exists():
                return {
                    'success': False,
                    'message': 'Presupuesto no encontrado.',
                }

            if orden.state == 'cancel':
                return {
                    'success': False,
                    'message': 'Este presupuesto ya está cancelado.',
                }

            orden.action_cancel()

            return {
                'success': True,
                'message': f'Presupuesto {orden.name} cancelado.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al cancelar: {str(e)}',
            }
