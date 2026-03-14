# Pendientes técnicos

## Acceso Denegado no renderiza correctamente

Problema:
Usuarios no admin no ven la página access_denied_template.
Odoo redirige a /web/login en lugar de renderizar la vista.

Estado:
Permisos funcionan correctamente.
Pendiente revisar renderizado de template QWeb en controlador.

Fecha:
14/03/2026