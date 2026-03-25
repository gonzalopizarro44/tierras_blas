# -*- coding: utf-8 -*-
"""
==============================================================================
CONTROLLER: PANEL WEB DE COMPRAS - Módulo compras_web para Odoo 19
==============================================================================

REFACTORIZADO: Controllers LIVIANOS que solo manejan HTTP

Rutas:
- GET /compras: Listado de compras con filtros avanzados (HTTP)
- GET /compras/nueva: Formulario para nueva compra (HTTP)
- POST /compras/crear_proveedor: Crear proveedor rápidamente (JSON-RPC)
- POST /compras/crear: Crear nueva orden de compra (JSON-RPC)
- POST /compras/confirmar: Confirmar compra e incrementar stock (JSON-RPC)
- POST /compras/cancelar: Cancelar compra (JSON-RPC)

LÓGICA DE NEGOCIO:
→ Toda la lógica está en models/compras_service.py
→ Controllers solo parsean requests y llaman al servicio

FLUJO DE STOCK (COMPRAS):
1. Usuario crea orden → purchase.order en estado DRAFT (sin stock)
2. Usuario confirma → service.confirm_purchase_order() → button_confirm()
3. Stock se INCREMENTA en ubicación WH/Stock automáticamente

==============================================================================
"""

from odoo import http
from odoo.http import request


