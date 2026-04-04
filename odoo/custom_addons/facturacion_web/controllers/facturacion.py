# -*- coding: utf-8 -*-
"""
==============================================================================
CONTROLLER: PANEL WEB DE FACTURACIÓN - Módulo facturacion_web para Odoo 19
==============================================================================

REFACTORIZADO: Controllers LIVIANOS que solo manejan HTTP

Rutas:
- GET /facturacion: Listado de facturas con filtros avanzados (HTTP)
- GET /facturacion/nueva: Formulario para crear nueva factura (HTTP)
- GET /facturacion/pdf/<int:factura_id>: Descarga PDF (HTTP)
- POST /facturacion/crear_factura: Crear factura desde orden (JSON-RPC)
- POST /facturacion/cancelar_factura: Cancelar factura (JSON-RPC)

LÓGICA DE NEGOCIO:
→ Toda la lógica está en models/facturacion_service.py
→ Controllers solo parsean requests y llaman al servicio

TIPOS DE FACTURA:
1. Facturas de Ventas (out_invoice) - Generadas desde órdenes de venta
2. Facturas de Compras (in_invoice) - Generadas desde órdenes de compra

==============================================================================
"""

from odoo import http
from odoo.http import request
import base64


class FacturacionController(http.Controller):
    """Controller para gestión web de facturación - REFACTORIZADO a service layer"""

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

    def _obtener_servicio_facturacion(self):
        """
        Obtiene la instancia del servicio de facturación.
        
        Returns:
            facturacion.service: Instancia del servicio
        """
        return request.env['facturacion.service']

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA GET: /facturacion - Listar todas las facturas con filtros
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/facturacion', type='http', auth='user', website=True)
    def listado_facturas(self, **kwargs):
        """
        Página principal: Dashboard de facturas con filtros avanzados.
        
        Params (GET):
        - numero_factura: Buscar por número/nombre
        - socio: Buscar por nombre de cliente/proveedor
        - tipo: 'ventas' (facturas de clientes) o 'compras' (facturas de proveedores)
        - estado: 'draft', 'posted' o 'cancel'
        - fecha_desde: Fecha inicial (YYYY-MM-DD)
        - fecha_hasta: Fecha final (YYYY-MM-DD)
        - monto_min / monto_max: Rango de montos
        
        Returns:
            http.Response: Página HTML renderizada
        """
        # ── Validar permisos ──
        if not self._validar_permisos():
            return request.redirect('/')

        # ── Obtener servicio ──
        facturacion_service = self._obtener_servicio_facturacion()

        # ── Construir filtros usando el servicio ──
        domain = facturacion_service.construir_domain_filtros(kwargs)

        # ── Buscar facturas ──
        facturas = facturacion_service.obtener_facturas(domain)

        # ── Obtener datos para la UI ──
        socios = facturacion_service.obtener_socios_para_filtro()
        tipos_factura = facturacion_service.obtener_tipos_factura()

        # ── Contexto para la vista ──
        ctx = {
            'facturas': facturas,
            'socios': socios,
            'tipos_factura': tipos_factura,
            'filtros': kwargs,  # Repoblar filtros en la UI
            'total_facturas': len(facturas),
        }

        return request.render('facturacion_web.facturacion_template', ctx)

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA GET: /facturacion/nueva - Formulario de nueva factura
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/facturacion/nueva', type='http', auth='user', website=True)
    def formulario_nueva_factura(self, **kwargs):
        """
        Formulario para crear una nueva factura desde una orden.
        
        Carga:
        - Órdenes de venta sin facturar
        - Órdenes de compra sin facturar
        
        Returns:
            http.Response: Página HTML del formulario
        """
        # ── Validar permisos ──
        if not self._validar_permisos():
            return request.redirect('/')

        # ── Obtener datos necesarios ──
        facturacion_service = self._obtener_servicio_facturacion()
        ordenes_venta = facturacion_service.obtener_ordenes_venta_sin_factura()
        # Omitimos compras por solicitud del usuario
        # ordenes_compra = facturacion_service.obtener_ordenes_compra_sin_factura()
        
        # Nuevos datos para el formulario manual
        posiciones_fiscales = facturacion_service.obtener_posiciones_fiscales()

        ctx = {
            'ordenes_venta': ordenes_venta,
            'ordenes_compra': [], # Vacío por ahora
            'posiciones_fiscales': posiciones_fiscales,
        }

        return request.render('facturacion_web.nueva_factura_template', ctx)

    # ═════════════════════════════════════════════════════════════════════════
    # RUTAS JSON-RPC: Detalle de orden y tipos de documento
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/facturacion/detalle_orden', type='jsonrpc', auth='user', 
                 website=True, methods=['POST'])
    def detalle_orden(self, orden_id):
        """Obtiene detalles de una orden para pre-llenar el formulario."""
        if not self._validar_permisos():
            return {'success': False, 'message': 'No tiene permisos.'}
        
        return self._obtener_servicio_facturacion().obtener_detalle_orden_venta(orden_id)

    @http.route('/facturacion/tipos_documento', type='jsonrpc', auth='user', 
                 website=True, methods=['POST'])
    def tipos_documento(self, posicion_fiscal_receptor_id):
        """Determina el tipo de documento según la posición fiscal."""
        if not self._validar_permisos():
            return {'success': False, 'message': 'No tiene permisos.'}
        
        res = self._obtener_servicio_facturacion().determinar_tipo_documento(posicion_fiscal_receptor_id)
        return res or {'success': False, 'message': 'No se pudo determinar el tipo de documento'}

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA GET: /facturacion/pdf/<int:factura_id> - Descargar PDF
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/facturacion/pdf/<int:factura_id>', type='http', auth='user', website=True)
    def descargar_pdf_factura(self, factura_id):
        """
        Descarga el PDF de una factura.
        
        Parámetros:
        - factura_id: ID de account.move
        
        Returns:
            http.Response: PDF descargable
        """
        # ── Validar permisos ──
        if not self._validar_permisos():
            return request.redirect('/')

        # ── Obtener factura ──
        factura = request.env['account.move'].sudo().browse(factura_id)
        
        if not factura.exists():
            return request.redirect('/facturacion')

        # ── Generar y descargar PDF ──
        try:
            # Buscar el reporte qweb-pdf registrado para facturas
            reporte = request.env['ir.actions.report'].sudo().search([
                ('model', '=', 'account.move'),
                ('report_type', '=', 'qweb-pdf')
            ], limit=1)
            
            if not reporte:
                return request.redirect('/facturacion')
            
            # Renderizar PDF
            pdf_content, _ = reporte.render_qweb_pdf([factura_id])
            
            # Preparar nombre de archivo seguro
            safe_name = factura.name.replace('/', '_').replace(' ', '_')
            nombre_archivo = f"{safe_name}.pdf"
            
            return request.make_response(
                pdf_content,
                [
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'attachment; filename="{nombre_archivo}"'),
                    ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                    ('Pragma', 'no-cache'),
                    ('Expires', '0'),
                ]
            )
        except Exception as e:
            return request.redirect('/facturacion')

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /facturacion/crear_factura - Crear factura desde orden
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/facturacion/crear_factura', type='jsonrpc', auth='user', 
                 website=True, methods=['POST'])
    def crear_factura(self, **kwargs):
        """
        Crea una factura manual con los datos recibidos del formulario.
        """
        # ── Validar permisos ──
        if not self._validar_permisos():
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Llamar al servicio ──
        facturacion_service = self._obtener_servicio_facturacion()
        
        # El servicio ahora espera un diccionario con toda la data
        resultado = facturacion_service.crear_factura_manual(kwargs)

        return resultado

    # ═════════════════════════════════════════════════════════════════════════
    # RUTA POST: /facturacion/cancelar_factura - Cancelar factura
    # ═════════════════════════════════════════════════════════════════════════

    @http.route('/facturacion/cancelar_factura', type='jsonrpc', auth='user', 
                 website=True, methods=['POST'])
    def cancelar_factura(self, factura_id):
        """
        Cancela una factura.
        
        Parámetros (JSON-RPC):
        - factura_id: ID de account.move
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        # ── Validar permisos ──
        if not self._validar_permisos():
            return {'success': False, 'message': 'No tiene permisos.'}

        try:
            factura = request.env['account.move'].sudo().browse(factura_id)
            
            if not factura.exists():
                return {
                    'success': False,
                    'message': 'Factura no encontrada'
                }

            if factura.state == 'cancel':
                return {
                    'success': False,
                    'message': 'Esta factura ya está cancelada'
                }

            # Cancelar factura
            factura.button_draft()  # Volver a borrador
            factura.button_cancel()  # Cancelar

            return {
                'success': True,
                'message': f'Factura {factura.name} cancelada exitosamente'
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Error al cancelar factura: {str(e)}'
            }
