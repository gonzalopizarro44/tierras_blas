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
from datetime import datetime


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
        API: Obtiene lista paginada de productos con stock bajo (<10 unidades).
        
        SEGURIDAD:
        - Requiere usuario autenticado + grupo administrador
        - Valida parámetros de entrada
        - Manejo robusto de excepciones
        
        BUENAS PRÁCTICAS ODOO 19:
        - Logging detallado para auditoría
        - Validación de tipos de datos
        - Respuestas consistentes en formato JSON
        
        Parámetros GET/POST:
        - page (int, default=1): Número de página
        - limit (int, default=10, max=50): Registros por página
        
        Returns:
            json: {total, items, page, limit, total_pages, timestamp}
            items contiene: id, nombre, stock, sku, categoria, ubicacion
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        # 1. VALIDACIÓN DE SEGURIDAD
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            _logger.warning(f"[PANEL] Acceso denegado a /panel/api/productos-bajo-stock por usuario {request.env.user.name}")
            return {'error': 'Acceso denegado. Requiere permisos de administrador'}
        
        try:
            # 2. VALIDACIÓN Y SANITIZACIÓN DE PARÁMETROS
            page = int(kwargs.get('page', 1))
            limit = int(kwargs.get('limit', 10))
            
            # Validar rangos
            if page < 1:
                page = 1
            if limit < 1 or limit > 50:  # Máximo 50 items por página para evitar overhead
                limit = 10
            
            _logger.info(f"[PANEL] Solicitud: productos-bajo-stock - page={page}, limit={limit}")
            
            # 3. OBTENER DATOS DEL SERVICIO
            panel_service = request.env['panel.service']
            result = panel_service.obtener_productos_bajo_stock(page=page, limit=limit)
            
            # 4. ENRIQUECER RESPUESTA CON METADATOS
            result['timestamp'] = datetime.now().isoformat()
            result['success'] = True
            
            _logger.info(f"[PANEL] productos-bajo-stock exitoso: {result['total']} total, página {page} con {len(result['items'])} items")
            
            return request.make_response(
                json.dumps(result, default=str),
                headers=[('Content-Type', 'application/json')]
            )
            
        except ValueError as e:
            _logger.error(f"[PANEL] Error de validación en /productos-bajo-stock: {str(e)}")
            return {
                'error': 'Parámetros inválidos',
                'detalle': str(e),
                'success': False
            }
        except Exception as e:
            _logger.exception(f"[PANEL] Error inesperado en /productos-bajo-stock: {str(e)}")
            return {
                'error': 'Error al procesar solicitud',
                'detalle': str(e) if request.env.user.has_group('permisos_usuarios.group_administrador') else 'Error interno',
                'success': False
            }

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

    @http.route('/panel/api/debug/sin-stock', type='http', auth='user', website=True)
    def api_debug_sin_stock(self, **kwargs):
        """
        DEBUG: Analiza diferentes formas de buscar productos sin stock
        para identificar por qué solo se encuentra 1 producto.
        """
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'error': 'Acceso denegado'}
        
        Product = request.env['product.product'].sudo()
        StockQuant = request.env['stock.quant'].sudo()
        
        # Análisis 1: Búsqueda por qty_available
        sin_stock_qty = Product.search(
            [('active', '=', True), ('qty_available', '<=', 0)],
            order='name ASC'
        )
        
        # Análisis 2: Búsqueda por qty_available = 0 exacto
        sin_stock_qty_zero = Product.search(
            [('active', '=', True), ('qty_available', '=', 0)],
            order='name ASC'
        )
        
        # Análisis 3: Todos los productos activos y sus stocks
        todos_productos = Product.search(
            [('active', '=', True)],
            order='name ASC'
        )
        
        productos_con_stock_zero = []
        productos_con_stock_negativo = []
        
        for prod in todos_productos:
            if prod.qty_available == 0:
                productos_con_stock_zero.append({
                    'id': prod.id,
                    'nombre': prod.name,
                    'qty_available': prod.qty_available,
                })
            elif prod.qty_available < 0:
                productos_con_stock_negativo.append({
                    'id': prod.id,
                    'nombre': prod.name,
                    'qty_available': prod.qty_available,
                })
        
        # Análisis 4: Búsqueda en stock.quant (inventario)
        quants_sin_stock = StockQuant.search(
            [('quantity', '=', 0)],
        )
        productos_unicos_quant = list(set([q.product_id.id for q in quants_sin_stock]))
        
        # Análisis 5: Productos con stock en ubicaciones
        quants_all = StockQuant.search([])
        productos_stock_data = {}
        for quant in quants_all:
            prod_id = quant.product_id.id
            if prod_id not in productos_stock_data:
                productos_stock_data[prod_id] = {
                    'nombre': quant.product_id.name,
                    'ubicaciones': []
                }
            productos_stock_data[prod_id]['ubicaciones'].append({
                'ubicacion': quant.location_id.name,
                'cantidad': quant.quantity
            })
        
        # Encontrar productos cuya suma de stock en todas ubicaciones = 0
        productos_sin_stock_por_ubicacion = []
        for prod_id, data in productos_stock_data.items():
            total_stock = sum([u['cantidad'] for u in data['ubicaciones']])
            if total_stock <= 0:
                productos_sin_stock_por_ubicacion.append({
                    'id': prod_id,
                    'nombre': data['nombre'],
                    'stock_total': total_stock,
                    'ubicaciones': data['ubicaciones']
                })
        
        return request.make_response(
            json.dumps({
                'resumen': {
                    'total_productos_activos': len(todos_productos),
                    'búsqueda_qty_available_lte_0': len(sin_stock_qty),
                    'búsqueda_qty_available_eq_0': len(sin_stock_qty_zero),
                    'productos_con_qty_0_iterando': len(productos_con_stock_zero),
                    'productos_con_qty_negativo': len(productos_con_stock_negativo),
                    'quants_con_quantity_0': len(quants_sin_stock),
                    'productos_unicos_en_quants_0': len(productos_unicos_quant),
                    'productos_sin_stock_por_suma_ubicaciones': len(productos_sin_stock_por_ubicacion),
                },
                'productos_con_qty_0': [{'id': p['id'], 'nombre': p['nombre']} for p in productos_con_stock_zero],
                'productos_sin_stock_suma_ubicaciones': productos_sin_stock_por_ubicacion[:20],  # Primeros 20
                'debug': 'Se están analizando múltiples formas de buscar. La correcta debe retornar 12 productos.'
            }),
            headers=[('Content-Type', 'application/json')]
        )
