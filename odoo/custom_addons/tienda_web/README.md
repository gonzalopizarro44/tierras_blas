# Tienda Web Personalizada

## Descripción
Módulo custom para personalizar la tienda online (/shop) de Odoo 19 con las siguientes funcionalidades:

### Cambios Implementados

#### 1. ✅ Botón "Solicitar cotización" (NUEVO)
- Aparece en **tarjetas de producto** en la tienda (/shop)
- Aparece en **página de detalles** del producto (/shop/producto-xxx)
- Muestra una alerta temporal (mientras no tengas el # de Martín)
- Cuando tengas el número de WhatsApp de Martín, redirige automáticamente a WhatsApp

#### 2. ✅ Botón "Agregar al carrito" (DESHABILITADO)
- Está **comentado** en las vistas (no eliminado)
- **Dos ubicaciones comentadas**:
  1. En tarjetas de producto (`tienda_template.xml` línea ~48)
  2. En página de detalles (`tienda_template.xml` línea ~70)
- Fácil de reactivar descomenando el código

#### 3. ✅ Botón "Quick Reorder" (DESHABILITADO Y OCULTO)
- Este botón permitía acceder al carrito y listar productos (vulnerabilidad de seguridad)
- Ha sido **completamente ocultado** 
- Ubicación: En el encabezado de "Order summary" del carrito
- Está comentado y puede reactivarse si es necesario (aunque no recomendado)

#### 4. ✅ Elemento `#product_option_block` (OCULTADO)
- Este elemento en la página de detalles contenía botones adicionales de opciones
- Ha sido **ocultado completamente** para evitar acceso al carrito
- Ubicación: En la página de detalles del producto (/shop/producto-xxx)

#### 5. ✅ Botón "Add to Cart" en Lista de Deseos (DESHABILITADO Y OCULTO)
- En /shop/wishlist, los productos mostraban un botón "Add to Cart"
- Esto permitía comprar productos directamente desde el wishlist
- Ha sido **completamente ocultado**
- Está comentado para poder reactivarse en el futuro

#### 6. ✅ Botón "Add to Wishlist" (DESHABILITADO Y OCULTO)
- En la página de detalles del producto aparecía el botón "Add to Wishlist"
- Se ocultó por consistencia y simplicidad de interfaz
- Está comentado para poder reactivarse

___

## Configuración Rápida

### Paso 1: Obtener número de Martín
Cuando tengas el número de WhatsApp de Martín, busca esta línea en `views/tienda_template.xml`:

```javascript
const MARTIN_WHATSAPP_NUMBER = "";
```

**Aparece DOS VECES** (una en cada función), reemplazala en ambos lugares con (ejemplo):
```javascript
const MARTIN_WHATSAPP_NUMBER = "34666666666";  // Código país + número (sin +)
```

### Paso 2: Habilitar redirección a WhatsApp
En el mismo archivo, busca estas líneas (aparecen DOS VECES también):

```javascript
// window.open(urlBot, '_blank');
```

Y descomenta ambas (quita los `//`):
```javascript
window.open(urlBot, '_blank');
```

___

___

## Para Reactivar Elementos

### Botón "Agregar al Carrito" (Tarjetas y Detalles)
1. Abre: `views/tienda_template.xml`
2. Busca: "BOTÓN: AGREGAR AL CARRITO (COMENTADO - DESHABILITADO)" (hay DOS)
3. Descomenta ese bloque
4. Comenta o elimina el botón "Solicitar cotización" correspondiente

### Botón "Add to Cart" en Wishlist
1. Abre: `views/tienda_template.xml`
2. Busca: "BOTÓN: ADD TO CART EN WISHLIST (DESHABILITADO Y OCULTO)"
3. Descomenta ese bloque

### Botón "Add to Wishlist"
1. En tarjetas: Ya fue comentado manualmente (según mencionaste)
2. En página de detalles:
   - Abre: `views/tienda_template.xml`
   - Busca: "BOTÓN: ADD TO WISHLIST EN DETALLES (DESHABILITADO Y OCULTO)"
   - Descomenta ese bloque

### Elemento `#product_option_block`
1. Abre: `views/tienda_template.xml`
2. Busca: template id="tienda_web_hide_product_option_block"
3. Por ahora está simplemente ocultado con `d-none`, no comentado
4. Para reactivar, comenta o elimina el atributo `d-none`

___

## Estructura del Módulo

```
tienda_web/
├── __manifest__.py           # Configuración del módulo
├── __init__.py               # Inicialización
├── README.md                 # Este archivo
├── controllers/
│   └── __init__.py
└── views/
    └── tienda_template.xml   # Todas las personalizaciones
```

___

## Detalle de Cambios Técnicos

### Plantilla 1: `tienda_web_shop_product_buttons` (Tarjetas)
- **Heredada de**: `website_sale.shop_product_buttons`
- **XPath**: Busca botón con clase `o_wsale_product_btn_primary`
- **Ubicación en Odoo**: `/odoo/addons/website_sale/views/product_tile_templates.xml:220`

### Plantilla 2: `tienda_web_cta_wrapper` (Página de Detalles)
- **Heredada de**: `website_sale.cta_wrapper`
- **XPath**: Busca elemento con id `add_to_cart`
- **Ubicación en Odoo**: `/odoo/addons/website_sale/views/templates.xml:2315`

### Plantilla 3: `tienda_web_quick_reorder_button` (Botón Quick Reorder)
- **Heredada de**: `website_sale.quick_reorder_button`
- **XPath**: Busca span con atributo `t-att-title='quick_reorder_button_title'`
- **Ubicación en Odoo**: `/odoo/addons/website_sale/views/templates.xml:3124`
- **Razón**: Permitía acceso al carrito (/shop/cart)

### Plantilla 4: `tienda_web_hide_product_option_block` (Ocultar product_option_block)
- **Heredada de**: `website_sale.cta_wrapper`
- **Método**: Añade clase CSS `d-none` al div con id `product_option_block`
- **Ubicación en Odoo**: `/odoo/addons/website_sale/views/templates.xml:2339`
- **Razón**: Contenía botones adicionales de opciones que permitían comprar

### Plantilla 5: `tienda_web_hide_wishlist_add_to_cart` (Ocultar botón en Wishlist)
- **Heredada de**: `website_sale_wishlist.product_wishlist`
- **XPath**: Busca botón con id `add_to_cart_button`
- **Ubicación en Odoo**: `/odoo/addons/website_sale_wishlist/views/website_sale_wishlist_template.xml:362`
- **Razón**: Permitía comprar directamente desde la lista de deseos

### Plantilla 6: `tienda_web_hide_wishlist_button` (Ocultar botón "Add to Wishlist")
- **Heredada de**: `website_sale_wishlist.product_add_to_wishlist`
- **XPath**: Busca elemento con atributo `data-action='o_wishlist'`
- **Ubicación en Odoo**: `/odoo/addons/website_sale_wishlist/views/website_sale_wishlist_template.xml:100`
- **Razón**: Simplificar interfaz, los usuarios solo solicitan cotizaciones

### Scripts JavaScript
- **Función 1**: `solicitarCotizacion(element)` - Para tarjetas
- **Función 2**: `solicitarCotizacionDetail(event)` - Para página de detalles
- Ambas comparten la misma lógica, solo diferencia en cómo obtienen los datos del producto

___

## 📋 Resumen de Seguridad - 6 Vulnerabilidades Cerradas

| # | Elemento | Estado | Ubicación | Tipo |
|___|___|___|___|___|
| 1 | **Agregar al carrito** (tarjetas) | ✅ Comentado | /shop | Botón de compra |
| 2 | **Agregar al carrito** (detalles) | ✅ Comentado | /shop/producto-xxx | Botón de compra |
| 3 | **Quick Reorder** | ✅ Oculto | /shop/cart | Atajo compra rápida |
| 4 | **#product_option_block** | ✅ Oculto | /shop/producto-xxx | Opciones adicionales |
| 5 | **Add to Cart** (wishlist) | ✅ Comentado | /shop/wishlist | Botón de compra |
| 6 | **Add to Wishlist** | ✅ Comentado | /shop/producto-xxx | Navegación compras |

**Resultado**: Los usuarios **SOLO pueden solicitar cotizaciones** a través del botón dedicado. Todos los caminos para comprar directamente han sido cerrados. 🔒

___

## Notas Técnicas

- **Heredancia**: El módulo hereda de plantillas estándar de Odoo (no las reemplaza)
- **XPath personalizado**: Usa selectores robustos con `contains()` para mayor compatibilidad
- **JavaScript**: Se inyecta en cada página del sitio web mediante la plantilla `website.layout`
- **Dependencias**: Requiere `website_sale` activo en Odoo

___

## Soporte

- Para cualquier modificación futura, edita `views/tienda_template.xml`
- Los cambios se aplican automáticamente al reiniciar el servidor Odoo
- Si tienes dudas, revisa los comentarios dentro del archivo XML (bastante detallados)
