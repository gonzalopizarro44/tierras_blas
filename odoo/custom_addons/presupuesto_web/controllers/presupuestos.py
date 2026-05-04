"""
==============================================================================
CONTROLLER: PANEL WEB DE PRESUPUESTOS - Módulo presupuesto_web para Odoo 19
==============================================================================

Controllers LIVIANOS que solo manejan HTTP.

Rutas:
- GET /presupuestos: Listado de presupuestos con filtros (HTTP)
- GET /presupuestos/nuevo: Formulario para nuevo presupuesto (HTTP)
- POST /presupuestos/buscar_clientes: Buscar clientes en tiempo real (JSON-RPC)
- POST /presupuestos/crear_cliente: Crear cliente rápidamente (JSON-RPC)
- POST /presupuestos/crear: Crear nuevo presupuesto (JSON-RPC)
- POST /presupuestos/cancelar: Cancelar presupuesto (JSON-RPC)
- GET /presupuestos/<id>/pdf: Descargar PDF de cotización (HTTP)

LÓGICA DE NEGOCIO:
→ Toda la lógica está en models/presupuesto_service.py
→ Controllers solo parsean requests y llaman al servicio

==============================================================================
"""

from odoo import http
from odoo.http import request


class PresupuestosController(http.Controller):
    """Controller para gestión web de presupuestos"""

    # ═════════════════════════════════════════════════════════════════════════
    # MÉTODO AUXILIAR: Validación de permisos
    # ═════════════════════════════════════════════════════════════════════════

    def _check_permissions(self):
        """Valida que el usuario tenga permisos de administrador."""
        return request.env.user.has_group('permisos_usuarios.group_administrador')

    def _get_service(self):
        """Obtiene la instancia del servicio de presupuestos."""
        return request.env['presupuesto.service']

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA GET: /presupuestos - Listar todos los presupuestos
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/presupuestos', type='http', auth='user', website=True)
    def presupuestos_listado(self, **kwargs):
        """
        Página principal: Panel de presupuestos con filtros.
        
        Muestra cotizaciones (sale.order) creadas desde presupuesto_web.
        """
        if not self._check_permissions():
            return request.redirect('/')

        service = self._get_service()

        # Construir filtros
        domain = service.build_presupuesto_filters(kwargs)

        # Buscar presupuestos
        presupuestos = request.env['sale.order'].sudo().search(
            domain,
            order='date_order desc, id desc'
        )

        ctx = {
            'presupuestos': presupuestos,
            'filtros': kwargs,
            'total_presupuestos': len(presupuestos),
        }

        return request.render('presupuesto_web.presupuestos_template', ctx)

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA GET: /presupuestos/nuevo - Formulario de nuevo presupuesto
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/presupuestos/nuevo', type='http', auth='user', website=True)
    def presupuestos_nuevo_formulario(self, **kwargs):
        """
        Formulario para crear un nuevo presupuesto.
        
        Carga productos con sus precios (editables en el formulario).
        Clientes se cargan dinámicamente via AJAX.
        """
        if not self._check_permissions():
            return request.redirect('/')

        # Obtener productos disponibles para venta
        productos = request.env['product.product'].sudo().search(
            [('sale_ok', '=', True)],
            order='name asc'
        )

        # Formatear productos con información de precio, stock y tipo
        productos_formateados = []
        for p in productos:
            productos_formateados.append({
                'id': p.id,
                'name': p.name,
                'display_name': p.display_name,
                'list_price': p.list_price,
                'free_qty': p.free_qty,
                'is_service': p.product_tmpl_id.type == 'service',
            })

        ctx = {
            'productos': productos_formateados,
        }

        return request.render('presupuesto_web.presupuesto_nuevo_template', ctx)

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /presupuestos/buscar_clientes - Buscar clientes
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/presupuestos/buscar_clientes', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def buscar_clientes(self, term='', limit=30):
        """Busca clientes en tiempo real para el autocompletado."""
        if not self._check_permissions():
            return {'success': False, 'message': 'No tiene permisos.'}

        domain = [
            ('is_company', '=', False),
            ('type', '=', 'contact'),
        ]

        if term:
            term = term.strip()
            domain += [
                '|',
                ('name', 'ilike', term),
                ('vat', 'ilike', term),
            ]

        Partner = request.env['res.partner'].sudo()
        total = Partner.search_count(domain)
        clientes = Partner.search(
            domain,
            order='name asc',
            limit=int(limit)
        )

        resultado = []
        for c in clientes:
            label = c.name
            if c.vat:
                label += ' (' + c.vat + ')'
            resultado.append({
                'id': c.id,
                'name': c.name,
                'vat': c.vat or '',
                'label': label,
            })

        return {
            'success': True,
            'clientes': resultado,
            'total': total,
        }

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /presupuestos/crear_cliente - Crear cliente rápido
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/presupuestos/crear_cliente', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def crear_cliente_rapido(self, nombre, dni=None):
        """Crea un cliente rápidamente sin abandonar el formulario."""
        if not self._check_permissions():
            return {'success': False, 'message': 'No tiene permisos.'}

        service = self._get_service()
        return service.create_quick_customer(nombre, dni)

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /presupuestos/crear - Crear nuevo presupuesto
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/presupuestos/crear', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def crear_presupuesto(self, cliente_id, lineas):
        """
        Crea un nuevo presupuesto (cotización draft en Odoo).
        
        Parámetros (JSON-RPC):
        - cliente_id: ID del cliente (res.partner)
        - lineas: [{'product_id': int, 'quantity': float, 'price_unit': float}, ...]
        """
        if not self._check_permissions():
            return {'success': False, 'message': 'No tiene permisos.'}

        service = self._get_service()
        return service.create_presupuesto(
            cliente_id=cliente_id,
            lineas=lineas
        )

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /presupuestos/cancelar - Cancelar presupuesto
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/presupuestos/cancelar', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def cancelar_presupuesto(self, order_id):
        """Cancela un presupuesto existente."""
        if not self._check_permissions():
            return {'success': False, 'message': 'No tiene permisos.'}

        service = self._get_service()
        return service.cancelar_presupuesto(order_id)

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA GET: /presupuestos/<id>/pdf - Descargar PDF del presupuesto
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/presupuestos/<int:order_id>/pdf', type='http', auth='user', website=True)
    def descargar_pdf(self, order_id, **kwargs):
        """
        Genera y descarga el PDF de la cotización (reporte estándar de Odoo).
        
        Usa el reporte 'sale.action_report_saleorder' que Odoo genera
        automáticamente para sale.order.
        """
        if not self._check_permissions():
            return request.redirect('/')

        orden = request.env['sale.order'].sudo().browse(order_id)
        if not orden.exists():
            return request.redirect('/presupuestos')

        # Generar PDF usando el reporte estándar de Odoo
        pdf_content, content_type = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'sale.action_report_saleorder',
            [orden.id]
        )

        # Nombre del archivo
        filename = f"Presupuesto_{orden.name.replace('/', '_')}.pdf"

        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
            ]
        )
