/** @odoo-module **/
const WHATSAPP_NUMBER = "+5492612404565";
window.contactWhatsApp = function (element) {
    const productName = element.getAttribute('data-product-name') || 'el producto';
    const message = `Hola, estoy interesado en recibir una cotización del siguiente producto: ${productName}. Muchas gracias.`;
    const whatsappUrl = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(message)}`;
    window.open(whatsappUrl, '_blank');
    return false;
};
// Asegurar que las imágenes tengan un alto consistente si no se cargan correctamente
document.addEventListener('DOMContentLoaded', function () {
    const images = document.querySelectorAll('.card-img-top');
    images.forEach(img => {
        img.onerror = function () {
            this.src = '/web/static/img/placeholder.png';
        };
    });
});