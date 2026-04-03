"""
==============================================================================
SERVICIO DE INVENTARIO - Inventario Service
==============================================================================

Centraliza TODA la lógica de negocio del módulo inventario_web:
- Filtros avanzados de productos
- Búsqueda y obtención de stock
- Actualización de campos de productos
- Gestión de stock (stock.quant)
- Obtención de categorías

Este modelo es ABSTRACTO y no genera tablas en BD.
Se instancia desde los controllers para acceder a los métodos de negocio.

Uso:
    inventario_service = self.env['inventario.service']
    domain = inventario_service.construir_domain_filtros(kwargs)
    productos = inventario_service.obtener_productos(domain)
    categorias = inventario_service.obtener_categorias()
    inventario_service.actualizar_cantidad_stock(product_id, nueva_cantidad)

==============================================================================
"""

from odoo import models, api


class InventarioService(models.AbstractModel):
    """Servicio centralizado de lógica de negocio para inventario_web"""
    
    _name = 'inventario.service'
    _description = 'Servicio de Inventario Web'

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 1: FILTROS AVANZADOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def extraer_filtros(self, kwargs):
        """
        Extrae los parámetros de filtro de los argumentos GET
        y los devuelve en un dict con prefijo f_ para repoblar la vista.

        Args:
            kwargs (dict): Parámetros GET recibidos en la petición.

        Returns:
            dict: Filtros normalizados con prefijo f_.
        """
        return {
            'f_nombre': kwargs.get('nombre', '').strip(),
            'f_proveedor': kwargs.get('proveedor', '').strip(),
            'f_categoria': kwargs.get('categoria', '').strip(),
            'f_estado': kwargs.get('estado', 'activo').strip(),
            'f_cantidad': kwargs.get('cantidad', '').strip(),
            'f_cantidad_op': kwargs.get('cantidad_op', 'exact').strip(),
            'f_precio_costo': kwargs.get('precio_costo', '').strip(),
            'f_precio_venta': kwargs.get('precio_venta', '').strip(),
        }

    @api.model
    def construir_domain_filtros(self, filtros):
        """
        Construye una lista de tuplas (domain) para el ORM
        a partir del diccionario de filtros recibidos por GET.

        Soporta:
        - nombre: búsqueda parcial en product.name (ilike)
        - proveedor: búsqueda en seller_ids.partner_id.name (ilike)
        - categoria: selección exacta por product.categ_id (ID)
        - estado: activo/inactivo/todos
        - cantidad: búsqueda en qty_available con operadores (=, <, >)
        - precio_costo: búsqueda en standard_price (>=)
        - precio_venta: búsqueda en list_price (>=)

        Args:
            filtros (dict): Diccionario con los valores de filtro
                            extraídos de los parámetros GET.

        Returns:
            list: Domain compatible con product.product.search().
        """
        dominio = []

        # Filtro por nombre (búsqueda parcial, insensible a mayúsculas)
        nombre = filtros.get('f_nombre')
        if nombre:
            dominio.append(('name', 'ilike', nombre))

        # Filtro por proveedor (a través de seller_ids → partner_id)
        proveedor = filtros.get('f_proveedor')
        if proveedor:
            dominio.append(('seller_ids.partner_id.name', 'ilike', proveedor))

        # Filtro por categoría (selección exacta por ID)
        categoria = filtros.get('f_categoria')
        if categoria:
            try:
                dominio.append(('categ_id', '=', int(categoria)))
            except (ValueError, TypeError):
                pass  # Ignorar si el valor no es un entero válido

        # Filtro por estado (activo / inactivo / todos)
        # Nota: el manejo de 'active_test' en contexto se hace en obtener_productos(),
        # no aquí, porque requiere modificar el contexto de búsqueda.
        estado = filtros.get('f_estado', 'activo')
        if estado == 'activo':
            dominio.append(('active', '=', True))
        elif estado == 'inactivo':
            dominio.append(('active', '=', False))
        # 'todos' → no se agrega filtro de active (se desactiva active_test en obtener_productos)

        # Filtro por cantidad (stock disponible)
        cantidad = filtros.get('f_cantidad')
        operador_cantidad = filtros.get('f_cantidad_op', 'exact')
        if cantidad not in (None, ''):
            try:
                valor_cantidad = float(cantidad)
                mapa_operadores = {
                    'exact': '=',
                    'lt': '<',
                    'gt': '>',
                }
                operador = mapa_operadores.get(operador_cantidad, '=')
                dominio.append(('qty_available', operador, valor_cantidad))
            except (ValueError, TypeError):
                pass  # Ignorar si el valor no es numérico

        # Filtro por precio de costo (mayor o igual)
        precio_costo = filtros.get('f_precio_costo')
        if precio_costo not in (None, ''):
            try:
                dominio.append(('standard_price', '>=', float(precio_costo)))
            except (ValueError, TypeError):
                pass

        # Filtro por precio de venta (mayor o igual)
        precio_venta = filtros.get('f_precio_venta')
        if precio_venta not in (None, ''):
            try:
                dominio.append(('list_price', '>=', float(precio_venta)))
            except (ValueError, TypeError):
                pass

        return dominio

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 2: BÚSQUEDA Y OBTENCIÓN DE DATOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def obtener_productos(self, dominio, incluir_inactivos=False):
        """
        Obtiene productos según un domain dinámico.

        Args:
            dominio (list): Domain Odoo para filtrar productos (tuplas).
            incluir_inactivos (bool): Si es True, incluye productos con active=False.

        Returns:
            product.product (recordset): Productos que cumplen el domain.
        """
        ProductoProducto = self.env['product.product'].sudo()

        # Si se solicita incluir inactivos, desactivar active_test
        if incluir_inactivos:
            ProductoProducto = ProductoProducto.with_context(active_test=False)

        return ProductoProducto.search(dominio)

    @api.model
    def obtener_categorias(self):
        """
        Obtiene todas las categorías de productos, ordenadas alfabéticamente.

        Returns:
            product.category (recordset): Categorías disponibles (ordenadas por nombre).
        """
        return self.env['product.category'].sudo().search(
            [], order='name asc'
        )

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 3: ACTUALIZACIÓN DE CAMPOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def actualizar_campo_producto(self, product_id, field, value):
        """
        Actualiza un campo específico de un producto.

        Soporta los campos:
        - name: nombre del producto (validación: obligatorio)
        - description_ecommerce: descripción para ecommerce
        - categ_id: categoría del producto (validación: ID válido)
        - qty_available: cantidad de stock (validación: >= 0, especial manejo de quant)
        - standard_price: precio de costo (validación: >= 0)
        - list_price: precio de venta (validación: >= 0)
        - active: estado activo/inactivo (booleano)

        Args:
            product_id (int): ID del product.product.
            field (str): Nombre del campo técnico.
            value (any): Nuevo valor.

        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        try:
            producto = self.env['product.product'].sudo().browse(int(product_id))
            if not producto.exists():
                return {'success': False, 'message': 'El producto no existe.'}

            # ── Lógica específica por campo ──

            if field == 'name':
                if not value or not str(value).strip():
                    return {'success': False, 'message': 'El nombre es obligatorio.'}
                producto.write({'name': value})

            elif field == 'description_ecommerce':
                producto.write({'description_ecommerce': value})

            elif field == 'categ_id':
                try:
                    cat_id = int(value)
                    if cat_id <= 0:
                        return {'success': False, 'message': 'Categoría no válida.'}
                    producto.write({'categ_id': cat_id})
                except (ValueError, TypeError):
                    return {'success': False, 'message': 'ID de categoría no válido.'}

            elif field == 'qty_available':
                result = self._actualizar_cantidad_stock(producto, value)
                return result

            elif field == 'standard_price':
                try:
                    valor = float(value)
                    if valor < 0:
                        return {'success': False, 'message': 'El precio de costo debe ser positivo.'}
                    producto.write({'standard_price': valor})
                except (ValueError, TypeError):
                    return {'success': False, 'message': 'Precio no válido.'}

            elif field == 'list_price':
                try:
                    valor = float(value)
                    if valor < 0:
                        return {'success': False, 'message': 'El precio de venta debe ser positivo.'}
                    producto.write({'list_price': valor})
                except (ValueError, TypeError):
                    return {'success': False, 'message': 'Precio no válido.'}

            elif field == 'active':
                # Esperamos un booleano (True/False)
                producto.write({'active': bool(value)})

            elif field == 'x_costo_usd':
                try:
                    valor = float(value)
                    if valor < 0:
                        return {'success': False, 'message': 'El costo USD debe ser positivo.'}
                    # Escribir en el template del producto
                    producto.product_tmpl_id.write({'x_costo_usd': valor})
                except (ValueError, TypeError):
                    return {'success': False, 'message': 'Costo USD no válido.'}

            else:
                return {'success': False, 'message': 'Campo no soportado para edición.'}

            return {'success': True, 'message': 'Campo actualizado correctamente.'}

        except Exception as e:
            return {'success': False, 'message': f'Error interno: {str(e)}'}

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 4: GESTIÓN ESPECIAL DE STOCK
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def _actualizar_cantidad_stock(self, producto, nueva_cantidad):
        """
        Actualiza la cantidad de stock de un producto mediante stock.quant.

        IMPORTANTE:
        - Utiliza inventory_mode=True para manejar correctamente stock.quant
        - Evita duplicados buscando quant existente antes de crear
        - Solo maneja ubicaciones internas (usage='internal')
        - Valida que la cantidad sea >= 0

        Args:
            producto (product.product): Recordset del producto.
            nueva_cantidad (float): Nueva cantidad de stock.

        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            nueva_cantidad = float(nueva_cantidad)
            if nueva_cantidad < 0:
                return {'success': False, 'message': 'La cantidad no puede ser negativa.'}

            # ── Obtener ubicación interna ──
            location = self.env['stock.location'].sudo().search([
                ('usage', '=', 'internal')
            ], limit=1)

            if not location:
                return {'success': False, 'message': 'No se encontró una ubicación de inventario válida.'}

            # ── Buscar o crear quant ──
            Quant = self.env['stock.quant'].sudo().with_context(inventory_mode=True)
            quant = Quant.search([
                ('product_id', '=', producto.id),
                ('location_id', '=', location.id)
            ], limit=1)

            if quant:
                # ── Actualizar quant existente ──
                quant.write({'inventory_quantity': nueva_cantidad})
            else:
                # ── Crear nuevo quant (evita duplicados) ──
                Quant.create({
                    'product_id': producto.id,
                    'location_id': location.id,
                    'inventory_quantity': nueva_cantidad,
                })

            return {'success': True, 'message': 'Stock actualizado correctamente.'}

        except (ValueError, TypeError):
            return {'success': False, 'message': 'Cantidad no válida.'}
        except Exception as e:
            return {'success': False, 'message': f'Error al actualizar stock: {str(e)}'}
