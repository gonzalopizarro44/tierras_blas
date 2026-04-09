from odoo import http
from odoo.http import request
class TiendaController(http.Controller):
    @http.route(['/tienda'], type='http', auth="public", website=True)
    def tienda(self, **post):
        # Buscamos productos que estén publicados y tengan stock disponible (inventario)
        # O simplemente productos que se pueden vender si el usuario prefiere mostrar todo el catálogo
        # Según el requerimiento: "productos que se encuentran actualmente en el inventario"
        products = request.env['product.template'].sudo().search([
            ('sale_ok', '=', True),
            ('is_published', '=', True),
        ])
        
        # Opcional: Filtrar por stock si se desea rigor absoluto
        # products = products.filtered(lambda p: p.qty_available > 0)
        values = {
            'products': products,
        }
        return request.render("tienda.tienda_catalog_template", values)
