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

---

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

---

## Para Reactivar el Carrito

Si en algún momento quieres reactivar el botón "Agregar al carrito":

### En Tarjetas de Producto (/shop)
1. Abre: `views/tienda_template.xml`
2. Busca: "BOTÓN: AGREGAR AL CARRITO (COMENTADO - DESHABILITADO)" (primera sección)
3. Descomenta ese bloque (`<!-- -->`)
4. Comenta o elimina el botón "Solicitar cotización" de arriba

### En Página de Detalles (/shop/producto-xxx)
1. Abre: `views/tienda_template.xml`
2. Busca: "BOTÓN: AGREGAR AL CARRITO (COMENTADO - DESHABILITADO)" (segunda sección)
3. Descomenta ese bloque (`<!-- -->`)
4. Comenta o elimina el botón "Solicitar cotización" de arriba

---

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

---

## Detalle de Cambios Técnicos

### Plantilla 1: `tienda_web_shop_product_buttons` (Tarjetas)
- **Heredada de**: `website_sale.shop_product_buttons`
- **XPath**: Busca botón con clase `o_wsale_product_btn_primary`
- **Ubicación en Odoo**: `/odoo/addons/website_sale/views/product_tile_templates.xml:220`

### Plantilla 2: `tienda_web_cta_wrapper` (Página de Detalles)
- **Heredada de**: `website_sale.cta_wrapper`
- **XPath**: Busca elemento con id `add_to_cart`
- **Ubicación en Odoo**: `/odoo/addons/website_sale/views/templates.xml:2315`

### Scripts JavaScript
- **Función 1**: `solicitarCotizacion(element)` - Para tarjetas
- **Función 2**: `solicitarCotizacionDetail(event)` - Para página de detalles
- Ambas comparten la misma lógica, solo diferencia en cómo obtienen los datos del producto

---

## Notas Técnicas

- **Heredancia**: El módulo hereda de plantillas estándar de Odoo (no las reemplaza)
- **XPath personalizado**: Usa selectores robustos con `contains()` para mayor compatibilidad
- **JavaScript**: Se inyecta en cada página del sitio web mediante la plantilla `website.layout`
- **Dependencias**: Requiere `website_sale` activo en Odoo

---

## Soporte

- Para cualquier modificación futura, edita `views/tienda_template.xml`
- Los cambios se aplican automáticamente al reiniciar el servidor Odoo
- Si tienes dudas, revisa los comentarios dentro del archivo XML (bastante detallados)
