# -*- coding: utf-8 -*-
from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'
    # Campo agregado por compatibilidad con la base de datos para evitar errores de UndefinedColumn
    dni = fields.Char(string="DNI")
