# Control financiero de fletes — alcance inicial

## Fuente operativa

Dos capturas del proceso actual en Google Sheets muestran: una tabla de
bancarizaciones/detracciones (guía, factura, proveedor, importes y estado);
y un resumen ejecutivo con presupuestos, facturas, diferencias y excepciones.

No se recibieron aún fórmulas ni las hojas originales editables. No se
asume que `Monto bancarizado` equivalga en todos los casos a
`importe pagado al proveedor + depósito de detracción`: el desglose
debe confirmarse con los usuarios del proceso.

## Primera entrega implementada

- `OperacionFlete` con factura, guía, cotización, moneda y evidencias.
- Bancarización: importe asignado a la factura, referencia y respaldo.
- Detracción: depósito declarado separado del pago al proveedor; no
  se infiere porcentaje ni obligación tributaria.
- Nota de crédito: reducción solo si está verificada y respaldada.
- `conciliar_flete()`: saldo provisional, alertas y estado
  CONFORME / PENDIENTE / OBSERVADA.
- `resumir_operaciones()`: agrupación por moneda y por presupuesto
  identificado, sin sumar una cotización varias veces.
- Rechazo de facturas duplicadas o presupuestos incompatibles.

**Verificada** significa verificación humana/documental declarada;
no consulta automática a la entidad bancaria ni a SUNAT.

## Fases pendientes

- Vinculación con los registros actuales del agente; persistencia de
  operaciones y evidencias; importación de las hojas existentes.
- Tratamiento de movimientos bancarios compartidos por varias facturas.
- Reglas tributarias SPOT, valor referencial, retenciones y validaciones.
- Registro de guías y notas de crédito como entidades independientes.
- Cierre de presupuestos, clasificación de sobrecostos confirmados.
- Dashboard Streamlit con filtros, auditoría, estados y exportación.
- Validación funcional contra hojas reales anonimizadas.

## Interpretación monetaria de esta entrega

`facturado_neto = monto_facturado - notas_credito_acreditadas`

`total_acreditado = movimientos_bancarios_verificados
+ depositos_detraccion_verificados`

`saldo_por_acreditar = facturado_neto - total_acreditado`

Estas fórmulas constituyen un **modelo preliminar de conciliación
documental**, no la interpretación confirmada de cada columna de Google
Sheets. Los importes de evidencias pendientes no se consideran acreditados.

Un saldo negativo es excepción. Un saldo positivo en expediente
incompleto queda pendiente; en expediente cerrado y documentado queda
observado. El consolidado por moneda y cotización no equivale a un
estado de sobrecostos aprobados.
