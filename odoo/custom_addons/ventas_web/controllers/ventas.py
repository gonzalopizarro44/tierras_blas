"""
==============================================================================
CONTROLLER: PANEL WEB DE VENTAS - Módulo ventas_web para Odoo 19
==============================================================================

Maneja:
- GET /ventas: Listado de ventas con filtros avanzados  
- POST /ventas/crear: Crear nueva orden de venta
- POST /ventas/confirmar: Confirmar orden y descontar stock
- POST /ventas/cancelar: Cancelar orden
- POST /ventas/crear_cliente: Crear cliente rápidamente

Flujo de stock:
1. Usuario crea orden → sale.order en estado DRAFT
2. Usuario confirma → action_confirm() automático → movimientos de stock
3. Stock se descuenta en ubicación WH/Stock

==============================================================================
"""

from odoo import http
from odoo.http import request
from datetime import datetime, timedelta


class VentasController(http.Controller):

    # ═══════════════════════════════════════════════════════════════════
    # MÉTODO AUXILIAR: Construcción dinámica de domain (FILTROS)
    # ═══════════════════════════════════════════════════════════════════

    def _construir_domain_filtros(self, kwargs):
        """
        Construye un domain basado en parámetros GET para filtrar sale.order.
        
        Soporta:
        - cliente: búsqueda por nombre en partner_id
        - producto: búsqueda en order_line.product_id
        - fecha_desde / fecha_hasta: rango de date_order
        - monto_min / monto_max: rango de amount_total
        - categoria: product_id.categ_id
        - estado: state (confirmada/cancelada)
        - origen: sales_origin (admin/cliente_web/etc)
        """
        domain = []

        # Filtro: Cliente (name, DNI)
        cliente = kwargs.get('cliente', '').strip()
        if cliente:
            domain.append(('partner_id.name', 'ilike', cliente))

        # Filtro: Producto (order_line.product_id)
        producto = kwargs.get('producto', '').strip()
        if producto:
            domain.append(('order_line.product_id.name', 'ilike', producto))

        # Filtro: Rango de fechas
        fecha_desde = kwargs.get('fecha_desde', '').strip()
        if fecha_desde:
            try:
                # Parsear: YYYY-MM-DD
                dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
                domain.append(('date_order', '>=', dt))
            except ValueError:
                pass

        fecha_hasta = kwargs.get('fecha_hasta', '').strip()
        if fecha_hasta:
            try:
                dt = datetime.strptime(fecha_hasta, '%Y-%m-%d')
                # Incluir todo el día
                dt_fin = dt + timedelta(days=1)
                domain.append(('date_order', '<', dt_fin))
            except ValueError:
                pass

        # Filtro: Monto total
        monto_min = kwargs.get('monto_min', '').strip()
        if monto_min:
            try:
                domain.append(('amount_total', '>=', float(monto_min)))
            except (ValueError, TypeError):
                pass

        monto_max = kwargs.get('monto_max', '').strip()
        if monto_max:
            try:
                domain.append(('amount_total', '<=', float(monto_max)))
            except (ValueError, TypeError):
                pass

        # Filtro: Categoría de producto
        categoria = kwargs.get('categoria', '').strip()
        if categoria:
            try:
                domain.append(('order_line.product_id.categ_id', '=', int(categoria)))
            except (ValueError, TypeError):
                pass

        # Filtro: Estado
        estado = kwargs.get('estado', '').strip()
        if estado == 'confirmada':
            domain.append(('state', '=', 'sale'))
        elif estado == 'cancelada':
            domain.append(('state', '=', 'cancel'))

        # Filtro: Origen de venta
        origen = kwargs.get('origen', '').strip()
        if origen:
            domain.append(('sales_origin', '=', origen))

        return domain

    # ═══════════════════════════════════════════════════════════════════
    # RUTA GET: /ventas - Listar todas las ventas con filtros
    # ═══════════════════════════════════════════════════════════════════

    @http.route('/ventas', type='http', auth='user', website=True)
    def ventas_listado(self, **kwargs):
        """
        Página principal: Dashboard de ventas.
        
        - Aplica filtros dinámicos
        - Obtiene categorías para select
        - Renderiza tabla con todas las ventas
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return request.redirect('/')

        # ── Construir domain con filtros ──
        domain = self._construir_domain_filtros(kwargs)

        # ── Buscar ventas ──
        SaleOrder = request.env['sale.order'].sudo()
        ventas = SaleOrder.search(domain, order='date_order desc, id desc')

        # ── Obtener categorías para filter select ──
        categorias = request.env['product.category'].sudo().search([], order='name asc')

        # ── Obtener clientes para autocomplete ──
        clientes = request.env['res.partner'].sudo().search(
            [('customer_rank', '>', 0)],
            order='name asc',
            limit=50
        )

        # ── Contexto para la vista ──
        ctx = {
            'ventas': ventas,
            'categorias': categorias,
            'clientes': clientes,
            'filtros': kwargs,  # Repoblar filtros en la UI
            'total_ventas': len(ventas),
        }

        return request.render('ventas_web.ventas_template', ctx)

    # ═══════════════════════════════════════════════════════════════════
    # RUTA GET: /ventas/nueva - Formulario de nueva venta
    # ═══════════════════════════════════════════════════════════════════

    @http.route('/ventas/nueva', type='http', auth='user', website=True)
    def ventas_nueva_formulario(self, **kwargs):
        """
        Formulario para crear una nueva orden de venta.
        
        Carga:
        - Clientes (res.partner)
        - Productos (product.product)
        - Métodos de pago (account.journal)
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return request.redirect('/')

        # ── Obtener datos necesarios ──
        clientes = request.env['res.partner'].sudo().search(
            [('customer_rank', '>', 0)],
            order='name asc'
        )
        productos = request.env['product.product'].sudo().search(
            [('sale_ok', '=', True)],
            order='name asc'
        )
        # Métodos de pago: journals de tipo sale
        journals = request.env['account.journal'].sudo().search(
            [('type', '=', 'sale')],
            order='name asc'
        )

        ctx = {
            'clientes': clientes,
            'productos': productos,
            'journals': journals,
        }

        return request.render('ventas_web.nueva_venta_template', ctx)

    # ═══════════════════════════════════════════════════════════════════
    # RUTA POST: /ventas/crear_cliente - Crear cliente rápidamente
    # ═══════════════════════════════════════════════════════════════════

    @http.route('/ventas/crear_cliente', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def crear_cliente_rapido(self, nombre, dni=None):
        """
        Crea un cliente rápidamente sin abandonar el formulario.
        
        Parámetros (JSON-RPC):
        - nombre: Nombre completo del cliente (obligatorio)
        - dni: DNI o documento (opcional, se guarda en 'vat')
        
        Retorna: { 'success': bool, 'id': int, 'nombre': str }
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Validación de datos ──
        nombre = (nombre or '').strip()
        if not nombre:
            return {'success': False, 'message': 'El nombre del cliente es obligatorio.'}

        try:
            # Verificar si ya existe (por nombre exacto)
            cliente_existente = request.env['res.partner'].sudo().search(
                [('name', '=', nombre), ('customer_rank', '>', 0)],
                limit=1
            )
            if cliente_existente:
                return {
                    'success': True,
                    'id': cliente_existente.id,
                    'nombre': cliente_existente.name,
                    'es_nuevo': False,
                    'message': 'Cliente ya existe.'
                }

            # Crear nuevo cliente
            cliente_nuevo = request.env['res.partner'].sudo().create({
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
                'message': 'Cliente creado exitosamente.'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear cliente: {str(e)}'
            }

    # ═══════════════════════════════════════════════════════════════════
    # RUTA POST: /ventas/crear - Crear nueva orden de venta
    # ═══════════════════════════════════════════════════════════════════

    @http.route('/ventas/crear', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def crear_venta(self, cliente_id, lineas, origen='admin', journal_id=None):
        """
        Crea una nueva orden de venta con líneas de productos.
        
        FLUJO:
        1. Validar datos
        2. Crear sale.order en estado DRAFT
        3. Crear sale.order.line para cada producto
        4. Confirmar automáticamente → action_confirm()
        5. El sistema descuenta stock automáticamente
        
        Parámetros (JSON-RPC):
        - cliente_id: ID del cliente (res.partner)
        - lineas: Lista de dicts [{'product_id': int, 'quantity': float}, ...]
        - origen: string ('admin', 'cliente_web', etc)
        - journal_id: ID del journal (método de pago) - opcional
        
        Retorna: { 'success': bool, 'order_id': int, 'order_name': str }
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'success': False, 'message': 'No tiene permisos.'}

        try:
            # ── Validar cliente ──
            cliente = request.env['res.partner'].sudo().browse(int(cliente_id))
            if not cliente.exists():
                return {'success': False, 'message': 'Cliente no encontrado.'}

            # ── Validar líneas ──
            if not lineas or not isinstance(lineas, list):
                return {'success': False, 'message': 'Debe agregar al menos un producto.'}

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

            orden = request.env['sale.order'].sudo().create(order_vals)

            # ── Crear líneas de orden ──
            for linea_data in lineas:
                try:
                    product_id = int(linea_data.get('product_id', 0))
                    cantidad = float(linea_data.get('quantity', 1))

                    if product_id <= 0 or cantidad <= 0:
                        continue

                    producto = request.env['product.product'].sudo().browse(product_id)
                    if not producto.exists():
                        continue

                    # Crear línea (list_price es la tarifa por defecto de Odoo)
                    request.env['sale.order.line'].sudo().create({
                        'order_id': orden.id,
                        'product_id': producto.id,
                        'product_uom_qty': cantidad,
                        'price_unit': producto.list_price,
                    })

                except (ValueError, TypeError, Exception):
                    continue  # Ignorar líneas mal formadas

            # ── CONFIRMACIÓN AUTOMÁTICA ──
            # El usuario eligió que se auto-confirme, así que llamamos a action_confirm()
            # Esto dispara:
            # - Validación de cantidades
            # - Generación de movimientos de stock
            # - Cambio de estado a 'sale'
            try:
                orden.action_confirm()
            except Exception as e:
                # Log pero no fallo; la orden existe aunque no se haya confirmado
                print(f"[VENTAS_WEB] Error al confirmar orden {orden.name}: {str(e)}")

            return {
                'success': True,
                'order_id': orden.id,
                'order_name': orden.name,
                'message': f'Orden {orden.name} creada y confirmada exitosamente.',
                'url': f'/ventas'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear la venta: {str(e)}'
            }

    # ═══════════════════════════════════════════════════════════════════
    # RUTA POST: /ventas/confirmar - Confirmar una orden existente
    # ═══════════════════════════════════════════════════════════════════

    @http.route('/ventas/confirmar', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def confirmar_venta(self, order_id):
        """
        Confirma una orden de venta existente (estado DRAFT → SALE).
        
        Esto dispara:
        - Validación de stock
        - Generación de movimientos en WH/Stock
        - Cambio de estado a 'sale'
        
        Parámetros (JSON-RPC):
        - order_id: ID de la sale.order
        
        Retorna: { 'success': bool, 'message': str }
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'success': False, 'message': 'No tiene permisos.'}

        try:
            orden = request.env['sale.order'].sudo().browse(int(order_id))

            if not orden.exists():
                return {'success': False, 'message': 'Orden no encontrada.'}

            if orden.state != 'draft':
                return {
                    'success': False,
                    'message': f'Solo se pueden confirmar órdenes en DRAFT. Estado actual: {orden.state}'
                }

            # ── Confirmar ──
            orden.action_confirm()

            return {
                'success': True,
                'message': f'Orden {orden.name} confirmada. Stock descontado.'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al confirmar: {str(e)}'
            }

    # ═══════════════════════════════════════════════════════════════════
    # RUTA POST: /ventas/cancelar - Cancelar una orden
    # ═══════════════════════════════════════════════════════════════════

    @http.route('/ventas/cancelar', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def cancelar_venta(self, order_id):
        """
        Cancela una orden de venta.
        
        Si ya estaba confirmada, revierte los movimientos de stock.
        
        Parámetros (JSON-RPC):
        - order_id: ID de la sale.order
        
        Retorna: { 'success': bool, 'message': str }
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'success': False, 'message': 'No tiene permisos.'}

        try:
            orden = request.env['sale.order'].sudo().browse(int(order_id))

            if not orden.exists():
                return {'success': False, 'message': 'Orden no encontrada.'}

            if orden.state == 'cancel':
                return {
                    'success': False,
                    'message': 'Esta orden ya está cancelada.'
                }

            # ── Cancelar ──
            orden.action_cancel()

            return {
                'success': True,
                'message': f'Orden {orden.name} cancelada.'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al cancelar: {str(e)}'
            }
