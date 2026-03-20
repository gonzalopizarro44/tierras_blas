from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
import json


class PanelController(http.Controller):

    @http.route('/panel', type='http', auth='user', website=True)
    def panel_administrativo(self, **kwargs):
        """
        Dashboard administrativo central con métricas, indicadores, alertas y gráficos.
        """
        
        # Validación de seguridad
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return request.redirect('/')
        
        # Obtener filtros
        fecha_desde = kwargs.get('fecha_desde', self._obtener_fecha_por_defecto()[0])
        fecha_hasta = kwargs.get('fecha_hasta', self._obtener_fecha_por_defecto()[1])
        categoria = kwargs.get('categoria', '')
        
        # Llamar funciones de datos
        metricas = self._obtener_metricas(fecha_desde, fecha_hasta, categoria)
        indicadores = self._obtener_indicadores(fecha_desde, fecha_hasta)
        alertas = self._obtener_alertas()
        graficos = self._obtener_datos_graficos(fecha_desde, fecha_hasta, categoria)
        categorias = request.env['product.category'].sudo().search([])
        
        # Condominio especial para filtros
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
        
        return request.render(
            'panel_web.panel_template',
            contexto
        )
    
    def _obtener_fecha_por_defecto(self):
        """Retorna rango de fechas por defecto (mes actual)."""
        hoy = datetime.now()
        primer_dia = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ultimo_dia = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
        return (primer_dia.isoformat(), ultimo_dia.isoformat())
    
    def _obtener_metricas(self, fecha_desde, fecha_hasta, categoria_id=''):
        """
        Calcula métricas principales: ventas, compras, ingresos, gastos, stock.
        """
        Quant = request.env['stock.quant'].sudo()
        SaleOrder = request.env['sale.order'].sudo()
        PurchaseOrder = request.env['purchase.order'].sudo()
        Product = request.env['product.product'].sudo()
        
        # Dominio base con fechas
        domain_fecha_venta = [
            ('date_order', '>=', fecha_desde),
            ('date_order', '<=', fecha_hasta),
            ('state', 'in', ['sale', 'done']),  # Solo confirmadas/entregadas
        ]
        domain_fecha_compra = [
            ('date_order', '>=', fecha_desde),
            ('date_order', '<=', fecha_hasta),
            ('state', 'in', ['purchase', 'done']),  # Solo confirmadas/entregadas
        ]
        
        # VENTAS
        ventas = SaleOrder.search(domain_fecha_venta)
        total_ventas = len(ventas)
        ingresos = sum(ventas.mapped('amount_total'))
        
        # COMPRAS
        compras = PurchaseOrder.search(domain_fecha_compra)
        total_compras = len(compras)
        gastos = sum(compras.mapped('amount_total'))
        
        # INVENTARIO
        productos_activos = Product.search([('active', '=', True)])
        total_productos = len(productos_activos)
        productos_sin_stock = Quant.search_count([('quantity', '=', 0)])
        productos_bajo_stock = Quant.search_count([('quantity', '>', 0), ('quantity', '<', 10)])
        
        return {
            'total_ventas': total_ventas,
            'ingresos': round(ingresos, 2),
            'total_compras': total_compras,
            'gastos': round(gastos, 2),
            'ganancia_neta': round(ingresos - gastos, 2),
            'productos_activos': total_productos,
            'productos_sin_stock': productos_sin_stock,
            'productos_bajo_stock': productos_bajo_stock,
        }
    
    def _obtener_indicadores(self, fecha_desde, fecha_hasta):
        """
        Calcula indicadores analíticos: TOP 5, promedios, etc.
        """
        SaleOrder = request.env['sale.order'].sudo()
        Product = request.env['product.product'].sudo()
        ResPartner = request.env['res.partner'].sudo()
        
        domain_fecha = [
            ('date_order', '>=', fecha_desde),
            ('date_order', '<=', fecha_hasta),
            ('state', 'in', ['sale', 'done']),
        ]
        
        # TOP 5 PRODUCTOS MÁS VENDIDOS
        ventas = SaleOrder.search(domain_fecha)
        productos_qty = {}
        for venta in ventas:
            for linea in venta.order_line:
                pid = linea.product_id.id
                productos_qty[pid] = productos_qty.get(pid, 0) + linea.product_qty
        
        top_productos = sorted(productos_qty.items(), key=lambda x: x[1], reverse=True)[:5]
        productos_mas_vendidos = []
        for pid, qty in top_productos:
            prod = Product.browse(pid)
            productos_mas_vendidos.append({
                'nombre': prod.name,
                'cantidad': qty,
                'categoria': prod.categ_id.name,
            })
        
        # TOP 5 CLIENTES MÁS COMPRADORES
        clientes_qty = {}
        for venta in ventas:
            cid = venta.partner_id.id
            clientes_qty[cid] = clientes_qty.get(cid, 0) + venta.amount_total
        
        top_clientes = sorted(clientes_qty.items(), key=lambda x: x[1], reverse=True)[:5]
        clientes_top = []
        for cid, monto in top_clientes:
            cliente = ResPartner.browse(cid)
            clientes_top.append({
                'nombre': cliente.name,
                'monto': round(monto, 2),
            })
        
        # TICKET PROMEDIO
        ticket_promedio = round(sum(ventas.mapped('amount_total')) / len(ventas), 2) if ventas else 0
        
        # ITEMS PROMEDIO POR VENTA
        items_promedio = round(sum(len(v.order_line) for v in ventas) / len(ventas), 1) if ventas else 0
        
        return {
            'productos_top': productos_mas_vendidos,
            'clientes_top': clientes_top,
            'ticket_promedio': ticket_promedio,
            'items_promedio': items_promedio,
            'total_ordenes': len(ventas),
        }
    
    def _obtener_alertas(self):
        """
        Identifica problemas y crea alertas dinámicas.
        """
        Quant = request.env['stock.quant'].sudo()
        Product = request.env['product.product'].sudo()
        SaleOrder = request.env['sale.order'].sudo()
        PurchaseOrder = request.env['purchase.order'].sudo()
        
        alertas = []
        
        # Alerta 1: STOCK CERO
        sin_stock = Quant.search([('quantity', '=', 0)])
        if sin_stock:
            alertas.append({
                'tipo': 'warning',
                'titulo': 'Productos sin Stock',
                'mensaje': f'{len(sin_stock)} producto(s) con cantidad = 0',
                'icono': '📦',
            })
        
        # Alerta 2: STOCK BAJO (menos de 10)
        bajo_stock = Quant.search([('quantity', '>', 0), ('quantity', '<', 10)])
        if bajo_stock:
            alertas.append({
                'tipo': 'info',
                'titulo': 'Stock Bajo',
                'mensaje': f'{len(bajo_stock)} producto(s) con cantidad < 10',
                'icono': '⚠️',
            })
        
        # Alerta 3: PRODUCTOS SIN PRECIO DE COSTO
        sin_precio = Product.search([('standard_price', '=', 0)])
        if sin_precio:
            alertas.append({
                'tipo': 'danger',
                'titulo': 'Productos sin Precio de Costo',
                'mensaje': f'{len(sin_precio)} producto(s) sin precio estándar',
                'icono': '💰',
            })
        
        # Alerta 4: VENTAS EN DRAFT (sin confirmar)
        ventas_draft = SaleOrder.search([('state', '=', 'draft')])
        if ventas_draft:
            alertas.append({
                'tipo': 'warning',
                'titulo': 'Ventas Pendientes de Confirmación',
                'mensaje': f'{len(ventas_draft)} venta(s) en estado DRAFT',
                'icono': '📋',
            })
        
        # Alerta 5: COMPRAS EN DRAFT (sin confirmar)
        compras_draft = PurchaseOrder.search([('state', '=', 'draft')])
        if compras_draft:
            alertas.append({
                'tipo': 'warning',
                'titulo': 'Compras Pendientes de Confirmación',
                'mensaje': f'{len(compras_draft)} compra(s) en estado DRAFT',
                'icono': '📋',
            })
        
        return alertas
    
    def _obtener_datos_graficos(self, fecha_desde, fecha_hasta, categoria_id=''):
        """
        Prepara datos en formato JSON para gráficos.
        """
        SaleOrder = request.env['sale.order'].sudo()
        
        domain = [
            ('date_order', '>=', fecha_desde),
            ('date_order', '<=', fecha_hasta),
            ('state', 'in', ['sale', 'done']),
        ]
        
        ventas = SaleOrder.search(domain)
        
        # GRÁFICO 1: VENTAS POR CATEGORÍA (BARRAS)
        categoria_montos = {}
        for venta in ventas:
            for linea in venta.order_line:
                cat_name = linea.product_id.categ_id.name or 'Sin categoría'
                monto = linea.price_subtotal
                categoria_montos[cat_name] = categoria_montos.get(cat_name, 0) + monto
        
        grafico_categorias = {
            'labels': list(categoria_montos.keys()),
            'data': list(categoria_montos.values()),
        }
        
        # GRÁFICO 2: EVOLUCIÓN DE VENTAS (LÍNEAS POR MES)
        ventas_por_fecha = {}
        for venta in ventas:
            fecha_key = venta.date_order.strftime('%Y-%m-%d')
            monto = venta.amount_total
            ventas_por_fecha[fecha_key] = ventas_por_fecha.get(fecha_key, 0) + monto
        
        fechas_ordenadas = sorted(ventas_por_fecha.keys())
        grafico_evolucion = {
            'labels': fechas_ordenadas,
            'data': [ventas_por_fecha[f] for f in fechas_ordenadas],
        }
        
        return {
            'ventas_por_categoria': grafico_categorias,
            'evolucion_ventas': grafico_evolucion,
        }
