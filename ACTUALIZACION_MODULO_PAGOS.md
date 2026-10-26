# Actualización 0.2.0 — módulo de pagos

Esta actualización agrega el flujo `Factura → Comprobante de pago` sin reemplazar el proyecto
completo.

## Aplicación manual

1. Conserva tu archivo `.env` y la carpeta `output/` actuales.
2. Copia sobre tu proyecto los archivos incluidos respetando sus rutas.
3. Copia `comprobante_pago_prueba_001.png` dentro de `input/samples/`.
4. No borres ni recrees `output/registros.xlsx`: la actualización reutiliza sus cuatro hojas.
5. Ejecuta las pruebas:

```powershell
pytest
ruff check .
```

## Prueba funcional

Usa el ID de la factura original, no el registro marcado como duplicado:

```powershell
python main.py pago --factura FAC-BAFC36C7F5 "input/samples/comprobante_pago_prueba_001.png"
```

El pago ficticio es de `S/ 7,350.00`, operación `98765432`, en moneda `PEN`.

## Comportamiento esperado

- Se crea una fila en `PAGOS`.
- El pago queda vinculado a `FAC-BAFC36C7F5`.
- `FACTURAS` y `COMPARATIVA` cambian a `PAGADO` cuando el comprobante es válido.
- Un pago parcial deja la factura en `PAGO PARCIAL`.
- Un comprobante duplicado, dudoso, con moneda distinta o con sobrepago se registra para revisión,
  pero no se aplica nuevamente a la factura.
