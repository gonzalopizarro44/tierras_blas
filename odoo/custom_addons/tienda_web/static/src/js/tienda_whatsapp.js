/** @odoo-module **/

const WHATSAPP_NUMBER = "5492612404565";

/**
 * Redirige a WhatsApp con el nombre del producto.
 * Usada en las tarjetas de /shop (onclick en el botón).
 */
window.consultarWhatsApp = function (element) {
    const productName = element.getAttribute('data-product-name') || 'el producto';
    const mensaje = `Hola, solicito información de: ${productName}`;
    window.open(
        'https://wa.me/' + WHATSAPP_NUMBER + '?text=' + encodeURIComponent(mensaje),
        '_blank'
    );
};

/**
 * Redirige a WhatsApp desde la página de detalle del producto.
 * Usada en el botón de /shop/<producto>.
 */
window.consultarWhatsAppDetail = function (event) {
    event.preventDefault();
    const button = event.currentTarget;
    const productName = button.getAttribute('data-product-name') || 'el producto';
    const mensaje = `Hola, solicito información de: ${productName}`;
    window.open(
        'https://wa.me/' + WHATSAPP_NUMBER + '?text=' + encodeURIComponent(mensaje),
        '_blank'
    );
    return false;
};