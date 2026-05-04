"""
==============================================================================
Extensión de sale.order para presupuesto_web
==============================================================================

Agrega el campo presupuesto_origin a sale.order para distinguir
las cotizaciones creadas desde el módulo de presupuestos web.

==============================================================================
"""

from odoo import models, fields


class SaleOrderPresupuestoExtension(models.Model):
    _inherit = 'sale.order'

    # Campo: Origen del presupuesto
    # Si es 'presupuesto_web', se muestra en el panel de presupuestos.
    # Las ventas normales no tienen este campo seteado.
    presupuesto_origin = fields.Char(
        string='Origen Presupuesto',
        default='',
        help='Si es "presupuesto_web", esta cotización fue creada desde el módulo de presupuestos web.',
    )
