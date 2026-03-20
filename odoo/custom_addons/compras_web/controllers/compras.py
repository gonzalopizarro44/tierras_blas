# -*- coding: utf-8 -*-
"""
═════════════════════════════════════════════════════════════════════════════════
CONTROLLER: PANEL WEB DE COMPRAS - Módulo compras_web para Odoo 19
═════════════════════════════════════════════════════════════════════════════════

Maneja:
- GET /compras: Listado de compras con filtros avanzados
- GET /compras/nueva: Formulario de creación
- POST /compras/crear: Crear nueva orden de compra
- POST /compras/crear_proveedor: Crear proveedor rápidamente
- POST /compras/confirmar: Confirmar compra + incrementar stock
- POST /compras/cancelar: Cancelar compra

Flujo de stock (recepción simplificada):
1. Usuario crea compra → purchase.order en estado DRAFT
2. Usuario confirma → button_confirm() + incrementar stock.quant
3. Stock se incrementa directamente en WH/Stock

═════════════════════════════════════════════════════════════════════════════════
"""

from odoo import http
from odoo.http import request
from datetime import datetime, timedelta


class ComprasController(http.Controller):

    # ═══════════════════════════════════════════════════════════════════════
    # MÉTODO AUXILIAR: Construcción dinámica de domain (FILTROS)
    # ═══════════════════════════════════════════════════════════════════════

    def _construir_domain_filtros(self, kwargs):
        """
        Construye un domain basado en parámetros GET para filtrar purchase.order.
        
        Soporta:
        - proveedor: búsqueda por nombre en partner_id
        - producto: búsqueda en order_line.product_id
        - fecha_desde / fecha_hasta: rango de date_order
        - monto_min / monto_max: rango de amount_total
        - categoria: product_id.categ_id (categorías de productos comprados)
        - estado: state (draft/purchase/cancel)
        """
        domain = []

        # Filtro: Proveedor (name)
        proveedor = kwargs.get('proveedor', '').strip()
        if proveedor:
            domain.append(('partner_id.name', 'ilike', proveedor))

        # Filtro: Producto (order_line.product_id)
        producto = kwargs.get('producto', '').strip()
        if producto:
            domain.append(('order_line.product_id.name', 'ilike', producto))

        # Filtro: Rango de fechas
        fecha_desde = kwargs.get('fecha_desde', '').strip()
        if fecha_desde:
            try:
                dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
                domain.append(('date_order', '>=', dt))
            except ValueError:
                pass

        fecha_hasta = kwargs.get('fecha_hasta', '').strip()
        if fecha_hasta:
            try:
                dt = datetime.strptime(fecha_hasta, '%Y-%m-%d')
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
        if estado in ('draft', 'purchase', 'cancel'):
            domain.append(('state', '=', estado))

        return domain

    # ═══════════════════════════════════════════════════════════════════════
    # RUTA GET: /compras - Listar todas las compras con filtros
    # ═══════════════════════════════════════════════════════════════════════

    @http.route('/compras', type='http', auth='user', website=True)
    def listado_compras(self, **kwargs):
        """
        Página principal: Dashboard de compras.
        
        - Aplica filtros dinámicos
        - Obtiene categorías para select
        - Renderiza tabla con todas las compras
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return request.redirect('/')

        # ── Construir domain con filtros ──
        domain = self._construir_domain_filtros(kwargs)

        # ── Buscar compras ──
        OrdenCompra = request.env['purchase.order'].sudo()
        compras = OrdenCompra.search(domain, order='date_order desc, id desc')

        # ── Obtener categorías para filter select ──
        categorias = request.env['product.category'].sudo().search([], order='name asc')

        # ── Obtener proveedores para autocomplete ──
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
            'filtros': kwargs,
            'total_compras': len(compras),
        }

        return request.render('compras_web.compras_template', ctx)

    # ═══════════════════════════════════════════════════════════════════════
    # RUTA GET: /compras/nueva - Formulario de nueva compra
    # ═══════════════════════════════════════════════════════════════════════

    @http.route('/compras/nueva', type='http', auth='user', website=True)
    def formulario_nueva_compra(self, **kwargs):
        """
        Formulario para crear una nueva orden de compra.
        
        Carga:
        - Proveedores (res.partner)
        - Productos (product.product)
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
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

    # ═══════════════════════════════════════════════════════════════════════
    # RUTA POST: /compras/crear_proveedor - Crear proveedor rápidamente
    # ═══════════════════════════════════════════════════════════════════════

    @http.route('/compras/crear_proveedor', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def crear_proveedor_rapido(self, nombre):
        """
        Crea un proveedor rápidamente sin abandonar el formulario.
        
        Parámetros (JSON-RPC):
        - nombre: Nombre del proveedor (obligatorio)
        
        Retorna: { 'success': bool, 'id': int, 'nombre': str }
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'success': False, 'message': 'No tiene permisos.'}

        # ── Validación de datos ──
        nombre = (nombre or '').strip()
        if not nombre:
            return {'success': False, 'message': 'El nombre del proveedor es obligatorio.'}

        try:
            # Verificar si ya existe
            proveedor_existente = request.env['res.partner'].sudo().search(
                [('name', '=', nombre), ('supplier_rank', '>', 0)],
                limit=1
            )
            if proveedor_existente:
                return {
                    'success': True,
                    'id': proveedor_existente.id,
                    'nombre': proveedor_existente.name,
                    'es_nuevo': False,
                    'message': 'Proveedor ya existe.'
                }

            # Crear nuevo proveedor
            proveedor_nuevo = request.env['res.partner'].sudo().create({
                'name': nombre,
                'supplier_rank': 1,  # Marcar como proveedor
                'type': 'invoice',
            })

            return {
                'success': True,
                'id': proveedor_nuevo.id,
                'nombre': proveedor_nuevo.name,
                'es_nuevo': True,
                'message': 'Proveedor creado exitosamente.'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear proveedor: {str(e)}'
            }

    # ═══════════════════════════════════════════════════════════════════════
    # RUTA POST: /compras/crear - Crear nueva orden de compra
    # ═══════════════════════════════════════════════════════════════════════

    @http.route('/compras/crear', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def crear_compra(self, proveedor_id, lineas):
        """
        Crea una nueva orden de compra con líneas de productos.
        
        IMPORTANTE: La compra se crea en estado DRAFT sin modificar stock.
        El stock solo se incrementa en la confirmación.
        
        Parámetros (JSON-RPC):
        - proveedor_id: ID del proveedor (res.partner)
        - lineas: Lista de dicts [{'product_id': int, 'cantidad': float, 'precio_unitario': float}, ...]
        
        Retorna: { 'success': bool, 'orden_id': int, 'nombre_orden': str }
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'success': False, 'message': 'No tiene permisos.'}

        try:
            # ── Validar proveedor ──
            proveedor = request.env['res.partner'].sudo().browse(int(proveedor_id))
            if not proveedor.exists():
                return {'success': False, 'message': 'Proveedor no encontrado.'}

            # ── Validar líneas ──
            if not lineas or not isinstance(lineas, list):
                return {'success': False, 'message': 'Debe agregar al menos un producto.'}

            # ── Crear orden de compra (DRAFT) ──
            compra_vals = {
                'partner_id': proveedor.id,
                'state': 'draft',
                'date_order': datetime.now(),
            }

            orden_compra = request.env['purchase.order'].sudo().create(compra_vals)

            # ── Crear líneas de compra ──
            for linea_data in lineas:
                try:
                    product_id = int(linea_data.get('product_id', 0))
                    cantidad = float(linea_data.get('cantidad', 1))
                    precio_unt = float(linea_data.get('precio_unitario', 0))

                    if product_id <= 0 or cantidad <= 0 or precio_unt < 0:
                        continue

                    producto = request.env['product.product'].sudo().browse(product_id)
                    if not producto.exists():
                        continue

                    # Crear línea de compra
                    request.env['purchase.order.line'].sudo().create({
                        'order_id': orden_compra.id,
                        'product_id': producto.id,
                        'product_qty': cantidad,
                        'price_unit': precio_unt,
                    })

                except (ValueError, TypeError, Exception):
                    continue

            return {
                'success': True,
                'orden_id': orden_compra.id,
                'nombre_orden': orden_compra.name,
                'message': f'Orden {orden_compra.name} creada exitosamente.',
                'url': '/compras'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear la compra: {str(e)}'
            }

    # ═══════════════════════════════════════════════════════════════════════
    # RUTA POST: /compras/confirmar - Confirmar compra e incrementar stock
    # ═══════════════════════════════════════════════════════════════════════

    @http.route('/compras/confirmar', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def confirmar_compra(self, orden_id):
        """
        Confirma una orden de compra y INCREMENTA STOCK.
        
        Proceso:
        1. Ejecuta button_confirm() de Odoo (estado DRAFT → PURCHASE)
        2. Para cada línea, incrementa stock.quant en ubicación WH/Stock
        3. Evita confirmaciones duplicadas
        
        Parámetros (JSON-RPC):
        - orden_id: ID de purchase.order
        
        Retorna: { 'success': bool, 'message': str }
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'success': False, 'message': 'No tiene permisos.'}

        try:
            orden = request.env['purchase.order'].sudo().browse(int(orden_id))

            if not orden.exists():
                return {'success': False, 'message': 'Orden no encontrada.'}

            if orden.state != 'draft':
                return {
                    'success': False,
                    'message': f'Solo se pueden confirmar órdenes en DRAFT. Estado actual: {orden.state}'
                }

            # ── Paso 1: Confirmar orden (estado DRAFT → PURCHASE) ──
            try:
                orden.button_confirm()
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Error al confirmar orden: {str(e)}'
                }

            # ── Paso 2: Incrementar stock en WH/Stock ──
            try:
                # Buscar ubicación interna (WH/Stock)
                ubicacion_stock = request.env['stock.location'].sudo().search(
                    [('usage', '=', 'internal')],
                    limit=1
                )

                if not ubicacion_stock:
                    return {
                        'success': False,
                        'message': 'No se encontró una ubicación de inventario válida (WH/Stock).'
                    }

                # Incrementar stock para cada línea de compra
                for linea in orden.order_line:
                    if linea.product_id and linea.product_qty > 0:
                        # ── Validaciones básicas ──
                        if linea.product_qty <= 0:
                            continue

                        # Buscar o crear stock.quant en ubicación WH/Stock
                        Quant = request.env['stock.quant'].sudo()
                        quant = Quant.search([
                            ('product_id', '=', linea.product_id.id),
                            ('location_id', '=', ubicacion_stock.id)
                        ], limit=1)

                        if quant:
                            # Actualizar cantidad existente
                            quant.write({
                                'inventory_quantity': quant.inventory_quantity + linea.product_qty
                            })
                        else:
                            # Crear nuevo quant
                            Quant.create({
                                'product_id': linea.product_id.id,
                                'location_id': ubicacion_stock.id,
                                'inventory_quantity': linea.product_qty,
                            })

            except Exception as e:
                return {
                    'success': False,
                    'message': f'Error al actualizar stock: {str(e)}'
                }

            return {
                'success': True,
                'message': f'Orden {orden.name} confirmada. Stock incrementado.'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error inesperado: {str(e)}'
            }

    # ═══════════════════════════════════════════════════════════════════════
    # RUTA POST: /compras/cancelar - Cancelar una compra
    # ═══════════════════════════════════════════════════════════════════════

    @http.route('/compras/cancelar', type='jsonrpc', auth='user', website=True, methods=['POST'])
    def cancelar_compra(self, orden_id):
        """
        Cancela una orden de compra.
        
        IMPORTANTE: NO modifica stock bajo ninguna circunstancia.
        Si la orden aún no fue confirmada, no hay stock que revertir.
        Si ya fue confirmada, el usuario es responsable de reversal manual.
        
        Parámetros (JSON-RPC):
        - orden_id: ID de purchase.order
        
        Retorna: { 'success': bool, 'message': str }
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'success': False, 'message': 'No tiene permisos.'}

        try:
            orden = request.env['purchase.order'].sudo().browse(int(orden_id))

            if not orden.exists():
                return {'success': False, 'message': 'Orden no encontrada.'}

            if orden.state == 'cancel':
                return {
                    'success': False,
                    'message': 'Esta orden ya está cancelada.'
                }

            # ── Cancelar ──
            orden.button_cancel()

            return {
                'success': True,
                'message': f'Orden {orden.name} cancelada. No se modificó stock.'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al cancelar: {str(e)}'
            }
