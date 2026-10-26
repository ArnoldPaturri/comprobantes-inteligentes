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

## Integración disponible en esta rama

El adaptador `control_financiero/integracion.py` lee facturas, cotizaciones y
pagos desde el repositorio documental existente y crea un `BorradorFlete`.
No modifica las hojas originales. Los pagos reconocidos por OCR se importan
como **no acreditados**, con el fin de requerir revisión humana explícita.

Los controles se almacenan aparte como JSON versionado con escritura atómica;
no se sobrescriben los registros existentes ni se admiten IDs repetidos.
Por defecto, el JSON está junto al Excel activo. Una ruta alternativa se
puede pasar con `--control`.

```powershell
python principal.py flete-borrador --factura FAC-01
python principal.py fletes-ver
```

Si se especificó una ruta Excel alternativa, anteponer
`--workbook RUTA_DEL_EXCEL` antes del subcomando.

**Precauciones:** el comando no permite sobreescribir el Excel con JSON,
rechaza IDs ya guardados y no verifica bancos ni detracciones. Antes de
importar un nuevo borrador para el mismo ID, hay que revisar el existente;
la edición y aprobación operativa tendrán un flujo específico posterior.

La implementación actual está diseñada para uso local y secuencial, no
para escritura concurrente por varios usuarios.

## Visualización — primera versión de consulta

Se incorpora la página **Control financiero** en la navegación de Streamlit.
Lee `control_fletes.json` junto al Excel activo; no modifica registros.

- Resumen financiero desagregado por moneda, sin sumas entre PEN y USD.
- Filtros por estado, moneda e identificadores.
- Tabla de facturas, pagos declarados, evidencia acreditada y saldo documental.
- Detalle de respaldos, guías, notas de crédito y observaciones.
- Estilo visual propio inspirado en la paleta de Odoo.

```powershell
python -m streamlit run aplicacion.py
```

**Limitación:** no permite todavía acreditar movimientos, adjuntar guías
ni cerrar conciliaciones. Un control importado se mantiene pendiente hasta
su revisión explícita; esta pantalla es solo lectura.

## Revisión de clasificación del expediente

La interfaz permite seleccionar directamente una fila de la tabla y
registrar, con sustento, la clasificación `flete`, `otra operación` o
`sin clasificar`, el número de guía y la evaluación manual de detracción.

Los presupuestos y diferencias se muestran en los indicadores de fletes
**solo cuando la naturaleza del expediente está confirmada como flete**.
Esta clasificación evita que una compra de materiales se considere por
defecto un flete. Los expedientes no clasificados siguen visibles.

Cada modificación agrega fecha UTC, motivo y campos modificados al historial
local dentro de `control_fletes.json`; no contiene identidad autenticada.
Modificar el expediente reabre cualquier conciliación previamente cerrada.
No se acreditan pagos, no se calculan porcentajes de detracción y el archivo
`registros.xlsx` no se modifica.

La interfaz no implementa aprobaciones finales ni auditoría multiusuario.
El acceso es local, sin identificación del operador; no debe utilizarse como
control interno formal sin incorporar autenticación, autorizaciones y un
registro de auditoría resistente a alteraciones.


## Revisión manual de comprobantes de pago

En el expediente, la pestaña **Revisar pagos** permite seleccionar un
movimiento importado del registro documental y confirmar o retirar su
acreditación **documental declarada**, sin consultar bancos.

Para guardar se exige motivo (mínimo diez caracteres) y una confirmación
explícita de haber examinado por cuenta propia el comprobante original,
la referencia, el importe y la moneda. No se permite acreditar una entrada
sin referencia, respaldo o moneda coherente con la factura. La acción no
modifica el importe, el Excel ni la información de extracción OCR.

Cada cambio se almacena en el historial JSON con fecha UTC, motivo,
referencia, importe y estado anterior/nuevo. Si el expediente cambió desde
que se abrió el formulario, se rechaza el guardado y se solicita actualizar.
Se puede retirar la validación con un nuevo motivo; hacerlo vuelve a
excluir el importe del saldo acreditado.

**Límites:** un comprobante puede ser falso aunque un usuario lo marque
como revisado; no existe confirmación bancaria automatizada, identidad
autenticada del revisor ni auditoría multiusuario. No es una aprobación
final ni una liquidación tributaria.


## Registro manual de detracciones y notas de crédito

El expediente ahora incluye la pestaña **Detracciones y notas**, donde el
usuario puede declarar un importe, referencia, número (para nota de crédito),
nombre del archivo de respaldo y motivo. El registro inicia **sin acreditar**.
El nombre del archivo es una referencia declarada; todavía no existe
almacenamiento o carga física del documento en esta pantalla.

- Las detracciones requieren que la operación esté confirmada como flete y
  que se haya registrado manualmente que la detracción corresponde.
- Las notas de crédito se vinculan a su factura y reducen el importe neto
  solo después de una acreditación documental separada.
- Se rechazan referencias de detracción repetidas y números duplicados
  de notas de crédito dentro del expediente, así como importes inválidos.
- La acreditación y su reversión exigen motivo y confirmación expresa;
  cada cambio se añade al historial local del archivo JSON.
- Ninguna acción modifica el Excel de origen, ni calcula tasas SPOT,
  verifica datos en SUNAT, ni comprueba la autenticidad del archivo indicado.

**Alcance:** las restricciones de duplicados son por expediente; todavía
no existe control transaccional global o de concurrencia multiusuario.
El archivo JSON debe emplearse solo con un operador a la vez.
