# Guía de uso y pruebas de aceptación

Esta guía cubre el recorrido funcional de Comprobantes Inteligentes desde la primera carga hasta la conciliación y los reportes.

> **Entorno de prueba:** usar documentos inventados y una base vacía o aislada. No mezclar estas pruebas con facturas, pagos o expedientes reales.

## 1. Preparación

Desde PowerShell, en la carpeta del proyecto, ejecuta primero:

```powershell
git status --short --branch
```

Si aparecen cambios locales sin guardar, detente y respáldalos antes de cambiar de rama. Si el árbol está limpio, ejecuta:

```powershell
git switch feature/ux-guia-y-pruebas
git pull --ff-only origin feature/ux-guia-y-pruebas
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

Antes de limpiar o cambiar rutas, confirma dónde están el libro XLSX activo y el archivo `control_fletes.json`. Haz una copia de seguridad; no borres `.env`, `.venv`, el repositorio Git ni documentos de ejemplo.

## 2. Orden de carga en la interfaz

### Paso 1 — Cotizaciones

- Abre **Documentos → Registrar cotización**.
- Ingresa un código interno único, por ejemplo `COT-TEST-001`.
- Sube las imágenes de una sola cotización. Si tiene varias páginas, selecciónalas juntas.
- Pulsa **Analizar cotización**.
- Revisa proveedor, fecha, moneda e importe y corrige cualquier dato incorrecto antes de confirmar.
- Repite para las cotizaciones de prueba restantes.

### Paso 2 — Facturas

- Abre **Registrar factura**.
- Selecciona la cotización que corresponde a la factura.
- Sube la imagen o imágenes de la factura, analiza y revisa los datos.
- No corrijas automáticamente las diferencias: confirma el valor del documento y conserva la observación.
- Guarda y repite para las demás facturas.

### Paso 3 — Pagos por OCR

- Abre **Registrar pago** y selecciona la cotización.
- Si la factura ya existe, vincula el pago con ella; si todavía no existe, deja el pago pendiente de vinculación.
- Sube la imagen, analiza y revisa importe, fecha, moneda y número de operación.
- Un pago extraído por OCR queda como dato registrado; no es una confirmación bancaria ni se acredita automáticamente.

### Paso 4 — Expediente financiero

- Abre **Control financiero**.
- En **Crear expediente financiero desde una factura registrada**, selecciona la factura guardada en el Excel y pulsa **Crear expediente financiero**.
- El nuevo bloque de la interfaz evita tener que ejecutar la orden de consola para cada factura.
- Clasifica manualmente si es flete u otra operación, completa la guía cuando corresponda y registra el sustento de la revisión.
- Adjunta vouchers, constancias, notas de crédito y otros respaldos al expediente correspondiente.

## 3. Casos funcionales y resultados esperados

| Caso | Acción | Resultado esperado |
|---|---|---|
| Cotización válida | Registrar una imagen con código único | Se muestra la extracción revisable y se guarda al confirmar |
| Factura relacionada | Registrar una factura seleccionando su cotización | La factura queda asociada a la cotización seleccionada |
| Diferencia de importe | Cotización de S/ 600 y factura de S/ 620 | Se detecta una diferencia de S/ 20; el operador la revisa |
| Pago parcial OCR | Registrar S/ 150 sobre una factura de S/ 450 | Saldo referencial de S/ 300 antes de otros movimientos; pago sin acreditar hasta revisar evidencia |
| Movimiento central compartido | Voucher OP-TEST-001 de S/ 1,320 aplicado como S/ 700 + S/ 620 a dos facturas | La suma de aplicaciones coincide con el total del voucher y no duplica importes |
| Pago complementario | Aplicar OP-TEST-002 por S/ 300 a la primera factura | Completa el saldo de S/ 300 que quedó después de aplicar S/ 700 |
| Sobreasignación | Intentar aplicar S/ 301 cuando solo hay S/ 300 disponibles | La operación se rechaza; no debe guardarse una asignación por encima del saldo |
| Referencia repetida | Intentar registrar nuevamente OP-TEST-001 | La operación se bloquea o se envía a revisión; no se crea un segundo pago |
| Reversión y reaplicación | Revertir OP-TEST-002, revisar el historial y volver a aplicarlo | La evidencia y el historial se conservan; no se crea un pago duplicado |
| Detracción | Registrar y revisar constancia de S/ 50 para la factura de S/ 500 | Solo cuenta como acreditada después de la revisión documental |
| Nota de crédito | Registrar una nota de crédito de S/ 25 para la misma factura | Facturado neto de S/ 475; la nota no se suma a pagos acreditados |
| Conciliación con ajustes | Acreditar la detracción de S/ 50 y no registrar otros pagos para esa factura | Saldo documental esperado de S/ 425 sobre el neto de S/ 475 |
| Importación limpia | Subir `15_Importacion_Masiva_Lote_Limpio.xlsx` | Vista previa con tres facturas únicas; la importación solo se confirma tras revisión |
| Importación con incidencias | Subir `16_Importacion_Masiva_Casos_Auditoria.xlsx` | Se identifican referencias múltiples/compartidas, duplicados, efectivo, diferencia y monto inválido; no confirmar un lote bloqueado |
| Reportes | Descargar ZIP CSV e informe ejecutivo XLSX | Se generan archivos de consulta sin modificar el libro fuente |

## 4. Reglas que se deben comprobar

- **Registrado no equivale a acreditado.** La IA puede leer un importe, pero la evidencia debe revisarse manualmente.
- **No confundir nota de crédito con pago.** La nota reduce el importe facturado neto; no es un abono bancario.
- **No asumir una detracción.** Su aplicación se declara y revisa; el sistema no determina obligaciones tributarias automáticamente.
- **No dividir movimientos ambiguos.** Una referencia compartida o varias referencias en una celda requieren una asignación explícita y sustentada.
- **No duplicar importes.** Un movimiento central aplicado a varias facturas conserva un total único; las aplicaciones individuales deben sumar exactamente lo distribuido.
- **El Excel y el control financiero son persistencias distintas.** Guardar una factura en el libro documental no implica que su expediente de control ya exista.
- **Los reportes son exportaciones de consulta.** No reemplazan la evidencia original ni confirman movimientos de banco o SUNAT.

## 5. Verificación técnica después de los cambios

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

Si alguna prueba falla, guarda la salida completa y no cambies de rama ni limpies la base hasta identificar la causa.

## 6. Reinicio final

Cuando termine el recorrido, respalda la evidencia generada. Después, ejecuta el procedimiento de limpieza aprobado para volver a dejar el entorno de pruebas vacío. Verifica que el Excel y `control_fletes.json` estén limpios y conserva el paquete ficticio fuera de las carpetas de entrada productivas.

Todos los nombres, RUC, cuentas, referencias e importes de los documentos de prueba deben ser ficticios y estar marcados como tales. No se deben usar para operaciones reales.
