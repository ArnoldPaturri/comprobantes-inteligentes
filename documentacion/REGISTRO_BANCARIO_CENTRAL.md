# Registro bancario central y aplicaciones (v2)

## Objetivo y límites

Un movimiento bancario representa una transferencia única, identificada por banco,
referencia normalizada y moneda. Sus **aplicaciones** son importes independientes
asignados a una o varias facturas.

El registro central se guarda en `movimientos_bancarios_centrales.json`, junto al
Excel configurado. No modifica `registros.xlsx`. La preparación y revisión
documental tampoco alteran los saldos de `control_fletes.json`; estos solo cambian
cuando una persona confirma explícitamente **Aplicar a facturas** o **Revertir aplicación**.

La marca de aplicación significa que un operador cotejó la evidencia y autorizó
su reflejo en el control financiero. **No consulta la entidad bancaria, no valida
SUNAT y no es una confirmación bancaria automática.**

## Formato

La versión 2 separa cabecera y aplicaciones:

```json
{
  "version": 2,
  "movimientos": [
    {
      "identificador": "MB-EJEMPLO",
      "banco": "BCP",
      "referencia": "OP-123",
      "moneda": "PEN",
      "importe_total": "1000",
      "sustento": "Transferencia cotejada con el voucher original",
      "estado": "DOCUMENTADO",
      "respaldo": "adjunto:<sha256>.pdf",
      "revisiones": []
    }
  ],
  "aplicaciones": [
    {"movimiento_id": "MB-EJEMPLO", "expediente": "FAC-1", "importe": "400"},
    {"movimiento_id": "MB-EJEMPLO", "expediente": "FAC-2", "importe": "600"}
  ]
}
```

El ejemplo ilustra la estructura; el sistema agrega `creado_utc` y otros campos.
No edites el JSON manualmente.

## Ciclo de vida

- `BORRADOR`: distribución editable; no afecta los saldos.
- `DOCUMENTADO`: voucher original adjunto y cotejo humano registrado; todavía no
  afecta los saldos oficiales.
- `APLICADO`: las aplicaciones se han reflejado en los expedientes y entran en
  el cálculo de conciliación como evidencia documental revisada.
- `REVERTIDO`: se retiró el efecto de conciliación, pero el movimiento, sus
  aplicaciones, el voucher y el historial se conservan.
- Un movimiento `APLICADO` debe revertirse antes de corregir su distribución.
  Después puede reabrirse, redistribuirse, documentarse de nuevo y reaplicarse.

## Reglas de negocio

- La suma aplicada no supera el total del movimiento; cada importe es positivo y
  usa máximo dos decimales.
- La factura y el movimiento deben usar la misma moneda.
- La disponibilidad considera pagos históricos y aplicaciones de otros movimientos
  centrales, evitando contar dos veces una aplicación central ya registrada.
- Se bloquean referencias compuestas, marcas de efectivo, referencias históricas
  duplicadas y vouchers reutilizados en movimientos diferentes.
- Cada pago originado por el registro central conserva `movimiento_central_id`.
  El módulo de revisión individual, el editor de incidencias y la edición de
  adjuntos no pueden modificarlo: debe gestionarse desde Movimientos compartidos.
- La aplicación o reversión actualiza todos los expedientes implicados en una
  sola escritura atómica de `control_fletes.json`; después actualiza el estado
  central. Las operaciones son idempotentes para poder finalizar el estado si
  el proceso se interrumpe después de guardar el lote.
- Si falla la actualización del estado central tras escribir el lote, vuelve a
  cargar la pantalla y repite la misma acción. El servicio detecta las
  aplicaciones existentes y evita añadir pagos duplicados.
- Las revisiones guardan hora UTC, motivo, referencia, importes y cambios. Revertir
  una aplicación no borra los registros: marca sus pagos como no verificados.
- Los JSON usan escritura atómica y huellas para rechazar vistas obsoletas. Es un
  flujo local de un operador; no sustituye una base de datos multiusuario.

## Flujo en Streamlit

1. En **Control financiero → Movimientos bancarios compartidos**, crea el borrador
   indicando banco, referencia, moneda, total y asignaciones por factura.
2. Gestiona la distribución y comprueba el importe sin asignar.
3. Adjunta el voucher bancario original desde el registro central.
4. Contrasta manualmente banco, referencia, fecha, importe, moneda y facturas;
   marca `DOCUMENTADO`.
5. Revisa nuevamente la distribución y selecciona **Aplicar a facturas**. El
   sistema crea o actualiza un movimiento vinculado en cada expediente y registra
   la revisión humana.
6. Si detectas un error, selecciona **Revertir aplicación**. Los importes dejan
   de computar en la conciliación, sin borrar la evidencia ni la auditoría.
7. Para corregir la asignación, reabre el movimiento revertido, redistribuye,
   documenta y aplica nuevamente. No uses el formulario individual de pagos para
   cambiar aplicaciones centrales.

## Compatibilidad y recuperación

- Se leen archivos centrales v1 con aplicaciones anidadas. La primera escritura
  válida los migra a v2 con cabecera y aplicaciones separadas.
- `MovimientoBancario.movimiento_central_id` es opcional para los registros
  históricos; los JSON existentes de `control_fletes.json` siguen siendo válidos.
- Antes de usar datos reales, respalda `movimientos_bancarios_centrales.json`,
  `control_fletes.json` y la carpeta `adjuntos_financieros` fuera de carpetas
  sincronizadas.
- No abras un registro v2 con código antiguo: recupera el respaldo previo si
  necesitas volver a una versión anterior.

## Verificación

```powershell
python -m compileall -q src pruebas aplicacion.py principal.py
python -m pytest
python -m ruff check .
streamlit run aplicacion.py
```

Pruebas específicas: `pruebas/test_movimientos_centrales.py`,
`pruebas/test_ciclo_movimientos_centrales.py`,
`pruebas/test_aplicacion_movimientos_centrales.py` y
`pruebas/test_bloqueo_cruce_bancario.py`.
