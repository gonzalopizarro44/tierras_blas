"""
==============================================================================
Extensión de sale.order para ventas_web
==============================================================================

Agrega campos de control web:
- sales_origin: Origen de la venta (admin, cliente_web, otro)
- journal_id: Método de pago (reutiliza campo estándar de Odoo)

La confirmación automática ocurre en el controller cuando se crea una orden.
==============================================================================
"""

from odoo import models, fields


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

    # Campo: Método de pago
    # Usa el campo journal_id estándar de Odoo (account.journal)
    # Si es necesario expandir, se puede hacer aquí
    # Por ahora, se mantiene el journal_id nativo

    def _confirmar_automaticamente(self):
        """
        Confirma automáticamente la orden y descuenta stock.
        
        Esto se llama desde el controller cuando se crea una nueva orden.
        Usa el flujo estándar de Odoo:
        - action_confirm() → Confirma la orden
        - Genera movimientos de stock automáticamente
        """
        for orden in self:
            if orden.state == 'draft':
                try:
                    # Ejecutar confirmación estándar de Odoo
                    orden.action_confirm()
                except Exception as e:
                    # Log silencioso; la orden queda en draft si falla
                    print(f"[VENTAS_WEB] Error al confirmar orden {orden.name}: {str(e)}")
