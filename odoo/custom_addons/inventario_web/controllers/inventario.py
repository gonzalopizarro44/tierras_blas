"""
==============================================================================
CONTROLADOR DE INVENTARIO - Inventario Controller
==============================================================================

Controlador ligero para el panel web de inventario.

RESPONSABILIDADES:
- Recibir requests HTTP
- Validar permisos de seguridad
- Delegar lógica de negocio al inventario_service
- Renderizar respuestas

La lógica compleja está centralizada en inventario.service para:
- Mantenibilidad
- Escalabilidad
- Reutilización
- Testing

==============================================================================
"""

from odoo import http
from odoo.http import request


class InventarioController(http.Controller):
    """Controlador principal del panel web de inventario.

    Rutas:
    - GET /inventario → Página principal con filtros
    - POST /inventario/update_field → Actualización AJAX de campos
    """

    # ── Ruta principal: GET /inventario ────────────────────────────────

    @http.route('/inventario', type='http', auth='user', website=True)
    def pagina_inventario(self, **kwargs):
        """Página principal del panel de inventario.

        Flujo:
        1. Validar permisos (user debe ser administrador)
        2. Extraer y normalizar filtros desde los parámetros GET
        3. Construir domain dinámico
        4. Obtener productos
        5. Obtener categorías
        6. Renderizar template

        Args:
            **kwargs: Parámetros GET (nombre, proveedor, categoria, etc.)

        Returns:
            http.response: Página HTML renderizada o redirect a /
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return request.redirect('/')

        # ── Obtener servicio de inventario ──
        inventario_service = request.env['inventario.service']

        # ── Extraer y normalizar filtros ──
        filtros = inventario_service.extraer_filtros(kwargs)

        # ── Construir domain dinámico ──
        dominio = inventario_service.construir_domain_filtros(filtros)

        # ── Buscar productos (incluir inactivos si el filtro es 'todos') ──
        incluir_inactivos = filtros.get('f_estado') == 'todos'
        productos = inventario_service.obtener_productos(dominio, incluir_inactivos)

        # ── Obtener categorías para el select de filtro ──
        categorias = inventario_service.obtener_categorias()

        # ── Calcular total de productos encontrados ──
        total_productos = len(productos)

        # ── Renderizar template ──
        return request.render(
            'inventario_web.inventario_template',
            {
                'productos': productos,
                'categorias': categorias,
                'filtros': filtros,
                'total_productos': total_productos,
            }
        )

    # ── Ruta: POST /inventario/update_field (JSON-RPC) ────────────────────

    @http.route('/inventario/update_field', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def actualizar_campo_producto(self, product_id, field, value):
        """Actualiza un campo específico de un producto (AJAX).

        Flujo:
        1. Validar permisos
        2. Delegar a inventario_service.actualizar_campo_producto()
        3. Retornar resultado (success/error)

        Args:
            product_id (int): ID del product.product
            field (str): Nombre del campo técnico (name, categ_id, qty_available, etc.)
            value (any): Nuevo valor

        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'success': False, 'message': 'No tiene permisos para realizar esta acción.'}

        # ── Obtener servicio de inventario ──
        inventario_service = request.env['inventario.service']

        # ── Delegar al service ──
        resultado = inventario_service.actualizar_campo_producto(product_id, field, value)

        # ── Retornar resultado ──
        return resultado