# Registro bancario central y aplicaciones (v2)

## Objetivo y límites

Un movimiento bancario es una transferencia única identificada por banco,
referencia normalizada y moneda. Sus **aplicaciones** son importes independientes
asignados a uno o varios expedientes/facturas.

Se trabaja en `feature/control-financiero-fletes`, sin modificar `main`.
El registro se guarda en `movimientos_bancarios_centrales.json`, junto al
Excel configurado. **No modifica** `registros.xlsx` ni `control_fletes.json`.

La vinculación del voucher **no acredita** el movimiento. El estado
`DOCUMENTADO` confirma solo que un operador declaró haber cotejado los
documentos; no es consulta a la entidad bancaria, ni se traslada a los
indicadores o saldos oficiales del control de fletes.

## Formato

La versión 2 separa la cabecera del movimiento y sus aplicaciones:

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
      "sustento": "Transferencia verificada con voucher original",
      "estado": "BORRADOR",
      "respaldo": null,
      "revisiones": []
    }
  ],
  "aplicaciones": [
    {"movimiento_id": "MB-EJEMPLO", "expediente": "FAC-1", "importe": "400"},
    {"movimiento_id": "MB-EJEMPLO", "expediente": "FAC-2", "importe": "600"}
  ]
}
```

El ejemplo ilustra la estructura; el sistema agrega `creado_utc` y otros
campos del modelo. No edites el JSON a mano.

## Reglas de negocio

- La suma de aplicaciones de un movimiento no excede su importe.
- La factura y el movimiento deben usar la misma moneda.
- Se comprueba el saldo que aún no ha sido declarado en el expediente y los
  importes reservados en otros movimientos centrales.
- No se admite una misma factura dos veces dentro de un movimiento.
- Se bloquean referencias de pago compuestas, marcas de efectivo y referencias
  ya presentes en el registro histórico o en otro movimiento central.
- Se bloquea acreditar desde el módulo antiguo un pago cuyo número de
  operación o adjunto se encuentre en el registro central.
- Los adjuntos reutilizan el almacén inmutable por huella SHA-256.
  No se puede asociar el mismo adjunto a dos movimientos centrales.
- Los cambios registran hora UTC, motivo y valores anteriores/nuevos.
- Las escrituras JSON son atómicas y tienen comprobación de huellas para
  rechazar vistas obsoletas. Es un flujo local, no una base de datos multiusuario.

## Flujo en Streamlit

1. En **Control financiero**, abre **Movimientos compartidos** y crea el borrador
   indicando banco, referencia, moneda, total y asignaciones.
2. Abre **Gestionar movimiento existente** y distribuye o corrige los importes.
   El **saldo sin asignar** se mantiene disponible, sin duplicar la transferencia.
3. Carga el voucher bancario original desde el registro central.
4. Revisa manualmente referencia, moneda, total y cada factura, y marca
   `DOCUMENTADO` cuando corresponda.
5. Si hallas un error, **Reabrir para correcciones** revierte la revisión
   documental sin eliminar el voucher ni el historial.
6. Las facturas históricas continúan con su conciliación previa; este registro
   no se convierte automáticamente en pago acreditado.

## Compatibilidad y recuperación

- Se leen archivos centrales v1 con aplicaciones anidadas.
- En la primera escritura exitosa se guarda v2 con movimientos y aplicaciones
  separados. La lectura de v1 por sí sola no transforma el archivo.
- Antes de usar datos reales, haz una copia de
  `movimientos_bancarios_centrales.json` y `control_fletes.json` fuera
  de las carpetas sincronizadas.
- No abras con código antiguo un registro ya convertido a v2: para regresar
  deberías recuperar la copia previa. Los registros existentes de
  `control_fletes.json` no requieren migración.

## Verificación

```powershell
python -m compileall -q src pruebas aplicacion.py principal.py
python -m pytest
python -m ruff check .
streamlit run aplicacion.py
```

Pruebas específicas: `pruebas/test_movimientos_centrales.py`,
`pruebas/test_ciclo_movimientos_centrales.py` y
`pruebas/test_bloqueo_cruce_bancario.py`.
