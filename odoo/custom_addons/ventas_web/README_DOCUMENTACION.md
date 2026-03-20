"""
═══════════════════════════════════════════════════════════════════════════════
MÓDULO: VENTAS WEB - Gestor de Ventas para Sitio Web
Odoo 19 | Autor: Gonzalo Pizarro
═══════════════════════════════════════════════════════════════════════════════

📋 OBJETIVO GENERAL
═════════════════════
Panel web completo para gestión de órdenes de venta con:
- Visualización de todas las ventas
- Filtros avanzados dinámicos
- Creación manual de órdenes
- Confirmación automática con descuento de stock
- Cancelación de órdenes
- Creación rápida de clientes

═══════════════════════════════════════════════════════════════════════════════
📁 ESTRUCTURA DE ARCHIVOS
═════════════════════════════════════════════════════════════════════════════════

ventas_web/
├── __init__.py                       # Imports: models, controllers
├── __manifest__.py                   # Configuración del módulo
├── models/
│   ├── __init__.py                  # from . import sale_order_extension
│   └── sale_order_extension.py       # Extensión de sale.order
├── controllers/
│   ├── __init__.py                  # from . import ventas
│   └── ventas.py                    # Controller con 5 endpoints
├── views/
│   ├── ventas_template.xml          # Dashboard - Listado + Filtros
│   └── nueva_venta.xml              # Formulario - Crear venta
└── security/
    └── groups.xml                   # Grupos de acceso (vacío, se usa permisos_usuarios.group_administrador)

═══════════════════════════════════════════════════════════════════════════════
🔧 DEPENDENCIAS
═════════════════════════════════════════════════════════════════════════════════

- base              : Modelos base de Odoo
- website           : Framework web
- sale              : Modelo sale.order y sale.order.line
- sale_management   : Gestión avanzada de ventas
- product           : Modelo product.product y product.category
- stock             : Gestión de inventario (stock.location, stock.quant, stock.move)
- account           : Diarios contables (account.journal) para métodos de pago

═══════════════════════════════════════════════════════════════════════════════
🎯 MODELOS Y CAMPOS
═════════════════════════════════════════════════════════════════════════════════

1. sale.order (EXTENDIDO)
   ├── sales_origin: Selection
   │   ├ Opciones: 'admin', 'cliente_web', 'integracion', 'otro'
   │   └ Por defecto: 'admin'
   │   └ Uso: Indicar de dónde provino la orden
   │
   └── journal_id: Many2one → account.journal (Preexistente)
       └ Uso: Método de pago

2. res.partner (ESTÁNDAR)
   ├── name: Nombre del cliente
   ├── vat: DNI/Documento
   └── customer_rank: Para filtrar clientes

3. product.product (ESTÁNDAR)
   ├── name: Nombre
   ├── list_price: Precio de venta (lista)
   └── sale_ok: Validar que sea vendible

4. account.journal (ESTÁNDAR)
   └── type='sale': Diarios de venta (para métodos de pago)

═══════════════════════════════════════════════════════════════════════════════
🌐 RUTAS Y ENDPOINTS
═════════════════════════════════════════════════════════════════════════════════

GET  /ventas
─────────────
Descripción  : Listado principal con filtros avanzados
Auth         : user (administrador)
Método       : GET (parámetros en query string)

Parámetros (Filtros):
├── cliente          : Búsqueda por nombre (partner_id.name)
├── producto         : Búsqueda por nombre (order_line.product_id.name)
├── fecha_desde      : Formato YYYY-MM-DD
├── fecha_hasta      : Formato YYYY-MM-DD
├── monto_min        : Mínimo (amount_total ≥)
├── monto_max        : Máximo (amount_total ≤)
├── categoria        : ID de product.category
├── estado           : 'confirmada' (sale) | 'cancelada' (cancel)
└── origen           : 'admin' | 'cliente_web' | 'integracion' | 'otro'

Retorno      : Template HTML con tabla de ventas + filtros


GET  /ventas/nueva
─────────────────
Descripción  : Formulario para crear nueva venta
Auth         : user (administrador)
Método       : GET

Retorno      : Template HTML con formulario


POST /ventas/crear_cliente (JSON-RPC)
──────────────────────────────
Descripción  : Crear cliente rápidamente desde el formulario
Auth         : user (administrador)
Método       : POST (JSON-RPC)

Parámetros JSON:
├── nombre           : Nombre completo (obligatorio)
└── dni              : DNI (opcional) → se guarda en 'vat'

Retorno      : { success, message, id, nombre, es_nuevo }

NOTAS:
├ Si existe cliente con ese nombre exacto → devuelve existente
└ Si no existe → crea nuevo cliente con customer_rank=1


POST /ventas/crear (JSON-RPC)
──────────────────
Descripción  : Crear nueva orden de venta con sus líneas
Auth         : user (administrador)
Método       : POST (JSON-RPC)

Parámetros JSON:
├── cliente_id       : ID de res.partner (obligatorio)
├── lineas           : [{"product_id": int, "quantity": float}, ...]
├── origen           : 'admin' | 'cliente_web' | ... (default: 'admin')
└── journal_id       : ID de account.journal (opcional)

Retorno      : { success, message, order_id, order_name, url }

FLUJO:
1. Valida cliente existencia
2. Crea sale.order en estado DRAFT
3. Crea sale.order.line para cada producto
4. Ejecuta action_confirm() AUTOMÁTICAMENTE
   ├ Confirma estado a 'sale'
   ├ Genera movimientos de stock
   ├ Descuenta stock en ubicación WH/Stock
   └ El sistema cuadra inventario

IMPORTANTE:
└─ El descuento de stock ocurre en action_confirm(), no antes


POST /ventas/confirmar (JSON-RPC)
──────────────────────
Descripción  : Confirmar orden existente (DRAFT → SALE)
Auth         : user (administrador)
Método       : POST (JSON-RPC)

Parámetros JSON:
└── order_id         : ID de sale.order

Retorno      : { success, message }

NOTAS:
├ Solo aplica si estado = 'draft'
├ Ejecuta action_confirm()
└ Descuenta stock automáticamente


POST /ventas/cancelar (JSON-RPC)
────────────────────
Descripción  : Cancelar orden (revierte stock si ya estaba confirmada)
Auth         : user (administrador)
Método       : POST (JSON-RPC)

Parámetros JSON:
└── order_id         : ID de sale.order

Retorno      : { success, message }

NOTAS:
├ Si estaba en DRAFT → cancela
├ Si estaba en SALE → cancela + revierte movimientos
└ No se puede cancelar si ya estaba cancel


═══════════════════════════════════════════════════════════════════════════════
📊 FLUJO DE STOCK
═════════════════════════════════════════════════════════════════════════════════

1. CREAR VENTA (POST /ventas/crear)
   └─ Orden creada en estado DRAFT
   └─ Stock NO se descuenta

2. CONFIRMAR VENTA (automático en crear O manual con POST /ventas/confirmar)
   ├─ action_confirm() se ejecuta
   ├─ Se crean movimientos de stock:
   │  └─ De: WH/Stock (ubicación interna)
   │  └─ Hacia: WH/Salida → Cliente
   │  └─ Cantidad: Según líneas de orden
   └─ Stock se descuenta en tiempo real

3. CANCELAR VENTA (POST /ventas/cancelar)
   ├─ Si estaba en DRAFT: simplemente cancela
   ├─ Si estaba en SALE: revierte movimientos
   └─ Stock se RESTAURA en WH/Stock

═══════════════════════════════════════════════════════════════════════════════
🎨 INTERFAZ Y VISTAS
═════════════════════════════════════════════════════════════════════════════════

1. ventas_template.xml (Dashboard Principal)
   ├── Header
   │   ├─ Título: "Panel de Ventas"
   │   ├─ Contador: Total de ventas
   │   └─ Botón: "+ Registrar Nueva Venta"
   │
   ├── Filtros Avanzados
   │   ├─ Cliente (búsqueda texto)
   │   ├─ Producto (búsqueda texto)
   │   ├─ Categoría (select)
   │   ├─ Estado (select: Todos/Confirmada/Cancelada)
   │   ├─ Origen (select: Todos/Admin/Web/Otro)
   │   └─ Botones: Filtrar | Limpiar
   │
   ├── Tabla de Ventas (Responsive)
   │   ├─ Orden | Cliente | Productos | Cantidad | Total | Estado | Origen | Fecha
   │   ├─ Estado: Badges coloreadas (Confirmada/Borrador/Cancelada)
   │   └─ Acciones: Confirmar (si DRAFT) | Cancelar (si DRAFT o SALE)
   │
   └── Estado Vacío
       └─ Mensaje: "No se encontraron ventas"

2. nueva_venta.xml (Formulario de Creación)
   ├── Sección 1: Seleccionar Cliente
   │   ├─ Select de clientes existentes
   │   ├─ Botón: "+ Crear Nuevo Cliente" (collapse)
   │   │   └─ Campo: Nombre | DNI
   │   └─ Confirmación visual del cliente seleccionado
   │
   ├── Sección 2: Agregar Productos
   │   ├─ Select de productos (con precios)
   │   ├─ Input: Cantidad
   │   ├─ Botón: "+ Agregar"
   │   └─ Listado dinámico de líneas agregadas
   │       └─ Cada línea muestra: Producto | Cantidad | Precio Unit | Subtotal
   │       └─ Cada línea tiene: Botón ✕ Eliminar
   │
   ├── Sección 3: Método de Pago
   │   └─ Select de journals (account.journal)
   │
   ├── Sección 4: Resumen
   │   ├─ Información: Cant. productos | Cant. total | Total $
   │   ├─ Botón: "✓ Registrar y Confirmar Venta"
   │   └─ Botón: "← Cancelar"
   │
   └── JavaScript (Dinámico)
       ├─ Gestión de líneas en memoria
       ├─ Cálculo automático de totales
       ├─ Validaciones antes de enviar
       ├─ Llamadas JSON-RPC para crear cliente / crear venta
       └─ Reload de página tras éxito


═══════════════════════════════════════════════════════════════════════════════
🔐 SEGURIDAD
═════════════════════════════════════════════════════════════════════════════════

Todas las rutas validan:
└─ request.env.user.has_group('permisos_usuarios.group_administrador')

Si no pasa validación:
└─ Redirige a home (/)

En JSON-RPC:
└─ Devuelve { success: False, message: 'No tiene permisos.' }

═══════════════════════════════════════════════════════════════════════════════
✅ TESTING Y VALIDACIONES
═════════════════════════════════════════════════════════════════════════════════

Creación de Venta:
✓ Valida cliente existencia
✓ Valida que haya al menos 1 producto
✓ Valida que cantidad > 0
✓ Valida que producto sea sale_ok=True

Confirmación:
✓ Solo en draft
✓ Usa action_confirm() nativo de Odoo (confiable)
✓ Manejo de excepciones silencioso

Cancelación:
✓ No permite cancelar si ya está cancelada
✓ Revierte stock si estaba confirmada

═══════════════════════════════════════════════════════════════════════════════
🚀 USO PRÁCTICO
═════════════════════════════════════════════════════════════════════════════════

CASO 1: Admin crea venta manual
────────────────────────────────
1. Accede a /ventas/nueva
2. Selecciona cliente (o crea uno nuevo)
3. Agrega productos con cantidades
4. Selecciona método de pago (opcional)
5. Clica "Registrar y Confirmar"
   └─ Se crea orden EN VIVO
   └─ Se CONFIRMA automáticamente
   └─ Stock se DESCUENTA

CASO 2: Admin consulta ventas con filtros
────────────────────────────────────────────
1. Accede a /ventas
2. Filtra por:
   └─ En los últimos 7 días
   └─ Cliente "Juan Pérez"
   └─ Categoría "Electrónica"
   └─ Confirmadas
3. Visualiza tabla con resultados

CASO 3: Admin confirma orden en borrador
──────────────────────────────────────────
1. En el dashboard, ve una orden en estado "Borrador"
2. Clica "✓ Confirmar"
3. Sistema confirma (action_confirm)
4. Stock se descuenta
5. Tabla se refreshea automáticamente

CASO 4: Admin cancela venta confirmada
─────────────────────────────────────────
1. En el dashboard, ve una orden "Confirmada"
2. Clica "✕ Cancelar"
3. Sistema cancela (action_cancel)
4. Stock se RESTAURA
5. Tabla se refreshea

═══════════════════════════════════════════════════════════════════════════════
⚠️  CONSIDERACIONES Y NOTAS
═════════════════════════════════════════════════════════════════════════════════

1. Auto-Confirmación
   └─ Las órdenes se confirman AUTOMÁTICAMENTE al crearlas
   └─ Esto es por decisión del usuario en las preguntas iniciales
   └─ Si se desea cambiar: modificar controller (comentar línea action_confirm())

2. Ubicación de Stock
   └─ Se usa WH/Stock (ubicación interna estándar)
   └─ Si el cliente tiene otra configuración, cambiar en controller

3. Métodos de Pago
   └─ Por ahora usa account.journal (campo estándar)
   └─ Es extensible para integraciones futuras (Mercado Pago, etc.)

4. Sin Descuento Automático de Stock ANTES de confirmar
   └─ El stock se descuenta SOLO en action_confirm()
   └─ Esto respeta el flujo nativo de Odoo

5. Validación de Permisos
   └─ Solo administradores pueden acceder
   └─ Todos los endpoints lo validan

═══════════════════════════════════════════════════════════════════════════════
📖 PRÓXIMAS MEJORAS (FUTURO)
═════════════════════════════════════════════════════════════════════════════════

Nivel 1: Básico
├─ Integración con Mercado Pago (payment_method_web selection)
├─ Impresión de órdenes (PDF)
└─ Historial de cambios (audit log)

Nivel 2: Avanzado
├─ Facturación automática
├─ Sistema de devoluciones
├─ Reporte de ventas (gráficos)
└─ Integración con email

Nivel 3: Experto
├─ B2B Portal (clientes web crean sus propias órdenes)
├─ Sistema de descuentos dinámicos
├─ Análisis predictivo de demanda
└─ Integraciones con sistemas ERP


═══════════════════════════════════════════════════════════════════════════════
"""
