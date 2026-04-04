/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.PanelWeb = publicWidget.Widget.extend({
    selector: '.panel-page',
    events: {
        'click .metric-card': '_onMetricCardClick',
        'click .btn-pagination': '_onPaginationClick',
    },

    init: function () {
        this._super.apply(this, arguments);
        console.log("%c[PanelWeb] Widget Init - Selector matched", "color: #166534; font-weight: bold");
    },

    /**
     * @override
     */
    start: function () {
        console.log("%c[PanelWeb] Widget Start - Selector found:", "color: #166534; font-weight: bold", this.$el.length);
        
        if (this.$el.length === 0) {
            console.error("%c[PanelWeb] ERROR: Selector '.panel-page' not found!", "color: #dc3545; font-weight: bold");
            return this._super.apply(this, arguments);
        }
        
        this._initCharts();
        this._initModal();
        
        // Ensure metric cards with config have pointer cursor
        const metricCards = this.$('.metric-card');
        console.log("%c[PanelWeb] Found metric cards:", "color: #166534", metricCards.length);
        
        metricCards.each((idx, el) => {
            const metricKey = $(el).data('metric');
            if (this._getMetricasConfig()[metricKey]) {
                $(el).css('cursor', 'pointer');
                console.log("%c[PanelWeb] Registered clickable card:", "color: #166534", metricKey);
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
                columns: ['Nombre', 'Stock', 'SKU'],
                renderFn: 'renderProductosSinStock'
            },
            'bajo-stock': {
                title: '⚠️ Productos con Stock Bajo',
                endpoint: '/panel/api/productos-bajo-stock',
                columns: ['Nombre', 'Stock', 'SKU'],
                renderFn: 'renderProductosBajoStock'
            },
            'total-ventas': {
                title: '📦 Detalles de Ventas',
                endpoint: '/panel/api/detalles-ventas',
                columns: ['Número', 'Cliente', 'Monto', 'Fecha', 'Estado'],
                renderFn: 'renderVentas'
            },
            'total-compras': {
                title: '🛒 Detalles de Compras',
                endpoint: '/panel/api/detalles-compras',
                columns: ['Número', 'Proveedor', 'Monto', 'Fecha', 'Estado'],
                renderFn: 'renderCompras'
            },
            'ingresos': {
                title: '💵 Detalles de Ingresos',
                endpoint: '/panel/api/detalles-ventas',
                columns: ['Número', 'Cliente', 'Monto', 'Fecha', 'Estado'],
                renderFn: 'renderVentas'
            },
            'gastos': {
                title: '💸 Detalles de Gastos',
                endpoint: '/panel/api/detalles-compras',
                columns: ['Número', 'Proveedor', 'Monto', 'Fecha', 'Estado'],
                renderFn: 'renderCompras'
            },
            'productos-activos': {
                title: '📋 Listado de Productos Activos',
                endpoint: '/panel/api/productos-activos',
                columns: ['Nombre', 'Categoría', 'Precio', 'Stock'],
                renderFn: 'renderProductosActivos'
            },
            'ganancia-neta': {
                title: '💹 Análisis de Ganancia (Ventas)',
                endpoint: '/panel/api/detalles-ventas',
                columns: ['Número', 'Cliente', 'Monto', 'Fecha', 'Estado'],
                renderFn: 'renderVentas'
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
        console.log("%c[PanelWeb] Initializing modal...", "color: #166534; font-weight: bold");
        this.$modal = this.$('#modalDetalles');
        
        if (this.$modal.length) {
            console.log("%c[PanelWeb] Modal element found", "color: #166534");
            this.$modalBody = this.$modal.find('#modalBody');
            this.$modalTitle = this.$modal.find('#modalTitle');
            console.log("%c[PanelWeb] Modal initialized successfully", "color: #198754; font-weight: bold");
        } else {
            console.error("%c[PanelWeb] CRITICAL: Modal element #modalDetalles not found!", "color: #dc3545; font-weight: bold");
            console.error("DOM structure:");
            console.log(this.$el.html());
        }
    },

    // ═══════════════════════════════════════════════════════════════
    // HANDLERS DE EVENTOS
    // ═══════════════════════════════════════════════════════════════
    _onMetricCardClick: function(ev) {
        const metricKey = $(ev.currentTarget).data('metric');
        console.log("%c[PanelWeb] Metric Card Clicked:", "color: #166534; font-weight: bold", metricKey);
        
        const config = this._getMetricasConfig()[metricKey];
        if (config) {
            console.log("%c[PanelWeb] Config found for metric, loading details...", "color: #166534", config);
            this._cargarDetallesMetrica(metricKey);
        } else {
            console.warn("%c[PanelWeb] No configuration found for metric:", "color: #ffc107", metricKey);
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
            console.error("%c[PanelWeb] ERROR: Missing config or modal elements", "color: #dc3545; font-weight: bold", {
                config: !!config,
                modal: !!this.$modal,
                modalBody: !!this.$modalBody,
                modalTitle: !!this.$modalTitle
            });
            return;
        }

        console.log("%c[PanelWeb] Setting modal title and showing loading...", "color: #166534", config.title);
        
        this.$modalTitle.text(config.title);
        this.$modalBody.html('<div class="modal-loading"><div class="spinner-border"></div></div>');
        this.$modal.modal('show');

        const fechaDesdeInput = document.querySelector('input[name="fecha_desde"]');
        const fechaHastaInput = document.querySelector('input[name="fecha_hasta"]');
        const fechaDesde = fechaDesdeInput ? fechaDesdeInput.value : '';
        const fechaHasta = fechaHastaInput ? fechaHastaInput.value : '';
        
        console.log("%c[PanelWeb] Loading details for metric:", "color: #166534", metricKey, {
            endpoint: config.endpoint,
            fechaDesde,
            fechaHasta
        });
        
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
        console.log("%c[PanelWeb] Fetching URL:", "color: #166534", url);

        fetch(url)
            .then(response => {
                console.log("%c[PanelWeb] Response received:", "color: #166534", {
                    status: response.status,
                    ok: response.ok,
                    contentType: response.headers.get('content-type')
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("%c[PanelWeb] Data parse successful:", "color: #166534", data);
                
                // Validar que data sea un objeto y tenga la estructura esperada
                if (!data || typeof data !== 'object') {
                    throw new Error('Respuesta inválida del servidor');
                }
                
                if (data.error) {
                    console.error("%c[PanelWeb] API returned error:", "color: #dc3545", data.error);
                    this.$modalBody.html(`
                        <div class="modal-empty" style="color: #dc3545;">
                            <div class="empty-icon">⚠️</div>
                            <p><strong>Error:</strong> ${this._sanitizeText(data.error)}</p>
                        </div>
                    `);
                    return;
                }
                
                // Validar que items sea un array
                if (!Array.isArray(data.items)) {
                    console.warn("%c[PanelWeb] Items is not an array, setting to empty array", "color: #ffc107");
                    data.items = [];
                }
                
                console.log("%c[PanelWeb] Rendering table with", "color: #166534", data.items.length, "items");
                this._renderizarTabla(data, page, columns, metricKey, endpoint, fechaDesde, fechaHasta);
            })
            .catch(error => {
                console.error('%c[PanelWeb] Fetch Error:', "color: #dc3545; font-weight: bold", error);
                this.$modalBody.html(`
                    <div class="modal-empty" style="color: #dc3545;">
                        <div class="empty-icon">❌</div>
                        <p>Error al cargar los datos: ${this._sanitizeText(error.message)}</p>
                        <p style="font-size: 0.85rem; margin-top: 1rem;">Por favor, reintente más tarde.</p>
                    </div>
                `);
            });
    },

    _sanitizeText: function(text) {
        // Prevenir XSS renderizando solo texto plano
        const div = document.createElement('div');
        div.textContent = String(text || '');
        return div.innerHTML;
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
                html += this._renderItemPorMetrica(item, metricKey);
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

    _renderItemPorMetrica: function(item, metricKey) {
        let html = '<tr>';
        
        if (metricKey === 'sin-stock' || metricKey === 'bajo-stock') {
            html += `<td>${item.nombre || '-'}</td>`;
            html += `<td><strong>${item.stock || '0'}</strong></td>`;
            html += `<td>${item.sku || '-'}</td>`;
        } else if (['total-ventas', 'ingresos', 'ganancia-neta'].includes(metricKey)) {
            const monto = parseFloat(item.monto || 0);
            const clienteDisplay = item.dni ? `${item.cliente} - ${item.dni}` : item.cliente;
            const estadoColor = this._getColorEstado(item.estado);
            const estadoLabel = this._getEstadoLabel(item.estado);
            
            html += `<td>${item.numero || '-'}</td>`;
            html += `<td>${clienteDisplay || '-'}</td>`;
            html += `<td>$${monto.toFixed(2)}</td>`;
            html += `<td>${item.fecha || '-'}</td>`;
            html += `<td><span class="badge" style="background-color: ${estadoColor};">${estadoLabel}</span></td>`;
        } else if (['total-compras', 'gastos'].includes(metricKey)) {
            const monto = parseFloat(item.monto || 0);
            const proveedorDisplay = item.dni ? `${item.proveedor} - ${item.dni}` : item.proveedor;
            const estadoColor = this._getColorEstado(item.estado);
            const estadoLabel = this._getEstadoLabel(item.estado);
            
            html += `<td>${item.numero || '-'}</td>`;
            html += `<td>${proveedorDisplay || '-'}</td>`;
            html += `<td>$${monto.toFixed(2)}</td>`;
            html += `<td>${item.fecha || '-'}</td>`;
            html += `<td><span class="badge" style="background-color: ${estadoColor};">${estadoLabel}</span></td>`;
        } else if (metricKey === 'productos-activos') {
            const precio = parseFloat(item.precio || 0);
            html += `<td>${item.nombre || '-'}</td>`;
            html += `<td>${item.categoria || '-'}</td>`;
            html += `<td>$${precio.toFixed(2)}</td>`;
            html += `<td><strong>${item.stock || '0'}</strong></td>`;
        }
        
        html += '</tr>';
        return html;
    },

    _getColorEstado: function(estado) {
        // Mapeo de estados de Odoo a colores
        const estadoMap = {
            'draft': '#FFC107',      // Amarillo - Pendiente
            'sent': '#FFC107',       // Amarillo - Pendiente
            'sale': '#28A745',       // Verde - Confirmado
            'done': '#28A745',       // Verde - Completado
            'cancel': '#DC3545',     // Rojo - Cancelado
            'purchase': '#FFC107',   // Amarillo - Pendiente de compra
            'to approve': '#FFC107', // Amarillo - Pendiente de aprobación
            'approved': '#28A745',   // Verde - Aprobado
            'rejected': '#DC3545',   // Rojo - Rechazado
        };
        return estadoMap[estado] || '#6C757D'; // Gris por defecto
    },

    _getEstadoLabel: function(estado) {
        // Mapeo de estados de Odoo a etiquetas en español
        const labelMap = {
            'draft': 'Pendiente',
            'sent': 'Pendiente',
            'sale': 'Confirmado',
            'done': 'Completado',
            'cancel': 'Cancelado',
            'purchase': 'Pendiente',
            'to approve': 'Por Aprobar',
            'approved': 'Aprobado',
            'rejected': 'Rechazado',
        };
        return labelMap[estado] || estado;
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

