"""
==============================================================================
CONTROLADOR DE PANEL - Panel Controller
==============================================================================

Router HTTP para el dashboard administrativo panel_web.

Responsabilidades:
- Validar seguridad (permisos de acceso)
- Extraer parámetros de request
- Delegar toda la lógica de negocio a panel.service
- Renderizar template con datos calculados

Rutas:
- GET /panel → Dashboard administrativo general

==============================================================================
"""

from odoo import http
from odoo.http import request
import json


class PanelController(http.Controller):

    @http.route('/panel', type='http', auth='user', website=True)
    def panel_administrativo(self, **kwargs):
        """
        Dashboard administrativo central con métricas, indicadores, alertas y gráficos.
        
        Flujo:
        1. Validar seguridad (grupo administrador)
        2. Extraer parámetros de request (fechas, categoría)
        3. Delegar al panel_service para calcular datos
        4. Renderizar template con contexto
        
        Args:
            **kwargs: Parámetros GET (fecha_desde, fecha_hasta, categoria)
        
        Returns:
            html: Template panel_template.html renderizado
        """
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 1: VALIDACIÓN DE SEGURIDAD
        # ═══════════════════════════════════════════════════════════════════
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return request.redirect('/')
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 2: OBTENER INSTANCIA DEL SERVICE
        # ═══════════════════════════════════════════════════════════════════
        panel_service = request.env['panel.service']
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 3: EXTRAER PARÁMETROS DE REQUEST Y APLICAR DEFAULTS
        # ═══════════════════════════════════════════════════════════════════
        fecha_desde, fecha_hasta = panel_service.obtener_fecha_por_defecto()
        fecha_desde = kwargs.get('fecha_desde', fecha_desde)
        fecha_hasta = kwargs.get('fecha_hasta', fecha_hasta)
        categoria = kwargs.get('categoria', '')
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 4: DELEGAR AL SERVICE Y OBTENER DATOS
        # ═══════════════════════════════════════════════════════════════════
        metricas = panel_service.obtener_metricas_generales(
            fecha_desde, fecha_hasta, categoria
        )
        indicadores = panel_service.obtener_indicadores_detallados(
            fecha_desde, fecha_hasta
        )
        alertas = panel_service.obtener_alertas()
        graficos = panel_service.obtener_datos_graficos(
            fecha_desde, fecha_hasta, categoria
        )
        
        # Obtener catálogos para los filtros
        categorias = request.env['product.category'].sudo().search([])
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 5: CONSTRUIR CONTEXTO PARA EL TEMPLATE
        # ═══════════════════════════════════════════════════════════════════
        contexto = {
            'metricas': metricas,
            'indicadores': indicadores,
            'alertas': alertas,
            'graficos_json': json.dumps(graficos),
            'categorias': categorias,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'categoria_id': categoria,
        }
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 6: RENDERIZAR Y RETORNAR RESPUESTA
        # ═══════════════════════════════════════════════════════════════════
        return request.render(
            'panel_web.panel_template',
            contexto
        )

    @http.route('/panel/api/productos-sin-stock', type='http', auth='user', website=True)
    def api_productos_sin_stock(self, **kwargs):
        """
        API: Obtiene lista paginada de productos sin stock.
        
        Parámetros GET/POST:
        - page (int, default=1): Número de página
        - limit (int, default=10): Registros por página
        
        Returns:
            json: {total, items, page, limit, total_pages}
        """
        # Validación de seguridad
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'error': 'Acceso denegado'}
        
        panel_service = request.env['panel.service']
        page = int(kwargs.get('page', 1))
        limit = int(kwargs.get('limit', 10))
        
        result = panel_service.obtener_productos_sin_stock(page=page, limit=limit)
        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/panel/api/productos-bajo-stock', type='http', auth='user', website=True)
    def api_productos_bajo_stock(self, **kwargs):
        """
        API: Obtiene lista paginada de productos con stock bajo.
        
        Parámetros GET/POST:
        - page (int, default=1): Número de página
        - limit (int, default=10): Registros por página
        
        Returns:
            json: {total, items, page, limit, total_pages}
        """
        # Validación de seguridad
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'error': 'Acceso denegado'}
        
        panel_service = request.env['panel.service']
        page = int(kwargs.get('page', 1))
        limit = int(kwargs.get('limit', 10))
        
        result = panel_service.obtener_productos_bajo_stock(page=page, limit=limit)
        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/panel/api/detalles-ventas', type='http', auth='user', website=True)
    def api_detalles_ventas(self, **kwargs):
        """
        API: Obtiene lista paginada de ventas confirmadas.
        
        Parámetros GET/POST:
        - fecha_desde (str): Fecha inicio en formato ISO
        - fecha_hasta (str): Fecha fin en formato ISO
        - page (int, default=1): Número de página
        - limit (int, default=10): Registros por página
        
        Returns:
            json: {total, items, page, limit, total_pages}
        """
        # Validación de seguridad
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'error': 'Acceso denegado'}
        
        panel_service = request.env['panel.service']
        
        # Obtener fechas (usa defaults si no se proporciona)
        fecha_desde, fecha_hasta = panel_service.obtener_fecha_por_defecto()
        fecha_desde = kwargs.get('fecha_desde', fecha_desde)
        fecha_hasta = kwargs.get('fecha_hasta', fecha_hasta)
        page = int(kwargs.get('page', 1))
        limit = int(kwargs.get('limit', 10))
        
        result = panel_service.obtener_detalles_ventas(
            fecha_desde, fecha_hasta, page=page, limit=limit
        )
        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/panel/api/detalles-compras', type='http', auth='user', website=True)
    def api_detalles_compras(self, **kwargs):
        """
        API: Obtiene lista paginada de compras confirmadas.
        
        Parámetros GET/POST:
        - fecha_desde (str): Fecha inicio en formato ISO
        - fecha_hasta (str): Fecha fin en formato ISO
        - page (int, default=1): Número de página
        - limit (int, default=10): Registros por página
        
        Returns:
            json: {total, items, page, limit, total_pages}
        """
        # Validación de seguridad
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'error': 'Acceso denegado'}
        
        panel_service = request.env['panel.service']
        
        # Obtener fechas (usa defaults si no se proporciona)
        fecha_desde, fecha_hasta = panel_service.obtener_fecha_por_defecto()
        fecha_desde = kwargs.get('fecha_desde', fecha_desde)
        fecha_hasta = kwargs.get('fecha_hasta', fecha_hasta)
        page = int(kwargs.get('page', 1))
        limit = int(kwargs.get('limit', 10))
        
        result = panel_service.obtener_detalles_compras(
            fecha_desde, fecha_hasta, page=page, limit=limit
        )
        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/panel/api/productos-activos', type='http', auth='user', website=True)
    def api_productos_activos(self, **kwargs):
        """
        API: Obtiene lista paginada de productos activos.
        """
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'error': 'Acceso denegado'}
        
        panel_service = request.env['panel.service']
        page = int(kwargs.get('page', 1))
        limit = int(kwargs.get('limit', 10))
        
        result = panel_service.obtener_productos_activos(page=page, limit=limit)
        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
