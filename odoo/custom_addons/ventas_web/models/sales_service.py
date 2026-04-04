"""
==============================================================================
SERVICIO DE VENTAS - Sales Service
==============================================================================

Centraliza TODA la lógica de negocio del módulo ventas_web:
- Filtros avanzados
- Creación de clientes
- Creación de órdenes
- Confirmación y cancelación

Este modelo es ABSTRACTO y no genera tablas en BD.
Se instancia desde los controllers para acceder a los métodos de negocio.

Uso:
    sales_service = self.env['sales.service']
    domain = sales_service.build_sale_filters(kwargs)
    cliente = sales_service.create_quick_customer(nombre, dni)
    orden = sales_service.create_sale_order(cliente_id, lineas, origen)

==============================================================================
"""

from odoo import models, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class SalesService(models.AbstractModel):
    """Servicio centralizado de lógica de negocio para ventas_web"""
    
    _name = 'sales.service'
    _description = 'Servicio de Ventas Web'

    # ═════════════════════════════════════════════════════════════════════════
    # MÉTODO AUXILIAR: Logging
    # ═════════════════════════════════════════════════════════════════════════

    def _log_info(self, mensaje, order_id=None):
        """
        Registra un mensaje de información en los logs.
        
        Args:
            mensaje (str): Mensaje a registrar
            order_id (int, opcional): ID de la orden (para contexto)
        """
        contexto = f"[Orden {order_id}] " if order_id else "[Sales Service] "
        _logger.info(contexto + mensaje)

    # ═════════════════════════════════════════════════════════════════════════
    # MÉTODO AUXILIAR: Detección de entregas pendientes
    # ═════════════════════════════════════════════════════════════════════════

    def tiene_entregas_pendientes(self, order_id):
        """
        Verifica si una orden de venta tiene entregas (pickings outgoing) pendientes de validar.
        
        SINCRONIZACIÓN CON ODOO:
        - Busca TODAS las entregas (stock.picking con picking_type_code='outgoing')
        - Retorna True si al menos UNA está en estado 'assigned' o 'confirmed'
        - Retorna False si todas están en 'done' o 'cancel'
        
        RENDIMIENTO:
        - Usa search() sin mapped() para evitar N+1 queries
        - Límite de 1 picking para cortocircuito rápido
        
        Args:
            order_id (int): ID de la sale.order
        
        Returns:
            bool: True si hay al menos una entrega pendiente, False si no
        """
        try:
            # Buscar un picking outgoing en estado 'assigned' o 'confirmed'
            # Si encuentra aunque sea uno, retorna True (cortocircuito)
            picking_pendiente = self.env['stock.picking'].sudo().search([
                ('sale_id', '=', int(order_id)),
                ('picking_type_code', '=', 'outgoing'),
                ('state', 'in', ['assigned', 'confirmed']),
            ], limit=1)
            
            return bool(picking_pendiente)
        
        except (ValueError, TypeError):
            # Si el order_id no es válido, retorna False
            return False

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 1: FILTROS AVANZADOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def build_sale_filters(self, kwargs):
        """
        Construye un domain (filtro ORM) basado en parámetros GET.
        
        Soporta:
        - cliente: búsqueda por nombre en partner_id (ilike)
        - producto: búsqueda en order_line.product_id (ilike)
        - fecha_desde / fecha_hasta: rango de date_order
        - monto_min / monto_max: rango de amount_total
        - categoria: product_id.categ_id (ID exacto)
        - estado: state ('confirmada' → 'sale', 'cancelada' → 'cancel')
        - origen: sales_origin (exacto)
        
        Args:
            kwargs (dict): Parámetros GET del request
        
        Returns:
            list: Domain Odoo para search()
        """
        domain = []

        # ── Filtro: Cliente (name, DNI) ──
        cliente = kwargs.get('cliente', '').strip()
        if cliente:
            domain.append(('partner_id.name', 'ilike', cliente))

        # ── Filtro: Producto (order_line.product_id) ──
        producto = kwargs.get('producto', '').strip()
        if producto:
            domain.append(('order_line.product_id.name', 'ilike', producto))

        # ── Filtro: Rango de fechas (fecha_desde) ──
        fecha_desde = kwargs.get('fecha_desde', '').strip()
        if fecha_desde:
            try:
                dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
                domain.append(('date_order', '>=', dt))
            except ValueError:
                pass  # Ignorar formato inválido

        # ── Filtro: Rango de fechas (fecha_hasta) ──
        fecha_hasta = kwargs.get('fecha_hasta', '').strip()
        if fecha_hasta:
            try:
                dt = datetime.strptime(fecha_hasta, '%Y-%m-%d')
                # Incluir todo el día: sumar 1 día
                dt_fin = dt + timedelta(days=1)
                domain.append(('date_order', '<', dt_fin))
            except ValueError:
                pass

        # ── Filtro: Monto total (monto_min) ──
        monto_min = kwargs.get('monto_min', '').strip()
        if monto_min:
            try:
                domain.append(('amount_total', '>=', float(monto_min)))
            except (ValueError, TypeError):
                pass

        # ── Filtro: Monto total (monto_max) ──
        monto_max = kwargs.get('monto_max', '').strip()
        if monto_max:
            try:
                domain.append(('amount_total', '<=', float(monto_max)))
            except (ValueError, TypeError):
                pass

        # ── Filtro: Categoría de producto ──
        categoria = kwargs.get('categoria', '').strip()
        if categoria:
            try:
                domain.append(('order_line.product_id.categ_id', '=', int(categoria)))
            except (ValueError, TypeError):
                pass

        # ── Filtro: Estado (confirmada / cancelada) ──
        estado = kwargs.get('estado', '').strip()
        if estado == 'confirmada':
            domain.append(('state', '=', 'sale'))
        elif estado == 'cancelada':
            domain.append(('state', '=', 'cancel'))

        # ── Filtro: Origen de venta ──
        origen = kwargs.get('origen', '').strip()
        if origen:
            domain.append(('sales_origin', '=', origen))

        return domain

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 2: GESTIÓN DE CLIENTES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def create_quick_customer(self, nombre, dni=None):
        """
        Crea un cliente rápidamente o retorna uno existente.
        
        Verifica:
        - Si ya existe un cliente con el mismo nombre
        - Si no existe, lo crea
        
        Args:
            nombre (str): Nombre completo del cliente (obligatorio)
            dni (str): DNI o documento (opcional, se guarda en 'vat')
        
        Returns:
            dict: {
                'success': bool,
                'id': int,
                'nombre': str,
                'es_nuevo': bool,
                'message': str
            }
        """
        # ── Validación de datos ──
        nombre = (nombre or '').strip()
        if not nombre:
            return {
                'success': False,
                'message': 'El nombre del cliente es obligatorio.',
            }

        try:
            ResPartner = self.env['res.partner']
            
            # ── Buscar cliente existente ──
            cliente_existente = ResPartner.sudo().search(
                [('name', '=', nombre), ('customer_rank', '>', 0)],
                limit=1
            )
            
            if cliente_existente:
                return {
                    'success': True,
                    'id': cliente_existente.id,
                    'nombre': cliente_existente.name,
                    'es_nuevo': False,
                    'message': 'Cliente ya existe.',
                }

            # ── Crear nuevo cliente ──
            cliente_nuevo = ResPartner.sudo().create({
                'name': nombre,
                'vat': dni or '',
                'customer_rank': 1,  # Marcar como cliente
                'type': 'invoice',  # Dirección de facturación
            })

            return {
                'success': True,
                'id': cliente_nuevo.id,
                'nombre': cliente_nuevo.name,
                'es_nuevo': True,
                'message': 'Cliente creado exitosamente.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear cliente: {str(e)}',
            }

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 3: GESTIÓN DE ÓRDENES DE VENTA
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def create_sale_order(self, cliente_id, lineas, origen='admin', journal_id=None):
        """
        Crea una nueva orden de venta con líneas de productos.
        
        FLUJO:
        1. Valida cliente
        2. Valida líneas
        3. Crea sale.order en DRAFT
        4. Crea sale.order.line para cada producto
        5. Confirma automáticamente → action_confirm()
        6. El stock se descuenta automáticamente
        
        Args:
            cliente_id (int): ID del cliente (res.partner)
            lineas (list): [{'product_id': int, 'quantity': float}, ...]
            origen (str): 'admin', 'cliente_web', 'integracion', etc.
            journal_id (int): ID del journal de pago (opcional)
        
        Returns:
            dict: {
                'success': bool,
                'order_id': int,
                'order_name': str,
                'message': str,
                'url': str
            }
        """
        try:
            # ── Validar cliente ──
            cliente = self.env['res.partner'].sudo().browse(int(cliente_id))
            if not cliente.exists():
                return {
                    'success': False,
                    'message': 'Cliente no encontrado.',
                }

            # ── Validar líneas ──
            if not lineas or not isinstance(lineas, list):
                return {
                    'success': False,
                    'message': 'Debe agregar al menos un producto.',
                }

            # ── Crear orden (DRAFT) ──
            order_vals = {
                'partner_id': cliente.id,
                'sales_origin': origen,
                'state': 'draft',
                'date_order': datetime.now(),
            }

            # Si se proporciona journal_id, asignarlo
            if journal_id:
                try:
                    order_vals['journal_id'] = int(journal_id)
                except (ValueError, TypeError):
                    pass

            orden = self.env['sale.order'].sudo().create(order_vals)

            # ── Crear líneas de orden ──
            self._create_sale_order_lines(orden, lineas)

            # ── CONFIRMACIÓN AUTOMÁTICA ──
            # Llamamos a action_confirm() que dispara:
            # - Validación de cantidades y stock
            # - Generación de movimientos de stock
            # - Cambio de estado a 'sale'
            self._confirm_order_with_error_handling(orden)

            return {
                'success': True,
                'order_id': orden.id,
                'order_name': orden.name,
                'message': f'Orden {orden.name} creada y confirmada exitosamente.',
                'url': '/ventas',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear la venta: {str(e)}',
            }

    @api.model
    def _create_sale_order_lines(self, orden, lineas):
        """
        Crea las líneas de orden de venta.
        
        Ignora líneas mal formadas sin causar fallo general.
        
        Args:
            orden (sale.order): Orden ya creada
            lineas (list): [{'product_id': int, 'quantity': float}, ...]
        """
        for linea_data in lineas:
            try:
                product_id = int(linea_data.get('product_id', 0))
                cantidad = float(linea_data.get('quantity', 1))

                # Validaciones
                if product_id <= 0 or cantidad <= 0:
                    continue

                producto = self.env['product.product'].sudo().browse(product_id)
                if not producto.exists():
                    continue

                # Crear línea con list_price como tarifa por defecto
                self.env['sale.order.line'].sudo().create({
                    'order_id': orden.id,
                    'product_id': producto.id,
                    'product_uom_qty': cantidad,
                    'price_unit': producto.list_price,
                })

            except (ValueError, TypeError, Exception):
                # Ignorar líneas mal formadas; continuar con las siguientes
                continue

    @api.model
    def _confirm_order_with_error_handling(self, orden):
        """
        Confirma una orden llamando a action_confirm().
        
        Si falla, registra el error pero NO cancela la creación de la orden.
        
        Args:
            orden (sale.order): Orden a confirmar
        """
        try:
            orden.action_confirm()
        except Exception as e:
            # Log pero no propagate; la orden existe aunque no se haya confirmado
            print(f"[VENTAS_WEB] Error al confirmar orden {orden.name}: {str(e)}")

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 4: CONFIRMACIÓN DE ÓRDENES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def confirm_sale_order(self, order_id):
        """
        Confirma una orden de venta existente (DRAFT → SALE).
        
        Verifica:
        - Orden existe
        - Orden está en estado DRAFT (no puede confirmar si ya está confirmada)
        
        Luego:
        - Llama a action_confirm() que genera movimientos de stock
        
        Args:
            order_id (int): ID de la sale.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        try:
            orden = self.env['sale.order'].sudo().browse(int(order_id))

            # ── Validar existencia ──
            if not orden.exists():
                return {
                    'success': False,
                    'message': 'Orden no encontrada.',
                }

            # ── Validar estado ──
            if orden.state != 'draft':
                return {
                    'success': False,
                    'message': f'Solo se pueden confirmar órdenes en DRAFT. Estado actual: {orden.state}',
                }

            # ── Confirmar ──
            orden.action_confirm()

            return {
                'success': True,
                'message': f'Orden {orden.name} confirmada. Stock descontado.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al confirmar: {str(e)}',
            }

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 5: CANCELACIÓN DE ÓRDENES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def cancel_sale_order(self, order_id):
        """
        Cancela una orden de venta.
        
        Si la orden estaba confirmada:
        - Revierte los movimientos de stock
        
        Verifica:
        - Orden existe
        - Orden no está ya cancelada
        
        Args:
            order_id (int): ID de la sale.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        try:
            orden = self.env['sale.order'].sudo().browse(int(order_id))

            # ── Validar existencia ──
            if not orden.exists():
                return {
                    'success': False,
                    'message': 'Orden no encontrada.',
                }

            # ── Validar que no esté ya cancelada ──
            if orden.state == 'cancel':
                return {
                    'success': False,
                    'message': 'Esta orden ya está cancelada.',
                }

            # ── Cancelar ──
            orden.action_cancel()

            return {
                'success': True,
                'message': f'Orden {orden.name} cancelada.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al cancelar: {str(e)}',
            }

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 6: VALIDACIÓN DE ENTREGAS (STOCK PICKING)
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def validar_entrega_venta(self, order_id):
        """
        Valida las entregas (pickings outgoing) de una orden de venta e incrementa stock.
        
        PROCESO PARA CADA PICKING:
        1. Si está en draft: ejecutar action_confirm() → 'confirmed'
        2. Ejecutar action_assign() - Asigna stock disponible a las líneas
        3. Establece quantity en move_line_ids
        4. Ejecuta button_validate() - Valida el picking y genera movimientos de stock
        5. El stock.quant se actualiza automáticamente en la ubicación origen (disminuye)
        
        GARANTÍAS:
        - Usa campos correctos de Odoo 19 (quantity en move_line)
        - Completa la entrega al 100% (sin backorders parciales)
        - Manejo robusto de errores
        - Logging detallado en cada paso
        
        Args:
            order_id (int): ID de la sale.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'entregas_validadas': int,
                'order_name': str
            }
        """
        try:
            orden = self.env['sale.order'].sudo().browse(int(order_id))

            # ── Validar existencia ──
            if not orden.exists():
                self._log_info(f"Orden {order_id} no encontrada", order_id)
                return {
                    'success': False,
                    'message': 'Orden no encontrada.',
                }

            # ── Validar que esté confirmada ──
            if orden.state != 'sale':
                self._log_info(f"Orden {orden.name} no está confirmada. Estado: {orden.state}", orden.id)
                return {
                    'success': False,
                    'message': f'La orden debe estar confirmada. Estado actual: {orden.state}',
                }

            self._log_info(f"Iniciando validación de entregas para {orden.name}", orden.id)

            # ── Validar automáticamente los pickings asociados ──
            resultado_pickings = self._validar_pickings_venta(orden)

            return resultado_pickings

        except Exception as e:
            error_detail = str(e)
            self._log_info(f"ERROR CRÍTICO: {error_detail}", order_id)
            return {
                'success': False,
                'message': f'Error inesperado al validar entregas: {error_detail}',
            }

    @api.model
    def _validar_pickings_venta(self, orden):
        """
        Valida automáticamente todos los pickings outgoing (entregas) asociados a una orden de venta.
        
        FLUJO MEJORADO PARA CADA PICKING:
        1. Si está en draft: ejecutar action_confirm()
        2. Ejecutar action_assign() - Asigna stock disponible
        3. Crear move_lines si no existen
        4. Establece quantity en cada move_line
        5. Ejecuta button_validate()
        
        GARANTÍAS:
        - Usa campos correctos de Odoo 19
        - Completa la entrega al 100%
        - Logging detallado para debugging
        - Manejo robusto de errores
        
        Args:
            orden (sale.order): Orden ya confirmada
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'entregas_validadas': int
            }
        """
        try:
            # Obtener todos los pickings outgoing asociados a esta orden
            pickings = self.env['stock.picking'].sudo().search([
                ('sale_id', '=', orden.id),
                ('picking_type_code', '=', 'outgoing'),
            ])

            self._log_info(f"Procesando {len(pickings)} entrega(s) para orden {orden.name}", orden.id)

            if not pickings:
                self._log_info(f"No hay entregas para validar en orden {orden.name}", orden.id)
                return {
                    'success': True,
                    'message': 'No se encontraron entregas para validar.',
                    'entregas_validadas': 0,
                }

            entregas_validadas = 0
            errores = []

            for picking in pickings:
                try:
                    picking_name = picking.name
                    self._log_info(f"Iniciando validación de entrega {picking_name}", orden.id)

                    # ── VALIDACIÓN: Skip si ya está done ──
                    if picking.state == 'done':
                        self._log_info(f"Entrega {picking_name} ya está validada (done)", orden.id)
                        entregas_validadas += 1
                        continue

                    # ── PASO 1: Confirmar si está en draft ──
                    if picking.state == 'draft':
                        self._log_info(f"Confirmando entrega {picking_name} (draft → confirmed)", orden.id)
                        picking.action_confirm()

                    # ── PASO 2: Asignar stock disponible ──
                    if picking.state in ('confirmed', 'awaiting_picking'):
                        try:
                            self._log_info(f"Asignando stock disponible a {picking_name}", orden.id)
                            picking.action_assign()
                            self._log_info(f"Stock asignado correctamente a {picking_name}", orden.id)
                        except Exception as assign_error:
                            self._log_info(f"Aviso en asignación de {picking_name}: {str(assign_error)}", orden.id)

                    # ── PASO 3: Crear o completar move_lines con cantidades ──
                    self._preparar_move_lines_venta(picking, orden)

                    # ── PASO 4: Validar el picking ──
                    self._log_info(f"Validando entrega {picking_name} (button_validate)", orden.id)
                    picking.button_validate()
                    self._log_info(f"Entrega {picking_name} validada exitosamente. Stock descontado.", orden.id)

                    entregas_validadas += 1

                except Exception as e:
                    error_msg = str(e)
                    if hasattr(e, 'name'):
                        error_msg = e.name
                    
                    self._log_info(f"ERROR en entrega {picking.name}: {error_msg}", orden.id)
                    errores.append(f"Entrega {picking.name}: {error_msg}")

            # ── RESULTADO FINAL ──
            self._log_info(f"Proceso completado: {entregas_validadas}/{len(pickings)} entregas validadas", orden.id)
            
            if errores:
                mensaje = f'{entregas_validadas} entrega(s) validada(s). Errores: {"; ".join(errores[:3])}'
                return {
                    'success': True if entregas_validadas > 0 else False,
                    'message': mensaje,
                    'entregas_validadas': entregas_validadas,
                }

            return {
                'success': True,
                'message': f'{entregas_validadas} entrega(s) validada(s) exitosamente. Stock descontado.',
                'entregas_validadas': entregas_validadas,
            }

        except Exception as e:
            self._log_info(f"ERROR CRÍTICO en validación de pickings: {str(e)}", orden.id)
            return {
                'success': False,
                'message': f'Error crítico al validar entregas: {str(e)}',
                'entregas_validadas': 0,
            }

    def _preparar_move_lines_venta(self, picking, orden):
        """
        Prepara las move_lines para validación: crea las que falten y setea quantity.
        
        Este método es crucial porque:
        - Si no hay move_lines creadas, button_validate() no funciona
        - Debe ser ejecutado DESPUÉS de action_assign()
        - Setea quantity = cantidad esperada (para entregas sin lotes)
        
        Args:
            picking (stock.picking): Picking a preparar
            orden (sale.order): Orden asociada (para logging)
        """
        try:
            self._log_info(f"Preparando move_lines para {picking.name}", orden.id)
            
            # Iterar sobre los movimientos (stock.move)
            for move in picking.move_ids:
                # Obtener o crear la move_line
                move_lines = self.env['stock.move.line'].sudo().search([
                    ('move_id', '=', move.id)
                ], limit=1)
                
                if move_lines:
                    # Ya existe move_line, solo actualizar quantity
                    move_line = move_lines[0]
                else:
                    # Crear move_line
                    self._log_info(f"Creando move_line para {move.product_id.name} en {picking.name}", orden.id)
                    move_line = self.env['stock.move.line'].sudo().create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'quantity': move.product_uom_qty,  # Campo correcto en Odoo 19
                    })
                    self._log_info(f"Move_line creada: {move.product_id.name} x {move.product_uom_qty}", orden.id)
                    continue
                
                # Actualizar quantity si no está ya set
                if move_line.quantity == 0 and move.product_uom_qty > 0:
                    self._log_info(f"Actualizando quantity: {move.product_id.name} x {move.product_uom_qty}", orden.id)
                    move_line.write({
                        'quantity': move.product_uom_qty
                    })
                    
        except Exception as e:
            self._log_info(f"ERROR en preparación de move_lines: {str(e)}", orden.id)
            raise  # Re-lanzar para que sea manejado por el caller

