# -*- coding: utf-8 -*-
"""
==============================================================================
EXTENSIÓN DE MODELO: product.template y product.product
==============================================================================

Añade el campo personalizado x_costo_usd para registrar el costo en USD
de forma separada del costo de valuación de Odoo.

Campo: x_costo_usd
- Tipo: Float (precisión 2 decimales)
- Label: "Costo USD"
- Descripción: Valor de costo en USD (referencia informativa)
- Editable: Sí (desde vistas y formularios)
- Almacenado en BD: Sí

Uso:
- Se actualiza automáticamente desde el formulario de compras
- Se visualiza en el panel de inventario
- Se utiliza para llevar un registro del costo en USD del último costo comprado

==============================================================================
"""

from odoo import models, fields


class ProductTemplateExtension(models.Model):
    """Extiende product.template con campo de costo en USD"""
    
    _inherit = 'product.template'

    x_costo_usd = fields.Float(
        string='Costo USD',
        digits=(12, 2),
        help='Costo del producto en USD (válido para productos tipo "Producto")',
        tracking=True,  # Registra cambios en chatter
    )
    

class ProductProductExtension(models.Model):
    """Extiende product.product con campo de costo en USD"""
    
    _inherit = 'product.product'

    # El campo x_costo_usd se hereda automáticamente de product.template
    # No es necesario redefinirlo aquí
    # solo se declara en product.template
