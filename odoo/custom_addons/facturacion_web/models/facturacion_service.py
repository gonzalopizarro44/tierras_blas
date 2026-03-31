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
    def crear_factura_desde_orden(self, orden_id, tipo_orden):
        """
        Crea una factura a partir de una orden de venta o compra.
        
        Parámetros:
        - orden_id: ID de sale.order o purchase.order
        - tipo_orden: 'venta' o 'compra'
        
        Returns:
            dict: {
                'success': bool,
                'factura_id': int,
                'numero_factura': str,
                'message': str,
                'url': str
            }
        """
        try:
            if tipo_orden == 'venta':
                orden = self.env['sale.order'].sudo().browse(orden_id)
                if not orden.exists():
                    return {
                        'success': False,
                        'message': 'Orden de venta no encontrada'
                    }
                
                # Crear factura desde orden de venta
                facturas = orden._create_invoices()
                if facturas:
                    factura = facturas[0]
                    factura.action_post()  # Publicar factura
                    return {
                        'success': True,
                        'factura_id': factura.id,
                        'numero_factura': factura.name,
                        'message': f'Factura {factura.name} creada exitosamente',
                        'url': f'/facturacion?id={factura.id}'
                    }
                else:
                    return {
                        'success': False,
                        'message': 'No se pudo crear la factura'
                    }
            
            elif tipo_orden == 'compra':
                orden = self.env['purchase.order'].sudo().browse(orden_id)
                if not orden.exists():
                    return {
                        'success': False,
                        'message': 'Orden de compra no encontrada'
                    }
                
                # Crear factura desde orden de compra
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
                else:
                    return {
                        'success': False,
                        'message': 'No se pudo crear la factura'
                    }
            
            else:
                return {
                    'success': False,
                    'message': 'Tipo de orden inválido'
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear factura: {str(e)}'
            }

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
