warning: in the working copy of 'odoo/custom_addons/custom_signup_flow/__manifest__.py', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/odoo/custom_addons/custom_signup_flow/__manifest__.py b/odoo/custom_addons/custom_signup_flow/__manifest__.py[m
[1mindex 84f31fc..bac2acd 100644[m
[1m--- a/odoo/custom_addons/custom_signup_flow/__manifest__.py[m
[1m+++ b/odoo/custom_addons/custom_signup_flow/__manifest__.py[m
[36m@@ -2,6 +2,7 @@[m
     'name': 'Custom Signup Flow',[m
     'version': '1.0',[m
     'summary': 'Custom registration flow with DNI and activation via reset password.',[m
[32m+[m[32m    'author': 'Gonzalo Pizarro',[m
     'description': 'Modifies the signup flow to require DNI and set password via email.',[m
     'category': 'Website/Website',[m
     'depends': ['auth_signup', 'website'],[m
[1mdiff --git a/odoo/custom_addons/tienda_web/README.md b/odoo/custom_addons/tienda_web/README.md[m
[1mindex 78ad0d0..13a905c 100644[m
[1m--- a/odoo/custom_addons/tienda_web/README.md[m
[1m+++ b/odoo/custom_addons/tienda_web/README.md[m
[36m@@ -40,7 +40,7 @@[m [mMódulo custom para personalizar la tienda online (/shop) de Odoo 19 con las sig[m
 - Se ocultó por consistencia y simplicidad de interfaz[m
 - Está comentado para poder reactivarse[m
 [m
[31m----[m
[32m+[m[32m___[m
 [m
 ## Configuración Rápida[m
 [m
[36m@@ -68,9 +68,9 @@[m [mY descomenta ambas (quita los `//`):[m
 window.open(urlBot, '_blank');[m
 ```[m
 [m
[31m----[m
[32m+[m[32m___[m
 [m
[31m----[m
[32m+[m[32m___[m
 [m
 ## Para Reactivar Elementos[m
 [m
[36m@@ -98,7 +98,7 @@[m [mwindow.open(urlBot, '_blank');[m
 3. Por ahora está simplemente ocultado con `d-none`, no comentado[m
 4. Para reactivar, comenta o elimina el atributo `d-none`[m
 [m
[31m----[m
[32m+[m[32m___[m
 [m
 ## Estructura del Módulo[m
 [m
[36m@@ -113,7 +113,7 @@[m [mtienda_web/[m
     └── tienda_template.xml   # Todas las personalizaciones[m
 ```[m
 [m
[31m----[m
[32m+[m[32m___[m
 [m
 ## Detalle de Cambios Técnicos[m
 [m
[36m@@ -156,12 +156,12 @@[m [mtienda_web/[m
 - **Función 2**: `solicitarCotizacionDetail(event)` - Para página de detalles[m
 - Ambas comparten la misma lógica, solo diferencia en cómo obtienen los datos del producto[m
 [m
[31m----[m
[32m+[m[32m___[m
 [m
 ## 📋 Resumen de Seguridad - 6 Vulnerabilidades Cerradas[m
 [m
 | # | Elemento | Estado | Ubicación | Tipo |[m
[31m-|---|---|---|---|---|[m
[32m+[m[32m|___|___|___|___|___|[m
 | 1 | **Agregar al carrito** (tarjetas) | ✅ Comentado | /shop | Botón de compra |[m
 | 2 | **Agregar al carrito** (detalles) | ✅ Comentado | /shop/producto-xxx | Botón de compra |[m
 | 3 | **Quick Reorder** | ✅ Oculto | /shop/cart | Atajo compra rápida |[m
[36m@@ -171,7 +171,7 @@[m [mtienda_web/[m
 [m
 **Resultado**: Los usuarios **SOLO pueden solicitar cotizaciones** a través del botón dedicado. Todos los caminos para comprar directamente han sido cerrados. 🔒[m
 [m
[31m----[m
[32m+[m[32m___[m
 [m
 ## Notas Técnicas[m
 [m
[36m@@ -180,7 +180,7 @@[m [mtienda_web/[m
 - **JavaScript**: Se inyecta en cada página del sitio web mediante la plantilla `website.layout`[m
 - **Dependencias**: Requiere `website_sale` activo en Odoo[m
 [m
[31m----[m
[32m+[m[32m___[m
 [m
 ## Soporte[m
 [m
[1mdiff --git a/odoo/custom_addons/tienda_web/__manifest__.py b/odoo/custom_addons/tienda_web/__manifest__.py[m
[1mindex 5eaf3f8..3bcf1cd 100644[m
[1m--- a/odoo/custom_addons/tienda_web/__manifest__.py[m
[1m+++ b/odoo/custom_addons/tienda_web/__manifest__.py[m
[36m@@ -10,11 +10,9 @@[m
         'website_sale',[m
         'product',[m
     ],[m
[31m-[m
     'data': [[m
         'views/tienda_template.xml',[m
     ],[m
[31m-[m
     'installable': True,[m
     'application': False,[m
 }[m
[1mdiff --git a/odoo/custom_addons/tienda_web/views/tienda_template.xml b/odoo/custom_addons/tienda_web/views/tienda_template.xml[m
[1mindex 0e85669..6c0822f 100644[m
[1m--- a/odoo/custom_addons/tienda_web/views/tienda_template.xml[m
[1m+++ b/odoo/custom_addons/tienda_web/views/tienda_template.xml[m
[36m@@ -11,9 +11,7 @@[m
              2. El botón original está comentado para poder reactivarlo fácilmente[m
              [m
              PLANTILLA HEREDADA: website_sale.shop_product_buttons[m
[31m-             (Ubicación: /odoo/addons/website_sale/views/product_tile_templates.xml)[m
[31m-        -->[m
[31m-        [m
[32m+[m[32m             (Ubicación: /odoo/addons/website_sale/views/product_tile_templates.xml) -->[m
         <template id="tienda_web_shop_product_buttons" inherit_id="website_sale.shop_product_buttons">[m
             [m
             <!-- Buscar y reemplazar el botón principal (Add to Cart) -->[m
[36m@@ -96,13 +94,9 @@[m
                        data-animation-selector=".o_wsale_product_images">[m
                         <i class="fa fa-shopping-cart me-2"/>[m
                         Add to cart[m
[31m-                    </a>[m
[31m-                     [m
[31m-                -->[m
[31m-                [m
[32m+[m[32m                    </a> -->[m
             </xpath>[m
         </template>[m
[31m-[m
         <!-- ═══════════════════════════════════════════════════════════════════════════[m
              PERSONALIZACIÓN: Ocultar botón "Quick Reorder" [m
              ═══════════════════════════════════════════════════════════════════════════[m
[36m@@ -113,11 +107,8 @@[m
              directamente), este botón debe estar deshabilitado.[m
              [m
              HEREDADA DE: website_sale.quick_reorder_button[m
[31m-             (Ubicación: /odoo/addons/website_sale/views/templates.xml:3124)[m
[31m-        -->[m
[31m-        [m
[32m+[m[32m             (Ubicación: /odoo/addons/website_sale/views/templates.xml:3124) -->[m
         <template id="tienda_web_quick_reorder_button" inherit_id="website_sale.quick_reorder_button">[m
[31m-            [m
             <!-- Reemplazar todo el contenido con un comentario deshabilitado -->[m
             <xpath expr="//span[@t-att-title='quick_reorder_button_title']" position="replace">[m
                 [m
[36m@@ -142,10 +133,7 @@[m
                         >[m
                             <i class="fa fa-rotate-left me-2"/>Quick reorder[m
                         </button>[m
[31m-                    </span>[m
[31m-                     [m
[31m-                -->[m
[31m-                [m
[32m+[m[32m                    </span> -->[m
             </xpath>[m
         </template>[m
 [m
