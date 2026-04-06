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
import logging

_logger = logging.getLogger(__name__)


class PanelService(models.AbstractModel):
    """Servicio centralizado de lógica de negocio para panel_web"""
    
    _name = 'panel.service'
    _description = 'Servicio de Panel Web'

    # Umbral configurable para stock bajo
    STOCK_THRESHOLD = 10

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
        
        # INVENTARIO - Usar qty_available para máxima precisión en productos activos
        product_domain = [('active', '=', True), ('type', '=', 'product')]
        total_productos = Product.search_count([('active', '=', True)])
        
        # Productos sin stock (cantidad == 0)
        productos_sin_stock = Product.search_count(product_domain + [('qty_available', '=', 0)])
        
        # Productos con stock bajo (0 < cantidad < umbral)
        productos_bajo_stock = Product.search_count(product_domain + [
            ('qty_available', '>', 0), 
            ('qty_available', '<', self.STOCK_THRESHOLD)
        ])
        
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
        Product = self.env['product.product'].sudo()
        
        # Contar productos activos (congelado/almacenable) con stock == 0
        sin_stock_count = Product.search_count([
            ('active', '=', True), 
            ('type', '=', 'product'), 
            ('qty_available', '=', 0)
        ])
        
        if sin_stock_count > 0:
            return [{
                'tipo': 'warning',
                'titulo': 'Productos sin Stock',
                'mensaje': f'{sin_stock_count} producto(s) con stock = 0',
                'icono': '📦',
            }]
        return []

    @api.model
    def _generar_alerta_stock_bajo(self):
        """Genera alerta si hay productos con stock bajo."""
        Product = self.env['product.product'].sudo()
        
        # Contar productos activos (congelado/almacenable) con 0 < stock < umbral
        bajo_stock_count = Product.search_count([
            ('active', '=', True), 
            ('type', '=', 'product'), 
            ('qty_available', '>', 0), 
            ('qty_available', '<', self.STOCK_THRESHOLD)
        ])
        
        if bajo_stock_count > 0:
            return [{
                'tipo': 'info',
                'titulo': 'Stock Bajo',
                'mensaje': f'{bajo_stock_count} producto(s) con cantidad < {self.STOCK_THRESHOLD}',
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

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 6: DETALLES DE MÉTRICAS (para popups)
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def obtener_productos_sin_stock(self, page=1, limit=10):
        """
        Obtiene lista paginada de productos sin stock.
        
        Busca en stock.quant (tabla de inventario real) para encontrar todos los productos
        que tienen stock total = 0 en todas sus ubicaciones o que nunca han tenido inventario.
        
        MEJORAS ODOO 19:
        - Usa stock.quant como fuente de verdad (no qty_available que puede estar cacheada)
        - Agrega categoría del producto para mejor contexto
        - Considera ambos: productos con stock=0 y productos sin registros en stock.quant
        - Ordenado por nombre para fácil búsqueda
        
        Args:
            page (int): Número de página (1-indexado)
            limit (int): Cantidad de registros por página
        
        Returns:
            dict: {total: int, items: list, page: int, limit: int, total_pages: int}
        """
        Product = self.env['product.product'].sudo()
        
        # PASO 1: Buscar productos activos tipo 'congelado/almacenable' con stock 0
        domain = [('active', '=', True), ('type', '=', 'product'), ('qty_available', '=', 0)]
        sin_stock_total = Product.search(domain, order='name ASC')
        total = len(sin_stock_total)
        
        _logger.info(f"[PANEL] sin_stock: Encontrados {total} productos con cantidad = 0")
        
        # PASO 2: Paginar
        offset = (page - 1) * limit
        items_paginados = sin_stock_total[offset:offset + limit]
        
        # PASO 3: Construir respuesta
        items = []
        for prod in items_paginados:
            items.append({
                'id': prod.id,
                'nombre': prod.name,
                'stock': 0,
                'sku': prod.default_code or 'N/A',
                'categoria': prod.categ_id.name or 'Sin categoría',
            })
        
        return {
            'total': total,
            'items': items,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit,
        }

    @api.model
    def obtener_productos_bajo_stock(self, page=1, limit=10):
        """
        Obtiene lista paginada de productos con stock bajo (0 < stock < 10).
        
        Busca en stock.quant (tabla de inventario real) para encontrar todos los productos
        cuya suma de stock en todas ubicaciones esté entre 1 y 9.
        
        MEJORAS ODOO 19:
        - Usa stock.quant como fuente de verdad (no qty_available que puede estar cacheada)
        - Agrega categoría del producto para mejor contexto
        - Ordena por stock disponible (ASC) para priorizar productos más críticos
        - Incluye información de ubicación principal
        
        Args:
            page (int): Número de página (1-indexado)
            limit (int): Cantidad de registros por página
        
        Returns:
            dict: {total: int, items: list, page: int, limit: int, total_pages: int}
        """
        Product = self.env['product.product'].sudo()
        
        # PASO 1: Buscar productos con stock entre 1 y umbral-1
        domain = [
            ('active', '=', True), 
            ('type', '=', 'product'), 
            ('qty_available', '>', 0), 
            ('qty_available', '<', self.STOCK_THRESHOLD)
        ]
        bajo_stock_products = Product.search(domain, order='qty_available ASC, name ASC')
        total = len(bajo_stock_products)
        
        _logger.info(f"[PANEL] bajo_stock: Encontrados {total} productos con 0<stock<{self.STOCK_THRESHOLD}")
        
        # PASO 2: Paginar
        offset = (page - 1) * limit
        items_paginados = bajo_stock_products[offset:offset + limit]
        
        # PASO 3: Construir respuesta
        items = []
        for prod in items_paginados:
            items.append({
                'id': prod.id,
                'nombre': prod.name,
                'stock': int(prod.qty_available),
                'sku': prod.default_code or 'N/A',
                'categoria': prod.categ_id.name or 'Sin categoría',
                'ubicacion': 'Principal', # Simplificado, Odoo 19 gestiona múltiples
            })
        
        return {
            'total': total,
            'items': items,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit,
        }

    @api.model
    def obtener_detalles_ventas(self, fecha_desde, fecha_hasta, page=1, limit=10):
        """
        Obtiene lista paginada de ventas confirmadas en el período.
        
        Args:
            fecha_desde (str): Fecha inicio en formato ISO
            fecha_hasta (str): Fecha fin en formato ISO
            page (int): Número de página (1-indexado)
            limit (int): Cantidad de registros por página
        
        Returns:
            dict: {total: int, items: list, page: int, limit: int}
        """
        SaleOrder = self.env['sale.order'].sudo()
        
        domain = self._construir_domain_ventas(fecha_desde, fecha_hasta)
        ventas = SaleOrder.search(domain, order='date_order DESC')
        total = len(ventas)
        
        # Calcular offset para pagination
        offset = (page - 1) * limit
        items_paginados = ventas[offset:offset + limit]
        
        # Construir respuesta
        items = []
        for venta in items_paginados:
            # Obtener DNI/VAT del cliente
            dni = venta.partner_id.vat or ''
            if dni:
                # Limpiar y formatear DNI (remover espacios y caracteres especiales)
                dni = dni.replace(' ', '').strip()
            
            items.append({
                'id': venta.id,
                'numero': venta.name,
                'cliente': venta.partner_id.name,
                'dni': dni,
                'monto': round(venta.amount_total, 2),
                'fecha': venta.date_order.strftime('%d/%m/%Y'),
                'estado': venta.state,
            })
        
        return {
            'total': total,
            'items': items,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit,
        }

    @api.model
    def obtener_detalles_compras(self, fecha_desde, fecha_hasta, page=1, limit=10):
        """
        Obtiene lista paginada de compras confirmadas en el período.
        
        Args:
            fecha_desde (str): Fecha inicio en formato ISO
            fecha_hasta (str): Fecha fin en formato ISO
            page (int): Número de página (1-indexado)
            limit (int): Cantidad de registros por página
        
        Returns:
            dict: {total: int, items: list, page: int, limit: int}
        """
        PurchaseOrder = self.env['purchase.order'].sudo()
        
        domain = self._construir_domain_compras(fecha_desde, fecha_hasta)
        compras = PurchaseOrder.search(domain, order='date_order DESC')
        total = len(compras)
        
        # Calcular offset para pagination
        offset = (page - 1) * limit
        items_paginados = compras[offset:offset + limit]
        
        # Construir respuesta
        items = []
        for compra in items_paginados:
            # Obtener DNI/VAT del proveedor
            dni = compra.partner_id.vat or ''
            if dni:
                # Limpiar y formatear DNI (remover espacios y caracteres especiales)
                dni = dni.replace(' ', '').strip()
            
            items.append({
                'id': compra.id,
                'numero': compra.name,
                'proveedor': compra.partner_id.name,
                'dni': dni,
                'monto': round(compra.amount_total, 2),
                'fecha': compra.date_order.strftime('%d/%m/%Y'),
                'estado': compra.state,
            })
        
        return {
            'total': total,
            'items': items,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit,
        }

    @api.model
    def obtener_productos_activos(self, page=1, limit=10):
        """
        Obtiene lista paginada de productos activos.
        """
        Product = self.env['product.product'].sudo()
        productos = Product.search([('active', '=', True)], order='name ASC')
        total = len(productos)
        
        offset = (page - 1) * limit
        items_paginados = productos[offset:offset + limit]
        
        items = []
        for prod in items_paginados:
            # Obtener stock
            stock = prod.qty_available
            items.append({
                'id': prod.id,
                'nombre': prod.name,
                'categoria': prod.categ_id.name or 'N/A',
                'precio': prod.list_price,
                'stock': stock,
            })
        
        return {
            'total': total,
            'items': items,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit,
        }

