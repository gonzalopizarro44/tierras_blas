# -*- coding: utf-8 -*-
"""
==============================================================================
SERVICIO DE FACTURACIÓN - Facturación Service
==============================================================================

Centraliza TODA la lógica de negocio del módulo facturacion_web:
- Filtros avanzados para facturas de ventas y compras
- Obtención de facturas (account.move)
- Gestión de estados
- Incremento y decremento de inventario

Este modelo es ABSTRACTO y no genera tablas en BD.
Se instancia desde los controllers para acceder a los métodos de negocio.

Uso:
    facturacion_service = self.env['facturacion.service']
    domain = facturacion_service.construir_domain_filtros(kwargs)
    facturas = facturacion_service.obtener_facturas(domain)

==============================================================================
"""

from odoo import models, api
from datetime import datetime, timedelta


class FacturacionService(models.AbstractModel):
    """Servicio centralizado de lógica de negocio para facturacion_web"""
    
    _name = 'facturacion.service'
    _description = 'Servicio de Facturación Web'

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 1: FILTROS AVANZADOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def construir_domain_filtros(self, kwargs):
        """
        Construye un domain (filtro ORM) basado en parámetros GET.
        
        Soporta:
        - numero_factura: búsqueda por nombre en account.move.name (ilike)
        - socio: búsqueda por nombre en partner_id (ilike)
        - tipo: 'ventas' (customer invoices) o 'compras' (vendor bills)
        - estado: 'draft', 'posted', 'cancel'
        - fecha_desde / fecha_hasta: rango de invoice_date
        - monto_min / monto_max: rango de amount_total
        
        Args:
            kwargs (dict): Parámetros GET del request
        
        Returns:
            list: Domain Odoo para search()
        """
        domain = [
            ('move_type', 'in', ['out_invoice', 'in_invoice'])  # Solo facturas
        ]

        # ── Filtro: Tipo de factura (ventas o compras) ──
        tipo = kwargs.get('tipo', '').strip()
        if tipo == 'ventas':
            domain.append(('move_type', '=', 'out_invoice'))
        elif tipo == 'compras':
            domain.append(('move_type', '=', 'in_invoice'))

        # ── Filtro: Número de factura ──
        numero_factura = kwargs.get('numero_factura', '').strip()
        if numero_factura:
            domain.append(('name', 'ilike', numero_factura))

        # ── Filtro: Socio (cliente/proveedor) ──
        socio = kwargs.get('socio', '').strip()
        if socio:
            domain.append(('partner_id.name', 'ilike', socio))

        # ── Filtro: Rango de fechas (fecha_desde) ──
        fecha_desde = kwargs.get('fecha_desde', '').strip()
        if fecha_desde:
            try:
                dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
                domain.append(('invoice_date', '>=', dt.date()))
            except ValueError:
                pass

        # ── Filtro: Rango de fechas (fecha_hasta) ──
        fecha_hasta = kwargs.get('fecha_hasta', '').strip()
        if fecha_hasta:
            try:
                dt = datetime.strptime(fecha_hasta, '%Y-%m-%d')
                fecha_fin = dt.date() + timedelta(days=1)
                domain.append(('invoice_date', '<', fecha_fin))
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

        # ── Filtro: Estado ──
        estado = kwargs.get('estado', '').strip()
        if estado in ('draft', 'posted', 'cancel'):
            domain.append(('state', '=', estado))

        return domain

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 2: OBTENCIÓN DE FACTURAS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def obtener_facturas(self, domain):
        """
        Obtiene facturas según domain especificado.
        
        Args:
            domain (list): Domain Odoo para search()
        
        Returns:
            list: Facturas (account.move)
        """
        return self.env['account.move'].sudo().search(
            domain,
            order='invoice_date desc, id desc'
        )

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 3: OBTENCIÓN DE DATOS PARA LA UI
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def obtener_socios_para_filtro(self):
        """
        Obtiene lista de clientes y proveedores para filtro.
        
        Returns:
            list: Partners ordenados por nombre
        """
        return self.env['res.partner'].sudo().search(
            [('is_company', '=', True)],
            order='name asc',
            limit=100
        )

    @api.model
    def obtener_tipos_factura(self):
        """
        Obtiene tipos de factura disponibles.
        
        Returns:
            list: Tuplas (valor, etiqueta)
        """
        return [
            ('', 'Ambas'),
            ('ventas', 'Facturas de Ventas'),
            ('compras', 'Facturas de Compras'),
        ]

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 4: GENERACIÓN DE FACTURAS DESDE WEB
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def obtener_detalle_orden_venta(self, orden_id):
        """
        Obtiene los detalles completos de una orden de venta para el formulario.
        """
        orden = self.env['sale.order'].sudo().browse(orden_id)
        if not orden.exists():
            return {'success': False, 'message': 'Orden no encontrada'}
        
        partner = orden.partner_id
        lineas = []
        for line in orden.order_line:
            if not line.display_type: # Solo líneas de producto
                lineas.append({
                    'product_id': line.product_id.id,
                    'name': line.product_id.name,
                    'quantity': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'subtotal': line.price_subtotal,
                })

        return {
            'success': True,
            'orden': {
                'id': orden.id,
                'name': orden.name,
                'amount_total': orden.amount_total,
            },
            'partner': {
                'id': partner.id,
                'name': partner.name,
                'vat': partner.vat or '',
                'afip_type_id': partner.l10n_ar_afip_responsibility_type_id.id,
            },
            'lineas': lineas
        }

    @api.model
    def obtener_posiciones_fiscales(self):
        """
        Obtiene las posiciones fiscales (AFIP Responsibility Types) de Argentina.
        """
        posiciones = self.env['l10n_ar.afip.responsibility.type'].sudo().search([])
        return [{'id': p.id, 'name': p.name, 'code': p.code} for p in posiciones]

    @api.model
    def determinar_tipo_documento(self, posicion_fiscal_receptor_id):
        """
        Determina el tipo de documento (Factura A, B, C) de forma ultra-robusta.
        """
        if not posicion_fiscal_receptor_id:
            return None
            
        try:
            posicion = self.env['l10n_ar.afip.responsibility.type'].sudo().browse(int(posicion_fiscal_receptor_id))
            if not posicion.exists():
                return None
                
            codigo_afip_receptor = str(posicion.code)
            
            # Definir códigos y letras posibles
            # Factura A: Código 1 o 01, Letra A
            # Factura B: Código 6 o 06, Letra B
            if codigo_afip_receptor in ['1', '01']:
                target_codes = ['1', '01']
                target_letter = 'A'
            else:
                target_codes = ['6', '06']
                target_letter = 'B'
            
            # Intento 1: Por código y país
            doc_type = self.env['l10n_latam.document.type'].sudo().search([
                ('code', 'in', target_codes),
                ('country_id.code', '=', 'AR')
            ], limit=1)
            
            # Intento 2: Por letra (campo específico de l10n_ar)
            if not doc_type and hasattr(self.env['l10n_latam.document.type'], 'l10n_ar_letter'):
                doc_type = self.env['l10n_latam.document.type'].sudo().search([
                    ('l10n_ar_letter', '=', target_letter),
                    ('country_id.code', '=', 'AR')
                ], limit=1)

            # Intento 3: Búsqueda por nombre con país
            if not doc_type:
                doc_type = self.env['l10n_latam.document.type'].sudo().search([
                    ('name', 'ilike', f'Factura {target_letter}%'),
                    ('country_id.code', '=', 'AR')
                ], limit=1)

            # Intento 4: Por código sin país
            if not doc_type:
                doc_type = self.env['l10n_latam.document.type'].sudo().search([
                    ('code', 'in', target_codes)
                ], limit=1)

            # Intento 5: Por letra sin país
            if not doc_type and hasattr(self.env['l10n_latam.document.type'], 'l10n_ar_letter'):
                doc_type = self.env['l10n_latam.document.type'].sudo().search([
                    ('l10n_ar_letter', '=', target_letter)
                ], limit=1)

            if doc_type:
                return {
                    'id': doc_type.id,
                    'name': doc_type.name,
                    'code': doc_type.code
                }
            
            # Intento desesperado: buscar cualquier cosa que se llame Factura A o B
            if not doc_type:
                doc_type = self.env['l10n_latam.document.type'].sudo().search([
                    ('name', 'ilike', f'Factura {target_letter}%')
                ], limit=1)

            if doc_type:
                return {
                    'id': doc_type.id,
                    'name': doc_type.name,
                    'code': doc_type.code
                }
            
            # DIAGNÓSTICO: Si todo falla, vamos a ver qué hay en la base de datos
            # Buscamos los primeros 5 tipos de documentos argentinos o generales
            all_types = self.env['l10n_latam.document.type'].sudo().search([], limit=5)
            names = " | ".join([f"{t.name}[{t.code}]" for t in all_types])
            
            return {
                'id': None,
                'name': f"ERROR_DIAG: Disp: {names or 'VACÍO'}",
                'code': 'ERR'
            }
        except Exception as e:
            return {'id': None, 'name': f"EXCEP: {str(e)}", 'code': 'ERR'}

    @api.model
    def crear_factura_manual(self, data):
        """
        Crea una factura account.move manualmente con datos personalizados.
        
        Parámetros (data):
        - orden_id: ID de sale.order
        - partner_data: {id, name, vat, afip_type_id}
        - lineas: [{product_id, quantity, price_unit}]
        - document_type_id: ID de l10n_latam.document.type
        """
        try:
            orden_id = data.get('orden_id')
            partner_data = data.get('partner_data', {})
            lineas_data = data.get('lineas', [])
            document_type_id = data.get('document_type_id')

            orden = self.env['sale.order'].sudo().browse(orden_id)
            
            # Preparar valores del movimiento
            move_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner_data.get('id'),
                'l10n_latam_document_type_id': document_type_id,
                'invoice_origin': orden.name if orden.exists() else '',
                'invoice_line_ids': [],
            }
            
            # Agregar líneas de factura
            for line in lineas_data:
                move_vals['invoice_line_ids'].append((0, 0, {
                    'product_id': int(line.get('product_id')),
                    'quantity': float(line.get('quantity', 0)),
                    'price_unit': float(line.get('price_unit', 0)),
                }))
            
            # Crear la factura con el contexto de tipo de documento
            factura = self.env['account.move'].sudo().with_context(
                default_l10n_latam_document_type_id=document_type_id
            ).create(move_vals)
            
            # Publicar factura
            factura.action_post()
            
            # Vincular con la orden de venta si existe
            if orden.exists():
                orden.invoice_ids |= factura
            
            return {
                'success': True,
                'factura_id': factura.id,
                'numero_factura': factura.name,
                'message': f'Factura {factura.name} creada exitosamente',
                'url': f'/facturacion?id={factura.id}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear factura manual: {str(e)}'
            }

    @api.model
    def crear_factura_desde_orden(self, orden_id, tipo_orden):
        """
        Método deprecado o simplificado. Ahora redirige al flujo manual 
        si es necesario, pero mantenemos la firma por compatibilidad si algo falla.
        """
        # Por ahora lo dejamos igual para no romper nada, pero la UI usará crear_factura_manual
        try:
            if tipo_orden == 'venta':
                orden = self.env['sale.order'].sudo().browse(orden_id)
                facturas = orden._create_invoices()
                if facturas:
                    factura = facturas[0]
                    factura.action_post()
                    return {
                        'success': True,
                        'factura_id': factura.id,
                        'numero_factura': factura.name,
                        'message': f'Factura {factura.name} creada exitosamente',
                        'url': f'/facturacion?id={factura.id}'
                    }
            return {'success': False, 'message': 'Use el nuevo flujo manual'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 5: OBTENCIÓN DE DATOS PARA FORMULARIO
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def obtener_ordenes_venta_sin_factura(self):
        """
        Obtiene órdenes de venta que aún no tienen factura.
        
        Returns:
            list: sale.order sin factura relacionada
        """
        return self.env['sale.order'].sudo().search(
            [('state', '=', 'sale'), ('invoice_status', '!=', 'invoiced')],
            order='date_order desc'
        )

    @api.model
    def obtener_ordenes_compra_sin_factura(self):
        """
        Obtiene órdenes de compra que aún no tienen factura.
        
        Returns:
            list: purchase.order sin factura relacionada
        """
        return self.env['purchase.order'].sudo().search(
            [('state', '=', 'purchase'), ('invoice_status', '!=', 'invoiced')],
            order='date_order desc'
        )

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 6: MAPEO DE ESTADOS PARA UI
    # ═════════════════════════════════════════════════════════════════════════

    @staticmethod
    def mapear_estado_badge(estado):
        """
        Mapea estados de facturas a badges de UI.
        
        Args:
            estado (str): Estado de factura (draft, posted, cancel)
        
        Returns:
            dict: {clase, icono, texto}
        """
        mapa = {
            'draft': {'clase': 'badge-draft', 'icono': '📋', 'texto': 'Borrador'},
            'posted': {'clase': 'badge-posted', 'icono': '✓', 'texto': 'Publicada'},
            'cancel': {'clase': 'badge-cancel', 'icono': '✕', 'texto': 'Cancelada'},
        }
        return mapa.get(estado, {'clase': 'badge-default', 'icono': '?', 'texto': estado})
