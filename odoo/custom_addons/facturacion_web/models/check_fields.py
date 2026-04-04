import logging
from odoo import models, api

class CheckFields(models.AbstractModel):
    _name = 'check.fields'
    
    @api.model
    def check_arca_fields(self):
        Move = self.env['account.move']
        fields = Move._fields.keys()
        arca_fields = [f for f in fields if 'l10n_ar' in f or 'afip' in f]
        return arca_fields
