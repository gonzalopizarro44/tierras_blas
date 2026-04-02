# Tienda Web Personalizada

## Descripción
Módulo custom para personalizar la tienda online (/shop) de Odoo 19 con las siguientes funcionalidades:

### Cambios Implementados

#### 1. ✅ Botón "Solicitar cotización" (NUEVO)
- Aparece en cada tarjeta de producto en la tienda
- Muestra una alerta temporal (mientras no tengas el # de Martín)
- Cuando tengas el número de WhatsApp de Martín, redirige automáticamente a WhatsApp

#### 2. ✅ Botón "Agregar al carrito" (DESHABILITADO)
- Está **comentado** en las vistas (no eliminado)
- Fácil de reactivar descomenando el código
- Ubicación: [tienda_template.xml](views/tienda_template.xml#L48)

---

## Configuración Rápida

### Paso 1: Obtener número de Martín
Cuando tengas el número de WhatsApp de Martín, busca esta línea en `views/tienda_template.xml`:

```javascript
const MARTIN_WHATSAPP_NUMBER = "";
```

Y reemplazala con (ejemplo):
```javascript
const MARTIN_WHATSAPP_NUMBER = "34666666666";  // Código país + número (sin +)
```

### Paso 2: Habilitar redirección a WhatsApp
En el mismo archivo, busca esta línea (alrededor de la 93):

```javascript
// window.open(urlBot, '_blank');
```

Y descomenta:
```javascript
window.open(urlBot, '_blank');
```

---

## Para Reactivar el Carrito

Si en algún momento quieres reactivar el botón "Agregar al carrito":

1. Abre: `views/tienda_template.xml`
2. Busca el bloque comentado de "BOTÓN: AGREGAR AL CARRITO"
3. Descomenta ese bloque
4. Comenta o elimina el botón "Solicitar cotización"

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
    └── tienda_template.xml   # Vistas personalizadas
```

---

## Notas Técnicas

- **Heredancia**: El módulo hereda de `website_sale.shop_product_buttons` (plantilla estándar de Odoo)
- **XPath personalizado**: Busca el botón por su clase CSS: `o_wsale_product_btn_primary`
- **JavaScript**: La función `solicitarCotizacion()` se inyecta en cada página del sitio web
- **Dependencias**: Requiere `website_sale` activo en Odoo

---

## Soporte

- Para cualquier modificación futura, edita `views/tienda_template.xml`
- Los cambios se aplican automáticamente al reiniciar el servidor Odoo
