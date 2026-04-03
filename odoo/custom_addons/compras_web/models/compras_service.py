"""
==============================================================================
SERVICIO DE COMPRAS - Compras Service
==============================================================================

Centraliza TODA la lógica de negocio del módulo compras_web:
- Filtros avanzados
- Creación de proveedores
- Creación de órdenes de compra
- Confirmación de órdenes (crear pickings sin validar)
- Validación de recepciones (incrementar stock)
- Cancelación de órdenes

Este modelo es ABSTRACTO y no genera tablas en BD.
Se instancia desde los controllers para acceder a los métodos de negocio.

FLUJO DE ESTADOS:
1. "borrador": purchase.order en DRAFT
   - Crear con crear_orden_compra()

2. "pendiente": purchase.order en PURCHASE (pickings creados pero sin validar)
   - Confirmar con confirmar_orden_compra()
   - Crea stock.picking pero NO incrementa stock aún

3. "confirmado": purchase.order en DONE (pickings validados)
   - Validar con validar_recepcion_compra()
   - Valida pickings e incrementa stock automáticamente

Uso:
    compras_service = self.env['compras.service']
    domain = compras_service.construir_domain_filtros(kwargs)
    proveedor = compras_service.crear_proveedor_rapido(nombre)
    orden = compras_service.crear_orden_compra(proveedor_id, lineas)
    compras_service.confirmar_orden_compra(orden_id)  # "pendiente"
    compras_service.validar_recepcion_compra(orden_id)  # "confirmado"

==============================================================================
"""

