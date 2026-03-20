from odoo import http
from odoo.http import request


class InventarioController(http.Controller):
    """Controlador principal del panel web de inventario.

    Muestra productos con filtros avanzados (GET).
    Las operaciones CRUD se realizan desde el backend de Odoo;
    los botones del frontend solo muestran un modal de advertencia.
    """

    # ── Método auxiliar: construir dominio dinámico ─────────────────────

    def _construir_dominio(self, filtros):
        """Construye una lista de tuplas (domain) para el ORM
        a partir del diccionario de filtros recibidos por GET.

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
        # Nota: el manejo de 'active_test' en contexto se hace en el método
        # principal, no aquí, porque requiere modificar el contexto de búsqueda.
        estado = filtros.get('f_estado', 'activo')
        if estado == 'activo':
            dominio.append(('active', '=', True))
        elif estado == 'inactivo':
            dominio.append(('active', '=', False))
        # 'todos' → no se agrega filtro de active (se desactiva active_test)

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

    # ── Método auxiliar: extraer filtros de kwargs ──────────────────────

    def _extraer_filtros(self, kwargs):
        """Extrae los parámetros de filtro de los argumentos GET
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

    # ── Ruta principal: GET /inventario ────────────────────────────────

    @http.route('/inventario', type='http', auth='user', website=True)
    def pagina_inventario(self, **kwargs):
        """Página principal del panel de inventario.

        - Valida que el usuario pertenezca al grupo administrador.
        - Extrae filtros de los parámetros GET.
        - Construye un domain dinámico y busca productos.
        - Carga las categorías para el select de filtro.
        - Renderiza el template con todos los datos necesarios.
        """

        # ── Validación de seguridad ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return request.redirect('/')

        # ── Extraer filtros de los parámetros GET ──
        filtros = self._extraer_filtros(kwargs)

        # ── Construir dominio dinámico ──
        dominio = self._construir_dominio(filtros)

        # ── Buscar productos ──
        # Se usa .sudo() porque los usuarios del website podrían no tener
        # permisos directos de lectura sobre product.product / stock.quant.
        ProductoProducto = request.env['product.product'].sudo()

        # Si el filtro de estado es 'todos', desactivar active_test
        # para que Odoo también devuelva productos con active=False.
        if filtros.get('f_estado') == 'todos':
            ProductoProducto = ProductoProducto.with_context(active_test=False)

        productos = ProductoProducto.search(dominio)

        # ── Obtener categorías para el select de filtro ──
        categorias = request.env['product.category'].sudo().search(
            [], order='name asc'
        )

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
        """Actualiza un campo específico de un producto.

        Args:
            product_id (int): ID del product.product.
            field (str): Nombre del campo técnico.
            value (any): Nuevo valor.

        Returns:
            dict: { 'success': bool, 'message': str }
        """
        # ── Validación de seguridad (mismo grupo que la vista) ──
        if not request.env.user.has_group('permisos_usuarios.group_administrador'):
            return {'success': False, 'message': 'No tiene permisos para realizar esta acción.'}

        try:
            producto = request.env['product.product'].sudo().browse(int(product_id))
            if not producto.exists():
                return {'success': False, 'message': 'El producto no existe.'}

            # ── Lógica específica por campo ──

            if field == 'name':
                if not value or not str(value).strip():
                    return {'success': False, 'message': 'El nombre es obligatorio.'}
                producto.write({'name': value})

            elif field == 'description_ecommerce':
                # El usuario pidió extraer/actualizar description_ecommerce
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
                try:
                    nueva_cantidad = float(value)
                    if nueva_cantidad < 0:
                        return {'success': False, 'message': 'La cantidad no puede ser negativa.'}

                    # Para actualizar stock en Odoo 15+, buscamos el quant.
                    location = request.env['stock.location'].sudo().search([
                        ('usage', '=', 'internal')
                    ], limit=1)

                    if not location:
                        return {'success': False, 'message': 'No se encontró una ubicación de inventario válida.'}

                    Quant = request.env['stock.quant'].sudo().with_context(inventory_mode=True)
                    quant = Quant.search([
                        ('product_id', '=', producto.id),
                        ('location_id', '=', location.id)
                    ], limit=1)

                    if quant:
                        quant.write({'inventory_quantity': nueva_cantidad})
                    else:
                        Quant.create({
                            'product_id': producto.id,
                            'location_id': location.id,
                            'inventory_quantity': nueva_cantidad,
                        })
                except (ValueError, TypeError):
                    return {'success': False, 'message': 'Cantidad no válida.'}

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

            else:
                return {'success': False, 'message': 'Campo no soportado para edición.'}

            return {'success': True, 'message': 'Campo actualizado correctamente.'}

        except Exception as e:
            return {'success': False, 'message': f'Error interno: {str(e)}'}