class ComprasController(http.Controller):
    """Controller para gestión web de compras - REFACTORIZADO a service layer"""

    # ═════════════════════════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES: Validación y obtención de servicios
    # ═════════════════════════════════════════════════════════════════════════

    def _validar_permisos(self):
        """
        Valida que el usuario tenga permisos de administrador.
        
        Returns:
            bool: True si tiene permisos, False si no
        """
        return request.env.user.has_group('permisos_usuarios.group_administrador')

    def _obtener_servicio_compras(self):
        """
        Obtiene la instancia del servicio de compras.
        
        Returns:
            compras.service: Instancia del servicio
        """
        return request.env['compras.service']

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA GET: /compras - Listar todas las compras con filtros
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/compras', type='http', auth='user', website=True)
    def listado_compras(self, **kwargs):
        """
        Página principal: Dashboard de compras con filtros avanzados.
        
        Params (GET):
        - proveedor: Buscar por nombre de proveedor
        - producto: Buscar por nombre de producto
        - fecha_desde: Fecha inicial (YYYY-MM-DD)
        - fecha_hasta: Fecha final (YYYY-MM-DD)
        - monto_min / monto_max: Rango de montos
        - categoria: ID de categoría de producto
        - estado: 'draft', 'purchase' o 'cancel'
        
        Returns:
            http.Response: Página HTML renderizada
        """
        # ── Validar permisos ──
        if not self._validar_permisos():
            return request.redirect('/')

        # ── Obtener servicio ──
        compras_service = self._obtener_servicio_compras()

        # ── Construir filtros usando el servicio ──
        domain = compras_service.construir_domain_filtros(kwargs)

        # ── Buscar compras ──
        compras = request.env['purchase.order'].sudo().search(
            domain,
            order='date_order desc, id desc'
        )

        # ── Obtener datos para la UI ──
        categorias = request.env['product.category'].sudo().search(
            [],
            order='name asc'
        )
        proveedores = request.env['res.partner'].sudo().search(
            [('supplier_rank', '>', 0)],
            order='name asc',
            limit=50
        )

        # ── Contexto para la vista ──
        ctx = {
            'compras': compras,
            'categorias': categorias,
            'proveedores': proveedores,
            'filtros': kwargs,  # Repoblar filtros en la UI
            'total_compras': len(compras),
        }

        return request.render('compras_web.compras_template', ctx)

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA GET: /compras/nueva - Formulario de nueva compra
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/compras/nueva', type='http', auth='user', website=True)
    def formulario_nueva_compra(self, **kwargs):
        """
        Formulario para crear una nueva orden de compra.
        
        Carga:
        - Proveedores (res.partner) con supplier_rank > 0
        - Productos (product.product) con purchase_ok = True
        
        Returns:
            http.Response: Página HTML del formulario
        """
        # ── Validar permisos ──
        if not self._validar_permisos():
            return request.redirect('/')

        # ── Obtener datos necesarios ──
        proveedores = request.env['res.partner'].sudo().search(
            [('supplier_rank', '>', 0)],
            order='name asc'
        )
        productos = request.env['product.product'].sudo().search(
            [('purchase_ok', '=', True)],
            order='name asc'
        )

        ctx = {
            'proveedores': proveedores,
            'productos': productos,
        }

        return request.render('compras_web.nueva_compra_template', ctx)

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /compras/crear_proveedor - Crear proveedor rápidamente
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/compras/crear_proveedor', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def crear_proveedor_rapido(self, nombre):
        """
        Crea un proveedor rápidamente sin abandonar el formulario.
        
        Usa: compras_service.crear_proveedor_rapido()
        
        Parámetros (JSON-RPC):
        - nombre: Nombre del proveedor (obligatorio)
        
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
        if not self._validar_permisos():
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Llamar al servicio ──
        compras_service = self._obtener_servicio_compras()
        resultado = compras_service.crear_proveedor_rapido(nombre)

        return resultado

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /compras/crear - Crear nueva orden de compra
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/compras/crear', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def crear_compra(self, proveedor_id, lineas):
        """
        Crea una nueva orden de compra con líneas de productos.
        
        Usa: compras_service.crear_orden_compra()
        
        IMPORTANTE: La compra se crea en estado DRAFT sin modificar stock.
        El stock solo se incrementa en la confirmación.
        
        FLUJO:
        1. Valida datos
        2. Crea purchase.order
        3. Crea purchase.order.line para cada producto
        
        Parámetros (JSON-RPC):
        - proveedor_id: ID del proveedor (res.partner)
        - lineas: Lista de dicts [{'product_id': int, 'cantidad': float, 'precio_unitario': float}, ...]
        
        Returns:
            dict: {
                'success': bool,
                'orden_id': int,
                'nombre_orden': str,
                'message': str,
                'url': str
            }
        """
        # ── Validar permisos ──
        if not self._validar_permisos():
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Llamar al servicio ──
        compras_service = self._obtener_servicio_compras()
        resultado = compras_service.crear_orden_compra(proveedor_id, lineas)

        return resultado

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /compras/confirmar - Confirmar compra e incrementar stock
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/compras/confirmar', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def confirmar_compra(self, orden_id):
        """
        Confirma una orden de compra e INCREMENTA STOCK.
        
        Usa: compras_service.confirmar_orden_compra()
        
        PROCESO:
        1. Ejecuta button_confirm() de Odoo (DRAFT → PURCHASE)
        2. Incrementa stock.quant en ubicación WH/Stock
        3. Evita confirmaciones duplicadas
        
        Parámetros (JSON-RPC):
        - orden_id: ID de purchase.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        # ── Validar permisos ──
        if not self._validar_permisos():
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Llamar al servicio ──
        compras_service = self._obtener_servicio_compras()
        resultado = compras_service.confirmar_orden_compra(orden_id)

        return resultado

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /compras/cancelar - Cancelar una compra
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/compras/cancelar', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def cancelar_compra(self, orden_id):
        """
        Cancela una orden de compra.
        
        Usa: compras_service.cancelar_orden_compra()
        
        IMPORTANTE: NO modifica stock bajo ninguna circunstancia.
        - Si la orden NO fue confirmada: No hay stock que revertir
        - Si ya fue confirmada: El usuario es responsable de reversión manual
        
        Parámetros (JSON-RPC):
        - orden_id: ID de purchase.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        # ── Validar permisos ──
        if not self._validar_permisos():
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Llamar al servicio ──
        compras_service = self._obtener_servicio_compras()
        resultado = compras_service.cancelar_orden_compra(orden_id)

        return resultado
