"""
==============================================================================
SERVICIO DE PANEL - Panel Service
==============================================================================

Centraliza TODA la lógica de negocio del módulo panel_web:
- Cálculo de métricas generales (ventas, compras, ingresos, gastos, stock)
- Cálculo de indicadores analíticos (TOP 5 productos, TOP 5 clientes, promedios)
- Detección de alertas dinámicas (stock bajo, órdenes pendientes, etc.)
- Preparación de datos para gráficos (ventas por categoría, evolución de ventas)

Este modelo es ABSTRACTO y no genera tablas en BD.
Se instancia desde los controllers para acceder a los métodos de negocio.

Uso:
    panel_service = self.env['panel.service']
    metricas = panel_service.obtener_metricas_generales(fecha_desde, fecha_hasta)
    indicadores = panel_service.obtener_indicadores_detallados(fecha_desde, fecha_hasta)
    alertas = panel_service.obtener_alertas()
    graficos = panel_service.obtener_datos_graficos(fecha_desde, fecha_hasta)

==============================================================================
"""

from odoo import models, api
from datetime import datetime, timedelta


class PanelService(models.AbstractModel):
    """Servicio centralizado de lógica de negocio para panel_web"""
    
    _name = 'panel.service'
    _description = 'Servicio de Panel Web'

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 1: UTILIDADES Y HELPERS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def obtener_fecha_por_defecto(self):
        """
        Retorna rango de fechas por defecto (mes actual).
        
        Returns:
            tuple: (fecha_desde_iso, fecha_hasta_iso) en formato ISO 8601
        """
        hoy = datetime.now()
        primer_dia = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ultimo_dia = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
        return (primer_dia.isoformat(), ultimo_dia.isoformat())

    @api.model
    def _construir_domain_ventas(self, fecha_desde, fecha_hasta):
        """
        Construye domain para buscar órdenes de venta confirmadas.
        
        Args:
            fecha_desde (str): Fecha inicio en formato ISO
            fecha_hasta (str): Fecha fin en formato ISO
        
        Returns:
            list: Domain compatible con sale.order.search()
        """
        return [
            ('date_order', '>=', fecha_desde),
            ('date_order', '<=', fecha_hasta),
            ('state', 'in', ['sale', 'done']),  # Solo confirmadas/entregadas
        ]

    @api.model
    def _construir_domain_compras(self, fecha_desde, fecha_hasta):
        """
        Construye domain para buscar órdenes de compra confirmadas.
        
        Args:
            fecha_desde (str): Fecha inicio en formato ISO
            fecha_hasta (str): Fecha fin en formato ISO
        
        Returns:
            list: Domain compatible con purchase.order.search()
        """
        return [
            ('date_order', '>=', fecha_desde),
            ('date_order', '<=', fecha_hasta),
            ('state', 'in', ['purchase', 'done']),  # Solo confirmadas/entregadas
        ]

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 2: MÉTRICAS GENERALES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def obtener_metricas_generales(self, fecha_desde, fecha_hasta, categoria_id=''):
        """
        Calcula métricas principales: ventas, compras, ingresos, gastos, stock.
        
        Retorna:
        - total_ventas: cantidad de órdenes de venta confirmadas
        - ingresos: suma de amount_total de ventas
        - total_compras: cantidad de órdenes de compra confirmadas
        - gastos: suma de amount_total de compras
        - ganancia_neta: ingresos - gastos
        - productos_activos: cantidad de productos activos
        - productos_sin_stock: cantidad de productos con cantidad = 0
        - productos_bajo_stock: cantidad de productos con cantidad entre 1-9
        
        Args:
            fecha_desde (str): Fecha inicio en formato ISO
            fecha_hasta (str): Fecha fin en formato ISO
            categoria_id (str): ID de categoría (opcional, no usado en esta versión)
        
        Returns:
            dict: Diccionario con todas las métricas calculadas
        """
        Quant = self.env['stock.quant'].sudo()
        SaleOrder = self.env['sale.order'].sudo()
        PurchaseOrder = self.env['purchase.order'].sudo()
        Product = self.env['product.product'].sudo()
        
        # Construir domains
        domain_fecha_venta = self._construir_domain_ventas(fecha_desde, fecha_hasta)
        domain_fecha_compra = self._construir_domain_compras(fecha_desde, fecha_hasta)
        
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

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 3: INDICADORES ANALÍTICOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def obtener_indicadores_detallados(self, fecha_desde, fecha_hasta):
        """
        Calcula indicadores analíticos avanzados:
        - TOP 5 productos más vendidos (con cantidad y categoría)
        - TOP 5 clientes más compradores (con monto total)
        - Ticket promedio
        - Items promedio por venta
        - Total de órdenes en el período
        
        Args:
            fecha_desde (str): Fecha inicio en formato ISO
            fecha_hasta (str): Fecha fin en formato ISO
        
        Returns:
            dict: Diccionario con todos los indicadores calculados
        """
        SaleOrder = self.env['sale.order'].sudo()
        Product = self.env['product.product'].sudo()
        ResPartner = self.env['res.partner'].sudo()
        
        domain_fecha = self._construir_domain_ventas(fecha_desde, fecha_hasta)
        ventas = SaleOrder.search(domain_fecha)
        
        # TOP 5 PRODUCTOS MÁS VENDIDOS
        productos_mas_vendidos = self._obtener_top_productos(ventas)
        
        # TOP 5 CLIENTES MÁS COMPRADORES
        clientes_top = self._obtener_top_clientes(ventas)
        
        # TICKET PROMEDIO
        ticket_promedio = self._calcular_ticket_promedio(ventas)
        
        # ITEMS PROMEDIO POR VENTA
        items_promedio = self._calcular_items_promedio(ventas)
        
        return {
            'productos_top': productos_mas_vendidos,
            'clientes_top': clientes_top,
            'ticket_promedio': ticket_promedio,
            'items_promedio': items_promedio,
            'total_ordenes': len(ventas),
        }

    @api.model
    def _obtener_top_productos(self, ventas, limite=5):
        """
        Extrae los TOP N productos más vendidos de un recordset de ventas.
        
        Args:
            ventas: Recordset de sale.order
            limite (int): Cantidad de productos a retornar (default 5)
        
        Returns:
            list: Lista de dicts con nombre, cantidad y categoría de cada producto
        """
        Product = self.env['product.product'].sudo()
        
        # Agregar cantidades por producto
        productos_qty = {}
        for venta in ventas:
            for linea in venta.order_line:
                pid = linea.product_id.id
                productos_qty[pid] = productos_qty.get(pid, 0) + linea.product_qty
        
        # Ordenar y tomar TOP N
        top_productos = sorted(
            productos_qty.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limite]
        
        # Construir respuesta
        productos_mas_vendidos = []
        for pid, qty in top_productos:
            prod = Product.browse(pid)
            productos_mas_vendidos.append({
                'nombre': prod.name,
                'cantidad': qty,
                'categoria': prod.categ_id.name,
            })
        
        return productos_mas_vendidos

    @api.model
    def _obtener_top_clientes(self, ventas, limite=5):
        """
        Extrae los TOP N clientes con mayor volumen de compras.
        
        Args:
            ventas: Recordset de sale.order
            limite (int): Cantidad de clientes a retornar (default 5)
        
        Returns:
            list: Lista de dicts con nombre y monto total de cada cliente
        """
        ResPartner = self.env['res.partner'].sudo()
        
        # Agregar montos por cliente
        clientes_qty = {}
        for venta in ventas:
            cid = venta.partner_id.id
            clientes_qty[cid] = clientes_qty.get(cid, 0) + venta.amount_total
        
        # Ordenar y tomar TOP N
        top_clientes = sorted(
            clientes_qty.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limite]
        
        # Construir respuesta
        clientes_top = []
        for cid, monto in top_clientes:
            cliente = ResPartner.browse(cid)
            clientes_top.append({
                'nombre': cliente.name,
                'monto': round(monto, 2),
            })
        
        return clientes_top

    @api.model
    def _calcular_ticket_promedio(self, ventas):
        """
        Calcula el monto promedio de las órdenes.
        
        Args:
            ventas: Recordset de sale.order
        
        Returns:
            float: Monto promedio redondeado a 2 decimales
        """
        if not ventas:
            return 0
        
        total = sum(ventas.mapped('amount_total'))
        return round(total / len(ventas), 2)

    @api.model
    def _calcular_items_promedio(self, ventas):
        """
        Calcula la cantidad promedio de items por orden.
        
        Args:
            ventas: Recordset de sale.order
        
        Returns:
            float: Cantidad promedio redondeada a 1 decimal
        """
        if not ventas:
            return 0
        
        total_items = sum(len(v.order_line) for v in ventas)
        return round(total_items / len(ventas), 1)

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 4: ALERTAS DINÁMICAS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def obtener_alertas(self):
        """
        Identifica problemas operacionales y crea alertas dinámicas.
        
        Verifica:
        1. Productos sin stock (cantidad = 0)
        2. Stock bajo (cantidad < 10)
        3. Productos sin precio de costo
        4. Ventas pendientes de confirmación (state = draft)
        5. Compras pendientes de confirmación (state = draft)
        
        Returns:
            list: Lista de dicts con alertas (tipo, titulo, mensaje, icono)
        """
        alertas = []
        
        # Alerta 1: STOCK CERO
        alertas.extend(self._generar_alerta_stock_cero())
        
        # Alerta 2: STOCK BAJO
        alertas.extend(self._generar_alerta_stock_bajo())
        
        # Alerta 3: PRODUCTOS SIN PRECIO
        alertas.extend(self._generar_alerta_sin_precio())
        
        # Alerta 4: VENTAS PENDIENTES
        alertas.extend(self._generar_alerta_ventas_draft())
        
        # Alerta 5: COMPRAS PENDIENTES
        alertas.extend(self._generar_alerta_compras_draft())
        
        return alertas

    @api.model
    def _generar_alerta_stock_cero(self):
        """Genera alerta si hay productos sin stock."""
        Quant = self.env['stock.quant'].sudo()
        sin_stock = Quant.search([('quantity', '=', 0)])
        
        if sin_stock:
            return [{
                'tipo': 'warning',
                'titulo': 'Productos sin Stock',
                'mensaje': f'{len(sin_stock)} producto(s) con cantidad = 0',
                'icono': '📦',
            }]
        return []

    @api.model
    def _generar_alerta_stock_bajo(self):
        """Genera alerta si hay productos con stock bajo."""
        Quant = self.env['stock.quant'].sudo()
        bajo_stock = Quant.search([('quantity', '>', 0), ('quantity', '<', 10)])
        
        if bajo_stock:
            return [{
                'tipo': 'info',
                'titulo': 'Stock Bajo',
                'mensaje': f'{len(bajo_stock)} producto(s) con cantidad < 10',
                'icono': '⚠️',
            }]
        return []

    @api.model
    def _generar_alerta_sin_precio(self):
        """Genera alerta si hay productos sin precio de costo."""
        Product = self.env['product.product'].sudo()
        sin_precio = Product.search([('standard_price', '=', 0)])
        
        if sin_precio:
            return [{
                'tipo': 'danger',
                'titulo': 'Productos sin Precio de Costo',
                'mensaje': f'{len(sin_precio)} producto(s) sin precio estándar',
                'icono': '💰',
            }]
        return []

    @api.model
    def _generar_alerta_ventas_draft(self):
        """Genera alerta si hay ventas sin confirmar."""
        SaleOrder = self.env['sale.order'].sudo()
        ventas_draft = SaleOrder.search([('state', '=', 'draft')])
        
        if ventas_draft:
            return [{
                'tipo': 'warning',
                'titulo': 'Ventas Pendientes de Confirmación',
                'mensaje': f'{len(ventas_draft)} venta(s) en estado DRAFT',
                'icono': '📋',
            }]
        return []

    @api.model
    def _generar_alerta_compras_draft(self):
        """Genera alerta si hay compras sin confirmar."""
        PurchaseOrder = self.env['purchase.order'].sudo()
        compras_draft = PurchaseOrder.search([('state', '=', 'draft')])
        
        if compras_draft:
            return [{
                'tipo': 'warning',
                'titulo': 'Compras Pendientes de Confirmación',
                'mensaje': f'{len(compras_draft)} compra(s) en estado DRAFT',
                'icono': '📋',
            }]
        return []

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 5: DATOS PARA GRÁFICOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def obtener_datos_graficos(self, fecha_desde, fecha_hasta, categoria_id=''):
        """
        Prepara datos estructurados en formato dict para renderizar gráficos.
        
        Genera:
        1. Gráfico de ventas por categoría (barras)
        2. Gráfico de evolución de ventas por día (línea)
        
        Args:
            fecha_desde (str): Fecha inicio en formato ISO
            fecha_hasta (str): Fecha fin en formato ISO
            categoria_id (str): ID de categoría (opcional, no usado en esta versión)
        
        Returns:
            dict: Diccionario con dos gráficos (ventas_por_categoria, evolucion_ventas)
        """
        domain = self._construir_domain_ventas(fecha_desde, fecha_hasta)
        ventas = self.env['sale.order'].sudo().search(domain)
        
        # Gráfico 1: VENTAS POR CATEGORÍA
        grafico_categorias = self._generar_grafico_categorias(ventas)
        
        # Gráfico 2: EVOLUCIÓN DE VENTAS
        grafico_evolucion = self._generar_grafico_evolucion(ventas)
        
        return {
            'ventas_por_categoria': grafico_categorias,
            'evolucion_ventas': grafico_evolucion,
        }

    @api.model
    def _generar_grafico_categorias(self, ventas):
        """
        Genera datos para gráfico de barras (ventas por categoría).
        
        Args:
            ventas: Recordset de sale.order
        
        Returns:
            dict: Diccionario con labels (categorías) y data (montos)
        """
        categoria_montos = {}
        
        for venta in ventas:
            for linea in venta.order_line:
                cat_name = linea.product_id.categ_id.name or 'Sin categoría'
                monto = linea.price_subtotal
                categoria_montos[cat_name] = categoria_montos.get(cat_name, 0) + monto
        
        return {
            'labels': list(categoria_montos.keys()),
            'data': list(categoria_montos.values()),
        }

    @api.model
    def _generar_grafico_evolucion(self, ventas):
        """
        Genera datos para gráfico de línea (evolución de ventas por día).
        
        Args:
            ventas: Recordset de sale.order
        
        Returns:
            dict: Diccionario con labels (fechas) y data (montos acumulados por día)
        """
        ventas_por_fecha = {}
        
        for venta in ventas:
            fecha_key = venta.date_order.strftime('%Y-%m-%d')
            monto = venta.amount_total
            ventas_por_fecha[fecha_key] = ventas_por_fecha.get(fecha_key, 0) + monto
        
        fechas_ordenadas = sorted(ventas_por_fecha.keys())
        
        return {
            'labels': fechas_ordenadas,
            'data': [ventas_por_fecha[f] for f in fechas_ordenadas],
        }