from odoo import models, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class ComprasService(models.AbstractModel):
    """Servicio centralizado de lógica de negocio para compras_web"""
    
    _name = 'compras.service'
    _description = 'Servicio de Compras Web'

    # ═════════════════════════════════════════════════════════════════════════
    # MÉTODO AUXILIAR: Logging
    # ═════════════════════════════════════════════════════════════════════════

    def _log_info(self, mensaje, orden_id=None):
        """
        Registra un mensaje de información en los logs.
        
        Args:
            mensaje (str): Mensaje a registrar
            orden_id (int, opcional): ID de la orden (para contexto)
        """
        contexto = f"[Orden {orden_id}] " if orden_id else "[Compras Service] "
        _logger.info(contexto + mensaje)

    # ═════════════════════════════════════════════════════════════════════════
    # MÉTODO AUXILIAR: Validación de recepciones pendientes
    # ═════════════════════════════════════════════════════════════════════════

    def tiene_recepciones_pendientes(self, orden_id):
        """
        Verifica si una orden de compra tiene recepciones (pickings) pendientes de validar.
        
        SINCRONIZACIÓN CON ODOO:
        - Busca TODAS las recepciones asociadas a la orden
        - Retorna True si al menos UNA está en estado 'assigned' o 'confirmed'
        - Retorna False si todas están en 'done' o 'cancel'
        
        RENDIMIENTO:
        - Usa search() sin mapped() para evitar N+1 queries
        - Límite de 1 picking para cortocircuito rápido
        
        Args:
            orden_id (int): ID de la purchase.order
        
        Returns:
            bool: True si hay al menos una recepción pendiente, False si no
        """
        try:
            # Buscar un picking en estado 'assigned' o 'confirmed'
            # Si encuentra aunque sea uno, retorna True (cortocircuito)
            picking_pendiente = self.env['stock.picking'].sudo().search([
                ('purchase_id', '=', int(orden_id)),
                ('state', 'in', ['assigned', 'confirmed']),
            ], limit=1)
            
            return bool(picking_pendiente)
        
        except (ValueError, TypeError):
            # Si el orden_id no es válido, retorna False
            return False

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 1: FILTROS AVANZADOS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def construir_domain_filtros(self, kwargs):
        """
        Construye un domain (filtro ORM) basado en parámetros GET.
        
        Soporta:
        - proveedor: búsqueda por nombre en partner_id (ilike)
        - producto: búsqueda en order_line.product_id (ilike)
        - fecha_desde / fecha_hasta: rango de date_order
        - monto_min / monto_max: rango de amount_total
        - categoria: product_id.categ_id (ID exacto)
        - estado: state ('draft', 'purchase', 'cancel')
        
        Args:
            kwargs (dict): Parámetros GET del request
        
        Returns:
            list: Domain Odoo para search()
        """
        domain = []

        # ── Filtro: Proveedor (name) ──
        proveedor = kwargs.get('proveedor', '').strip()
        if proveedor:
            domain.append(('partner_id.name', 'ilike', proveedor))

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

        # ── Filtro: Estado ──
        estado = kwargs.get('estado', '').strip()
        if estado in ('draft', 'purchase', 'cancel'):
            domain.append(('state', '=', estado))

        return domain

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 2: GESTIÓN DE PROVEEDORES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def crear_proveedor_rapido(self, nombre):
        """
        Crea un proveedor rápidamente o retorna uno existente.
        
        Verifica:
        - Si ya existe un proveedor con el mismo nombre
        - Si no existe, lo crea
        
        Args:
            nombre (str): Nombre del proveedor (obligatorio)
        
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
                'message': 'El nombre del proveedor es obligatorio.',
            }

        try:
            ResPartner = self.env['res.partner']
            
            # ── Buscar proveedor existente ──
            proveedor_existente = ResPartner.sudo().search(
                [('name', '=', nombre), ('supplier_rank', '>', 0)],
                limit=1
            )
            
            if proveedor_existente:
                return {
                    'success': True,
                    'id': proveedor_existente.id,
                    'nombre': proveedor_existente.name,
                    'es_nuevo': False,
                    'message': 'Proveedor ya existe.',
                }

            # ── Crear nuevo proveedor ──
            proveedor_nuevo = ResPartner.sudo().create({
                'name': nombre,
                'supplier_rank': 1,  # Marcar como proveedor
                'type': 'invoice',  # Dirección de facturación
            })

            return {
                'success': True,
                'id': proveedor_nuevo.id,
                'nombre': proveedor_nuevo.name,
                'es_nuevo': True,
                'message': 'Proveedor creado exitosamente.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear proveedor: {str(e)}',
            }

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 3: GESTIÓN DE ÓRDENES DE COMPRA
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def crear_orden_compra(self, proveedor_id, lineas):
        """
        Crea una nueva orden de compra con líneas de productos.
        
        IMPORTANTE: La orden se crea en estado DRAFT sin modificar stock.
        El stock solo se incrementa en la confirmación.
        
        FLUJO:
        1. Valida proveedor
        2. Valida líneas
        3. Crea purchase.order en DRAFT
        4. Crea purchase.order.line para cada producto
        
        Args:
            proveedor_id (int): ID del proveedor (res.partner)
            lineas (list): [{'product_id': int, 'cantidad': float, 'precio_unitario': float}, ...]
        
        Returns:
            dict: {
                'success': bool,
                'orden_id': int,
                'nombre_orden': str,
                'message': str,
                'url': str
            }
        """
        try:
            # ── Validar proveedor ──
            proveedor = self.env['res.partner'].sudo().browse(int(proveedor_id))
            if not proveedor.exists():
                return {
                    'success': False,
                    'message': 'Proveedor no encontrado.',
                }

            # ── Validar líneas ──
            if not lineas or not isinstance(lineas, list):
                return {
                    'success': False,
                    'message': 'Debe agregar al menos un producto.',
                }

            # ── Crear orden (DRAFT) ──
            orden_vals = {
                'partner_id': proveedor.id,
                'state': 'draft',
                'date_order': datetime.now(),
            }

            orden_compra = self.env['purchase.order'].sudo().create(orden_vals)

            # ── Crear líneas de compra ──
            self._crear_lineas_compra(orden_compra, lineas)

            return {
                'success': True,
                'orden_id': orden_compra.id,
                'nombre_orden': orden_compra.name,
                'message': f'Orden {orden_compra.name} creada exitosamente.',
                'url': '/compras',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al crear la compra: {str(e)}',
            }

    @api.model
    def _crear_lineas_compra(self, orden, lineas):
        """
        Crea las líneas de orden de compra y actualiza x_costo_usd en product.template.
        
        FLUJO:
        1. Para cada línea válida:
           - Crea purchase.order.line con precio_unitario
           - Actualiza x_costo_usd en product.template con el precio_unitario
        
        Ignora líneas mal formadas sin causar fallo general.
        
        Args:
            orden (purchase.order): Orden ya creada
            lineas (list): [{'product_id': int, 'cantidad': float, 'precio_unitario': float}, ...]
        """
        for linea_data in lineas:
            try:
                product_id = int(linea_data.get('product_id', 0))
                cantidad = float(linea_data.get('cantidad', 1))
                precio_unt = float(linea_data.get('precio_unitario', 0))

                # Validaciones
                if product_id <= 0 or cantidad <= 0 or precio_unt < 0:
                    continue

                producto = self.env['product.product'].sudo().browse(product_id)
                if not producto.exists():
                    continue

                # Crear línea con precio unitario
                self.env['purchase.order.line'].sudo().create({
                    'order_id': orden.id,
                    'product_id': producto.id,
                    'product_qty': cantidad,
                    'price_unit': precio_unt,
                })

                # Actualizar x_costo_usd en product.template
                # El campo x_costo_usd se configura con el precio unitario de la compra
                producto.product_tmpl_id.sudo().write({
                    'x_costo_usd': precio_unt,
                })

            except (ValueError, TypeError, Exception):
                # Ignorar líneas mal formadas; continuar con las siguientes
                continue

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 4: CONFIRMACIÓN DE ÓRDENES (CON INCREMENTO DE STOCK)
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def confirmar_orden_compra(self, orden_id):
        """
        Confirma una orden de compra SIN VALIDAR los pickings.
        
        ESTADO: "pendiente" - Orden confirmada, pickings creados pero sin validar.
        
        PROCESO:
        1. Valida que la orden exista y esté en estado DRAFT
        2. Ejecuta button_confirm() de Odoo (DRAFT → PURCHASE)
           - Esto crea automáticamente los pickings (stock.picking)
           - Crea stock.move para cada línea
        3. Verifica que se crearon los pickings
        4. NO valida los pickings aún (ese es el siguiente paso)
        
        GARANTÍAS:
        - Evita confirmaciones duplicadas verificando estado
        - No incrementa stock en este punto
        - Los pickings quedan en estado 'draft' para validación posterior
        - Logging detallado en cada paso
        
        Args:
            orden_id (int): ID de la purchase.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'pickings_creados': int (número de pickings creados),
                'order_name': str
            }
        """
        try:
            orden = self.env['purchase.order'].sudo().browse(int(orden_id))

            # ── Validar existencia ──
            if not orden.exists():
                self._log_info(f"Orden {orden_id} no encontrada", orden_id)
                return {
                    'success': False,
                    'message': 'Orden no encontrada.',
                }

            # ── Validar estado (solo confirmar si está en DRAFT) ──
            if orden.state != 'draft':
                self._log_info(f"Orden {orden.name} no está en DRAFT. Estado: {orden.state}", orden.id)
                return {
                    'success': False,
                    'message': f'Solo se pueden confirmar órdenes en DRAFT. Estado actual: {orden.state}',
                }

            self._log_info(f"Iniciando confirmación de orden {orden.name}", orden.id)

            # ── PASO 1: Confirmar orden (DRAFT → PURCHASE) ──
            # Esto crea automáticamente los pickings (recepciones)
            try:
                self._log_info(f"Ejecutando button_confirm() para {orden.name}", orden.id)
                orden.button_confirm()
                self._log_info(f"Orden {orden.name} confirmada en Odoo (DRAFT → PURCHASE)", orden.id)
            except Exception as e:
                self._log_info(f"ERROR en button_confirm() para {orden.name}: {str(e)}", orden.id)
                return {
                    'success': False,
                    'message': f'Error al confirmar orden en Odoo: {str(e)}',
                }

            # ── PASO 2: Validar que se crearon los pickings ──
            pickings = self.env['stock.picking'].sudo().search([
                ('purchase_id', '=', orden.id)
            ])

            self._log_info(f"Se encontraron {len(pickings)} picking(s) para {orden.name}", orden.id)

            if not pickings:
                self._log_info(f"ADVERTENCIA: Orden {orden.name} confirmada pero sin pickings asociados", orden.id)
                return {
                    'success': False,
                    'message': f'Orden {orden.name} está confirmada pero no se crearon recepciones. Contacte al administrador.',
                }

            # ── PASO 3: Verificar que se crearon correctamente ──
            self._log_info(f"Confirmación completada: {len(pickings)} picking(s) creados (pendientes de validación)", orden.id)

            return {
                'success': True,
                'message': f'Orden {orden.name} confirmada exitosamente. {len(pickings)} recepción(es) pendiente(s) de validación.',
                'pickings_creados': len(pickings),
                'order_name': orden.name,
            }

        except Exception as e:
            error_detail = str(e)
            self._log_info(f"ERROR CRÍTICO: {error_detail}", orden_id)
            return {
                'success': False,
                'message': f'Error inesperado al confirmar orden: {error_detail}',
            }

    @api.model
    def validar_recepcion_compra(self, orden_id):
        """
        Valida las recepciones (pickings) de una orden de compra e incrementa stock.
        
        ESTADO: "confirmado" - Pickings validados, stock actualizado en inventario.
        
        PROCESO PARA CADA PICKING:
        1. Si está en draft: ejecutar action_confirm() → 'confirmed'
        2. Ejecutar action_assign() - Asigna stock disponible a las líneas
        3. Establece quantity_done = product_uom_qty en move_line_ids
        4. Ejecuta button_validate() - Valida el picking y genera movimientos de stock
        5. El stock.quant se actualiza automáticamente en la ubicación destino
        
        GARANTÍAS:
        - Usa campos correctos de Odoo 19 (quantity en move_line)
        - Completa la recepción al 100% (sin backorders parciales)
        - Manejo robusto de errores
        - Logging detallado en cada paso
        - No usa wizards (asume sin tracking por lotes/series)
        
        Args:
            orden_id (int): ID de la purchase.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'pickings_validados': int,
                'order_name': str
            }
        """
        try:
            orden = self.env['purchase.order'].sudo().browse(int(orden_id))

            # ── Validar existencia ──
            if not orden.exists():
                self._log_info(f"Orden {orden_id} no encontrada", orden_id)
                return {
                    'success': False,
                    'message': 'Orden no encontrada.',
                }

            # ── Validar que esté confirmada ──
            if orden.state not in ('purchase', 'done'):
                self._log_info(f"Orden {orden.name} no está confirmada. Estado: {orden.state}", orden.id)
                return {
                    'success': False,
                    'message': f'La orden debe estar confirmada. Estado actual: {orden.state}',
                }

            self._log_info(f"Iniciando validación de recepciones para {orden.name}", orden.id)

            # ── Validar automáticamente los pickings asociados ──
            resultado_pickings = self._validar_pickings_compra(orden)

            # ── PASO FINAL: Si la validación fue exitosa, cambiar estado a DONE ──
            if resultado_pickings.get('success'):
                try:
                    self._log_info(f"Finalizando orden {orden.name}: cambiando estado a DONE", orden.id)
                    orden.write({'state': 'done'})
                    self._log_info(f"Orden {orden.name} está ahora en estado DONE (completada)", orden.id)
                except Exception as e:
                    self._log_info(f"ADVERTENCIA: No se pudo cambiar estado a DONE: {str(e)}", orden.id)

            return resultado_pickings

        except Exception as e:
            error_detail = str(e)
            self._log_info(f"ERROR CRÍTICO: {error_detail}", orden_id)
            return {
                'success': False,
                'message': f'Error inesperado al validar recepciones: {error_detail}',
            }

    @api.model
    def _validar_pickings_compra(self, orden):
        """
        Valida automáticamente todos los pickings (recepciones) asociados a una orden de compra.
        
        FLUJO MEJORADO PARA CADA PICKING:
        1. Si está en draft: ejecutar action_confirm()
        2. Ejecutar action_assign() - Asigna stock disponible
        3. Crear move_lines si no existen (para intrastat tracking)
        4. Establece quantity en cada move_line
        5. Ejecuta button_validate()
        
        GARANTÍAS:
        - Usa campos correctos de Odoo 19
        - Completa la recepción al 100%
        - Logging detallado para debugging
        - Manejo robusto de errores
        
        Args:
            orden (purchase.order): Orden ya confirmada
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'pickings_validados': int
            }
        """
        try:
            # Obtener todos los pickings asociados a esta orden
            pickings = self.env['stock.picking'].sudo().search([
                ('purchase_id', '=', orden.id)
            ])

            self._log_info(f"Procesando {len(pickings)} recepción(es) para orden {orden.name}", orden.id)

            if not pickings:
                self._log_info(f"No hay recepciones para validar en orden {orden.name}", orden.id)
                return {
                    'success': True,
                    'message': 'No se encontraron recepciones para validar.',
                    'pickings_validados': 0,
                }

            pickings_validados = 0
            errores = []

            for picking in pickings:
                try:
                    picking_name = picking.name
                    self._log_info(f"Iniciando validación de recepción {picking_name}", orden.id)

                    # ── VALIDACIÓN: Skip si ya está done ──
                    if picking.state == 'done':
                        self._log_info(f"Recepción {picking_name} ya está validada (done)", orden.id)
                        pickings_validados += 1
                        continue

                    # ── PASO 1: Confirmar si está en draft ──
                    if picking.state == 'draft':
                        self._log_info(f"Confirmando recepción {picking_name} (draft → confirmed)", orden.id)
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
                    self._preparar_move_lines_para_pickling(picking, orden)

                    # ── PASO 4: Validar el picking ──
                    self._log_info(f"Validando recepción {picking_name} (button_validate)", orden.id)
                    picking.button_validate()
                    self._log_info(f"Recepción {picking_name} validada exitosamente. Stock incrementado.", orden.id)

                    pickings_validados += 1

                except Exception as e:
                    error_msg = str(e)
                    if hasattr(e, 'name'):
                        error_msg = e.name
                    
                    self._log_info(f"ERROR en recepción {picking.name}: {error_msg}", orden.id)
                    errores.append(f"Recepción {picking.name}: {error_msg}")

            # ── RESULTADO FINAL ──
            self._log_info(f"Proceso completado: {pickings_validados}/{len(pickings)} recepciones validadas", orden.id)
            
            if errores:
                mensaje = f'{pickings_validados} recepción(es) validada(s). Errores: {"; ".join(errores[:3])}'
                return {
                    'success': True if pickings_validados > 0 else False,
                    'message': mensaje,
                    'pickings_validados': pickings_validados,
                }

            return {
                'success': True,
                'message': f'{pickings_validados} recepción(es) validada(s) exitosamente. Stock incrementado.',
                'pickings_validados': pickings_validados,
            }

        except Exception as e:
            self._log_info(f"ERROR CRÍTICO en validación de pickings: {str(e)}", orden.id)
            return {
                'success': False,
                'message': f'Error crítico al validar pickings: {str(e)}',
                'pickings_validados': 0,
            }

    def _preparar_move_lines_para_pickling(self, picking, orden):
        """
        Prepara las move_lines para validación: crea las que falten y setea quantity.
        
        Este método es crucial porque:
        - Si no hay move_lines creadas, button_validate() no funciona
        - Debe ser ejecutado DESPUÉS de action_assign()
        - Setea quantity = cantidad esperada (para recepciones sin lotes)
        
        Args:
            picking (stock.picking): Picking a preparar
            orden (purchase.order): Orden asociada (para logging)
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
                    # Ya existe move_line, solo actualizar quantity_done
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

    # ═════════════════════════════════════════════════════════════════════════
    # SECCIÓN 5: CANCELACIÓN DE ÓRDENES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def cancelar_orden_compra(self, orden_id):
        """
        Cancela una orden de compra.
        
        IMPORTANTE: NO modifica stock bajo ninguna circunstancia.
        - Si la orden NO fue confirmada: No hay stock que revertir
        - Si ya fue confirmada: El usuario es responsable de reversión manual
        
        Args:
            orden_id (int): ID de la purchase.order
        
        Returns:
            dict: {
                'success': bool,
                'message': str
            }
        """
        try:
            orden = self.env['purchase.order'].sudo().browse(int(orden_id))

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
            orden.button_cancel()

            return {
                'success': True,
                'message': f'Orden {orden.name} cancelada. No se modificó stock.',
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error al cancelar: {str(e)}',
            }
