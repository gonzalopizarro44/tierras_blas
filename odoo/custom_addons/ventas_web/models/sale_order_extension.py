"""
==============================================================================
Extensión de sale.order para ventas_web
==============================================================================

Agrega campos de control web y métodos helper:
- sales_origin: Origen de la venta (admin, cliente_web, otro)
- Métodos wrapper para operaciones comunes

La lógica de negocio está centralizada en sales_service.py
Este modelo solo extiende sale.order con campos y métodos auxiliares.

==============================================================================
"""

from odoo import models, fields, api


class SaleOrderExtension(models.Model):
    _inherit = 'sale.order'

    # Campo: Origen de la venta
    # Indica de dónde provino la orden: administrador, cliente web, etc.
    sales_origin = fields.Selection(
        selection=[
            ('admin', 'Creado por Administrador'),
            ('cliente_web', 'Cliente Web'),
            ('integracion', 'Integración Externa'),
            ('otro', 'Otro'),
        ],
        string='Origen de la Venta',
        default='admin',
        help='Indica el origen o canal de donde provino la orden de venta.'
    )

    # El campo journal_id es heredado de sale.order (account.journal)
    # No se redefine aquí; se usa el estándar de Odoo

    # ════════════════════════════════════════════════════════════════════════════
    # MÉTODOS HELPER - Wrappers alrededor de métodos estándar
    # ════════════════════════════════════════════════════════════════════════════

    def action_confirm_web(self):
        """
        Wrapper web-friendly de action_confirm().
        
        Utiliza el flujo estándar de Odoo pero retorna el resultado
        de forma más controlada para uso desde el servicio.
        
        Returns:
            bool: True si se confirmó exitosamente
        """
        try:
            self.action_confirm()
            return True
        except Exception as e:
            print(f"[VENTAS_WEB] Error en action_confirm_web para {self.name}: {str(e)}")
            return False

    def action_cancel_web(self):
        """
        Wrapper web-friendly de action_cancel().
        
        Revierte movimientos de stock si la orden estaba confirmada.
        
        Returns:
            bool: True si se canceló exitosamente
        """
        try:
            self.action_cancel()
            return True
        except Exception as e:
            print(f"[VENTAS_WEB] Error en action_cancel_web para {self.name}: {str(e)}")
            return False

    @api.model
    def get_sale_count_by_origin(self):
        """
        Obtiene el conteo de órdenes agrupadas por origen.
        
        Útil para reportes y dashboard.
        
        Returns:
            dict: {'admin': 5, 'cliente_web': 3, ...}
        """
        origins = self.env['sale.order'].search_read(
            domain=[],
            fields=['sales_origin'],
            group_by='sales_origin'
        )
        
        result = {}
        for group in origins:
            origin = group.get('sales_origin', 'otro')
            count = group.get('__count', 0)
            result[origin] = count
        
        return result

    def get_formatted_origin(self):
        """
        Retorna el origen de la venta con etiqueta legible.
        
        Returns:
            str: Label legible del origen
        """
        origin_labels = {
            'admin': 'Creado por Administrador',
            'cliente_web': 'Cliente Web',
            'integracion': 'Integración Externa',
            'otro': 'Otro',
        }
        return origin_labels.get(self.sales_origin, 'Desconocido')
