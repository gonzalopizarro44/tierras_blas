"""
==============================================================================
CONTROLLER: PANEL WEB DE VENTAS - Módulo ventas_web para Odoo 19
==============================================================================

REFACTORIZADO: Controllers LIVIANOS que solo manejan HTTP

Rutas:
- GET /ventas: Listado de ventas con filtros avanzados (HTTP)
- GET /ventas/nueva: Formulario para nueva venta (HTTP)
- POST /ventas/crear_cliente: Crear cliente rápidamente (JSON-RPC)
- POST /ventas/crear: Crear nueva orden de venta (JSON-RPC)
- POST /ventas/confirmar: Confirmar orden (JSON-RPC)
- POST /ventas/cancelar: Cancelar orden (JSON-RPC)

LÓGICA DE NEGOCIO:
→ Toda la lógica está en models/sales_service.py
→ Controllers solo parseam requests y llaman al servicio

FLUJO DE STOCK:
1. Usuario crea orden → sale.order en estado DRAFT
2. Usuario confirma → service.confirm_sale_order() → action_confirm() automático
3. Stock se descuenta en ubicación WH/Stock automáticamente

==============================================================================
"""

from odoo import http
from odoo.http import request


class VentasController(http.Controller):
    """Controller para gestión web de ventas - REFACTORIZADO a service layer"""

    # ═════════════════════════════════════════════════════════════════════════
    # MÉTODO AUXILIAR: Validación de permisos
    # ═════════════════════════════════════════════════════════════════════════

    def _check_permissions(self):
        """
        Valida que el usuario tenga permisos de administrador en ventas.
        
        Returns:
            bool: True si tiene permisos, False si no
        """
        return request.env.user.has_group('permisos_usuarios.group_administrador')

    def _get_sales_service(self):
        """
        Obtiene la instancia del servicio de ventas.
        
        Returns:
            sales.service: Instancia del servicio
        """
        return request.env['sales.service']

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA GET: /ventas - Listar todas las ventas con filtros
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/ventas', type='http', auth='user', website=True)
    def ventas_listado(self, **kwargs):
        """
        Página principal: Dashboard de ventas con filtros avanzados.
        
        Params (GET):
        - cliente: Buscar por nombre de cliente
        - producto: Buscar por nombre de producto
        - fecha_desde: Fecha inicial (YYYY-MM-DD)
        - fecha_hasta: Fecha final (YYYY-MM-DD)
        - monto_min / monto_max: Rango de montos
        - categoria: ID de categoría de producto
        - estado: 'confirmada' o 'cancelada'
        - origen: Origen de la venta
        
        Returns:
            http.Response: Página HTML renderizada
        """
        # ── Validar permisos ──
        if not self._check_permissions():
            return request.redirect('/')

        # ── Obtener servicio ──
        sales_service = self._get_sales_service()

        # ── Construir filtros usando el servicio ──
        domain = sales_service.build_sale_filters(kwargs)

        # ── Buscar ventas ──
        ventas = request.env['sale.order'].sudo().search(
            domain,
            order='date_order desc, id desc'
        )

        # ── ENRIQUECIMIENTO: Calcular entregas pendientes en BATCH (sin N+1) ──
        # En lugar de iterar y hacer queries individuales, hacemos una búsqueda única
        # que obtiene TODOS los order_ids que tienen pickings outgoing pendientes
        order_ids = [v.id for v in ventas]
        
        if order_ids:
            # Búsqueda ÚNICA en batch: obtiene entregas pendientes para TODAS las órdenes
            pickings_pendientes = request.env['stock.picking'].sudo().search([
                ('sale_id', 'in', order_ids),
                ('picking_type_code', '=', 'outgoing'),
                ('state', 'in', ['assigned', 'confirmed']),
            ])
            # Crear un set de order_ids que tienen entregas pendientes (búsqueda O(1))
            order_ids_con_entregas = set(pickings_pendientes.mapped('sale_id.id'))
        else:
            order_ids_con_entregas = set()

        # ── Obtener datos para la UI ──
        categorias = request.env['product.category'].sudo().search(
            [],
            order='name asc'
        )
        clientes = request.env['res.partner'].sudo().search(
            [('customer_rank', '>', 0)],
            order='name asc',
            limit=50
        )

        # ── Contexto para la vista ──
        ctx = {
            'ventas': ventas,
            'order_ids_con_entregas': order_ids_con_entregas,
            'categorias': categorias,
            'clientes': clientes,
            'filtros': kwargs,  # Repoblar filtros en la UI
            'total_ventas': len(ventas),
        }

        return request.render('ventas_web.ventas_template', ctx)

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA GET: /ventas/nueva - Formulario de nueva venta
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/ventas/nueva', type='http', auth='user', website=True)
    def ventas_nueva_formulario(self, **kwargs):
        """
        Formulario para crear una nueva orden de venta.
        
        Carga:
        - Clientes (res.partner) con customer_rank > 0
        - Productos (product.product) con sale_ok = True
        - Métodos de pago (account.journal) tipo 'sale'
        
        Returns:
            http.Response: Página HTML del formulario
        """
        # ── Validar permisos ──
        if not self._check_permissions():
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
        journals = request.env['account.journal'].sudo().search(
            [('type', '=', 'sale')],
            order='name asc'
        )

        # ── Enriquecer productos con stock disponible ──
        # Crear diccionarios mapeados con información de stock (sin modificar ORM)
        productos_formateados = []
        for p in productos:
            # Obtener cantidad disponible según tipo de producto
            if p.type == 'service':
                # Los servicios no tienen stock
                stock = 0
                nombre_visual = p.display_name
                is_service = True
            else:
                # Productos físicos: usar free_qty (cantidad disponible)
                stock = p.free_qty
                nombre_visual = "{} - Stock: {} u.".format(
                    p.display_name,
                    int(stock) if stock == int(stock) else stock
                )
                is_service = False
            
            productos_formateados.append({
                'id': p.id,
                'name': p.name,
                'display_name': nombre_visual,
                'list_price': p.list_price,
                'free_qty': stock,
                'type': p.type,
                'is_service': is_service
            })

        ctx = {
            'clientes': clientes,
            'productos': productos_formateados,
            'journals': journals,
        }

        return request.render('ventas_web.nueva_venta_template', ctx)

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /ventas/crear_cliente - Crear cliente rápidamente
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/ventas/crear_cliente', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def crear_cliente_rapido(self, nombre, dni=None):
        """
        Crea un cliente rápidamente sin abandonar el formulario.
        
        Usa: sales_service.create_quick_customer()
        
        Parámetros (JSON-RPC):
        - nombre: Nombre completo del cliente (obligatorio)
        - dni: DNI o documento (opcional)
        
        Returns:
            dict: {
                'success': bool,
                'id': int,
                'nombre': str,
                'es_nuevo': bool,
                'message': str
            }
        """
        # ── Validar permisos ──
        if not self._check_permissions():
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Llamar al servicio ──
        sales_service = self._get_sales_service()
        resultado = sales_service.create_quick_customer(nombre, dni)

        return resultado

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /ventas/crear - Crear nueva orden de venta
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/ventas/crear', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def crear_venta(self, cliente_id, lineas, origen='admin', journal_id=None):
        """
        Crea una nueva orden de venta con líneas de productos.
        
        Usa: sales_service.create_sale_order()
        
        FLUJO:
        1. Valida datos
        2. Crea sale.order
        3. Crea sale.order.line para cada producto
        4. Confirma automáticamente
        5. El sistema descuenta stock automáticamente
        
        Parámetros (JSON-RPC):
        - cliente_id: ID del cliente (res.partner)
        - lineas: Lista de dicts [{'product_id': int, 'quantity': float}, ...]
        - origen: string ('admin', 'cliente_web', etc) - default: 'admin'
        - journal_id: ID del journal de pago - opcional
        
        Returns:
            dict: {
                'success': bool,
                'order_id': int,
                'order_name': str,
                'message': str,
                'url': str
            }
        """
        # ── Validar permisos ──
        if not self._check_permissions():
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Llamar al servicio ──
        sales_service = self._get_sales_service()
        resultado = sales_service.create_sale_order(
            cliente_id=cliente_id,
            lineas=lineas,
            origen=origen,
            journal_id=journal_id
        )

        return resultado

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /ventas/confirmar - Confirmar una orden existente
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/ventas/confirmar', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def confirmar_venta(self, order_id):
        """
        Confirma una orden de venta existente (DRAFT → SALE).
        
        Usa: sales_service.confirm_sale_order()
        
        Esto dispara:
        - Validación de stock
        - Generación de movimientos en WH/Stock
        - Cambio de estado a 'sale'
        
        Parámetros (JSON-RPC):
        - order_id: ID de la sale.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        # ── Validar permisos ──
        if not self._check_permissions():
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Llamar al servicio ──
        sales_service = self._get_sales_service()
        resultado = sales_service.confirm_sale_order(order_id)

        return resultado

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /ventas/cancelar - Cancelar una orden
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/ventas/cancelar', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def cancelar_venta(self, order_id):
        """
        Cancela una orden de venta.
        
        Usa: sales_service.cancel_sale_order()
        
        Si la orden estaba confirmada:
        - Revierte los movimientos de stock
        
        Parámetros (JSON-RPC):
        - order_id: ID de la sale.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        # ── Validar permisos ──
        if not self._check_permissions():
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Llamar al servicio ──
        sales_service = self._get_sales_service()
        resultado = sales_service.cancel_sale_order(order_id)

        return resultado

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /ventas/validar_entrega - Validar entrega (stock.picking)
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/ventas/validar_entrega', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def validar_entrega_venta(self, order_id):
        """
        Valida las entregas (pickings outgoing) de una orden de venta.
        
        Usa: sales_service.validar_entrega_venta()
        
        PROCESO:
        - Busca todas las entregas asociadas a la orden
        - Para cada entrega en estado 'assigned' o 'confirmed':
          1. Confirma si está en draft
          2. Asigna stock disponible
          3. Prepara move_lines con cantidades
          4. Valida el picking (descuenta stock)
        
        Parámetros (JSON-RPC):
        - order_id: ID de la sale.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'entregas_validadas': int,
                'order_name': str
            }
        """
        # ── Validar permisos ──
        if not self._check_permissions():
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Llamar al servicio ──
        sales_service = self._get_sales_service()
        resultado = sales_service.validar_entrega_venta(order_id)

        return resultado
