/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.PanelWeb = publicWidget.Widget.extend({
    selector: '.container-liquid',
    events: {
        'click .metric-card': '_onMetricCardClick',
        'click .btn-pagination': '_onPaginationClick',
    },

    init: function () {
        this._super.apply(this, arguments);
        console.log("PanelWeb Widget Init");
    },

    /**
     * @override
     */
    start: function () {
        console.log("PanelWeb Widget Start - Selector found:", this.$el.length);
        this._initCharts();
        this._initModal();
        // Ensure metric cards with config have pointer cursor (though already in CSS)
        this.$('.metric-card').each((idx, el) => {
            const metricKey = $(el).data('metric');
            if (this._getMetricasConfig()[metricKey]) {
                $(el).css('cursor', 'pointer');
            }
        });
        return this._super.apply(this, arguments);
    },

    // ═══════════════════════════════════════════════════════════════
    // CONFIGURACIÓN
    // ═══════════════════════════════════════════════════════════════
    _getMetricasConfig: function() {
        return {
            'sin-stock': {
                title: '❌ Productos Sin Stock',
                endpoint: '/panel/api/productos-sin-stock',
                columns: ['Nombre', 'Stock', 'SKU']
            },
            'bajo-stock': {
                title: '⚠️ Productos con Stock Bajo',
                endpoint: '/panel/api/productos-bajo-stock',
                columns: ['Nombre', 'Stock', 'SKU']
            },
            'total-ventas': {
                title: '📦 Detalles de Ventas',
                endpoint: '/panel/api/detalles-ventas',
                columns: ['Número', 'Cliente', 'Monto', 'Fecha', 'Estado']
            },
            'total-compras': {
                title: '🛒 Detalles de Compras',
                endpoint: '/panel/api/detalles-compras',
                columns: ['Número', 'Proveedor', 'Monto', 'Fecha', 'Estado']
            },
            'ingresos': {
                title: '💵 Detalles de Ingresos',
                endpoint: '/panel/api/detalles-ventas',
                columns: ['Número', 'Cliente', 'Monto', 'Fecha', 'Estado']
            },
            'gastos': {
                title: '💸 Detalles de Gastos',
                endpoint: '/panel/api/detalles-compras',
                columns: ['Número', 'Proveedor', 'Monto', 'Fecha', 'Estado']
            },
            'productos-activos': {
                title: '📋 Listado de Productos Activos',
                endpoint: '/panel/api/productos-activos',
                columns: ['Nombre', 'Categoría', 'Precio', 'Stock']
            },
            'ganancia-neta': {
                title: '💹 Análisis de Ganancia (Ventas)',
                endpoint: '/panel/api/detalles-ventas',
                columns: ['Número', 'Cliente', 'Monto', 'Fecha', 'Estado']
            }
        };
    },

    // ═══════════════════════════════════════════════════════════════
    // MÉTODOS DE INICIALIZACIÓN
    // ═══════════════════════════════════════════════════════════════
    _initCharts: function() {
        console.log("Initializing charts...");
        let graficos_data = {
            ventas_por_categoria: { labels: [], data: [] },
            evolucion_ventas: { labels: [], data: [] }
        };

        try {
            const graficosElement = document.getElementById('graficos_data_json');
            if (graficosElement) {
                const rawData = graficosElement.textContent;
                graficos_data = JSON.parse(rawData);
                console.log("Graficos data loaded:", graficos_data);
            }
        } catch (e) {
            console.error('Error parsing graficos_data:', e);
        }

        const chartCategoriasEl = document.getElementById('chartCategorias');
        if (chartCategoriasEl) {
            console.log("Creating chartCategorias...");
            new Chart(chartCategoriasEl.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: graficos_data.ventas_por_categoria.labels,
                    datasets: [{
                        label: 'Monto ($)',
                        data: graficos_data.ventas_por_categoria.data,
                        backgroundColor: '#166534',
                        borderColor: '#0f4620',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });
        }

        const chartEvolucionEl = document.getElementById('chartEvolucion');
        if (chartEvolucionEl) {
            console.log("Creating chartEvolucion...");
            new Chart(chartEvolucionEl.getContext('2d'), {
                type: 'line',
                data: {
                    labels: graficos_data.evolucion_ventas.labels,
                    datasets: [{
                        label: 'Ventas ($)',
                        data: graficos_data.evolucion_ventas.data,
                        borderColor: '#166534',
                        backgroundColor: 'rgba(22,101,52,0.1)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: true, position: 'top' }
                    },
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });
        }
    },

    _initModal: function() {
        console.log("Initializing modal...");
        this.$modal = this.$('#modalDetalles');
        if (this.$modal.length) {
            this.bootstrapModal = new bootstrap.Modal(this.$modal[0]);
            this.$modalBody = this.$modal.find('#modalBody');
            this.$modalTitle = this.$modal.find('#modalTitle');
            console.log("Modal elements found and initialized.");
        } else {
            console.error("Modal element #modalDetalles not found. Metric details will not work.");
        }
    },

    // ═══════════════════════════════════════════════════════════════
    // HANDLERS DE EVENTOS
    // ═══════════════════════════════════════════════════════════════
    _onMetricCardClick: function(ev) {
        const metricKey = $(ev.currentTarget).data('metric');
        console.log("Metric Card Clicked:", metricKey);
        if (this._getMetricasConfig()[metricKey]) {
            this._cargarDetallesMetrica(metricKey);
        } else {
            console.log('Métrica sin configuración de detalle:', metricKey);
        }
    },

    _onPaginationClick: function(ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);
        const $pagination = $btn.closest('.pagination');
        
        const newPage = parseInt($btn.data('page'));
        const endpoint = $pagination.data('endpoint');
        const metricKey = $pagination.data('metric');
        // Parse columns from string to array
        const columns = JSON.parse($pagination.data('columns'));
        const fechaDesde = $pagination.data('fecha-desde');
        const fechaHasta = $pagination.data('fecha-hasta');

        console.log(`Pagination Clicked: Page ${newPage} for metric ${metricKey}`);
        this._cargarPaginaDetalle(endpoint, newPage, columns, metricKey, fechaDesde, fechaHasta);
    },

    // ═══════════════════════════════════════════════════════════════
    // LÓGICA DE NEGOCIO
    // ═══════════════════════════════════════════════════════════════
    _cargarDetallesMetrica: function(metricKey) {
        const config = this._getMetricasConfig()[metricKey];
        if (!config || !this.$modal || !this.$modalBody || !this.$modalTitle) {
            console.warn("No config or modal elements found for metric:", metricKey);
            return;
        }

        this.$modalTitle.text(config.title);
        this.$modalBody.html('<div class="modal-loading"><div class="spinner-border"></div></div>');
        this.bootstrapModal.show();
        console.log(`Loading details for metric: ${metricKey}`);

        const fechaDesdeInput = document.querySelector('input[name="fecha_desde"]');
        const fechaHastaInput = document.querySelector('input[name="fecha_hasta"]');
        const fechaDesde = fechaDesdeInput ? fechaDesdeInput.value : '';
        const fechaHasta = fechaHastaInput ? fechaHastaInput.value : '';
        
        this._cargarPaginaDetalle(config.endpoint, 1, config.columns, metricKey, fechaDesde, fechaHasta);
    },

    _cargarPaginaDetalle: function(endpoint, page, columns, metricKey, fechaDesde, fechaHasta) {
        const params = new URLSearchParams();
        params.append('page', page);
        params.append('limit', 10);
        
        if (fechaDesde && ['total-ventas', 'total-compras', 'ingresos', 'gastos', 'ganancia-neta'].includes(metricKey)) {
            params.append('fecha_desde', fechaDesde);
            params.append('fecha_hasta', fechaHasta);
        }
        
        const url = `${endpoint}?${params.toString()}`;
        console.log("Fetching URL:", url);

        fetch(url)
            .then(response => {
                if (!response.ok) throw new Error('Error en la respuesta del servidor');
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    this.$modalBody.html(`<div class="modal-empty"><p>Error: ${data.error}</p></div>`);
                    console.error("API Error:", data.error);
                    return;
                }
                this._renderizarTabla(data, page, columns, metricKey, endpoint, fechaDesde, fechaHasta);
            })
            .catch(error => {
                console.error('Fetch Error:', error);
                this.$modalBody.html('<div class="modal-empty"><p>Error al cargar los datos. Por favor reintente.</p></div>');
            });
    },

    _renderizarTabla: function(data, page, columns, metricKey, endpoint, fechaDesde, fechaHasta) {
        console.log("Rendering table for metric:", metricKey, "page:", page);
        let html = '<div class="table-responsive">';
        html += '<table class="modal-table">';
        html += '<thead><tr>';
        
        columns.forEach(col => {
            html += `<th>${col}</th>`;
        });
        html += '</tr></thead><tbody>';

        if (data.items && data.items.length > 0) {
            data.items.forEach(item => {
                html += '<tr>';
                
                if (metricKey === 'sin-stock' || metricKey === 'bajo-stock') {
                    html += `<td>${item.nombre || '-'}</td>`;
                    html += `<td><strong>${item.stock || '0'}</strong></td>`;
                    html += `<td>${item.sku || '-'}</td>`;
                } else if (['total-ventas', 'ingresos', 'ganancia-neta'].includes(metricKey)) {
                    const monto = parseFloat(item.monto || 0);
                    html += `<td>${item.numero || '-'}</td>`;
                    html += `<td>${item.cliente || '-'}</td>`;
                    html += `<td>$${monto.toFixed(2)}</td>`;
                    html += `<td>${item.fecha || '-'}</td>`;
                    html += `<td><span class="badge bg-info">${item.estado || '-'}</span></td>`;
                } else if (['total-compras', 'gastos'].includes(metricKey)) {
                    const monto = parseFloat(item.monto || 0);
                    html += `<td>${item.numero || '-'}</td>`;
                    html += `<td>${item.proveedor || '-'}</td>`;
                    html += `<td>$${monto.toFixed(2)}</td>`;
                    html += `<td>${item.fecha || '-'}</td>`;
                    html += `<td><span class="badge bg-warning">${item.estado || '-'}</span></td>`;
                } else if (metricKey === 'productos-activos') {
                    const precio = parseFloat(item.precio || 0);
                    html += `<td>${item.nombre || '-'}</td>`;
                    html += `<td>${item.categoria || '-'}</td>`;
                    html += `<td>$${precio.toFixed(2)}</td>`;
                    html += `<td><strong>${item.stock || '0'}</strong></td>`;
                }
                
                html += '</tr>';
            });
        } else {
            html += `<tr><td colspan="${columns.length}" class="text-center text-muted py-4">No hay datos disponibles</td></tr>`;
        }

        html += '</tbody></table></div>';

        if (data.total_pages > 1) {
            html += this._generarPaginacion(data, page, endpoint, metricKey, columns, fechaDesde, fechaHasta);
        }

        this.$modalBody.html(html);
    },

    _generarPaginacion: function(data, page, endpoint, metricKey, columns, fechaDesde, fechaHasta) {
        console.log("Generating pagination...");
        let html = '<nav class="modal-pagination">';
        html += `<ul class="pagination" data-endpoint="${endpoint}" data-metric="${metricKey}" data-columns='${JSON.stringify(columns)}' data-fecha-desde="${fechaDesde}" data-fecha-hasta="${fechaHasta}">`;

        if (page > 1) {
            html += `<li class="page-item"><a class="page-link btn-pagination" href="#" data-page="${page - 1}">← Anterior</a></li>`;
        }

        let startPage = Math.max(1, page - 2);
        let endPage = Math.min(data.total_pages, page + 2);

        if (startPage > 1) {
            html += '<li class="page-item"><a class="page-link btn-pagination" href="#" data-page="1">1</a></li>';
            if (startPage > 2) html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }

        for (let i = startPage; i <= endPage; i++) {
            const active = i === page ? 'active' : '';
            html += `<li class="page-item ${active}"><a class="page-link btn-pagination" href="#" data-page="${i}">${i}</a></li>`;
        }

        if (endPage < data.total_pages) {
            if (endPage < data.total_pages - 1) html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
            html += `<li class="page-item"><a class="page-link btn-pagination" href="#" data-page="${data.total_pages}">${data.total_pages}</a></li>`;
        }

        if (page < data.total_pages) {
            html += `<li class="page-item"><a class="page-link btn-pagination" href="#" data-page="${page + 1}">Siguiente →</a></li>`;
        }

        html += '</ul></nav>';
        html += `<p class="text-center text-muted small" style="margin-top: 1rem;">Mostrando ${((page - 1) * 10 + 1)} a ${Math.min(page * 10, data.total)} de ${data.total} registros</p>`;
        
        return html;
    }
});

export default publicWidget.registry.PanelWeb;

