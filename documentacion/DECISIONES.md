# Decisiones técnicas

## Separación entre extracción y negocio

El modelo de visión clasifica y transcribe. No calcula diferencias, porcentajes, diagnósticos ni
estados. Estas reglas quedan en Python porque deben ser reproducibles y auditables.

## Una llamada por expediente

Todas las páginas de un mismo documento se mandan juntas. El prompt pide clasificación y
extracción en una sola respuesta JSON para reducir costo y latencia.

## Modelo interno más amplio que la comparativa

Las hojas de origen conservan RUC, moneda, hash, campos inciertos, archivos y fecha de registro.
La hoja `COMPARATIVA` mantiene las 13 columnas solicitadas como vista de negocio.

## Asociación explícita

El usuario indica el código de cotización al cargar una factura. No se delega esta relación crítica
a una inferencia del modelo. El sistema sí valida después proveedor, moneda y montos.

## Duplicados no destructivos

Se usan, en orden, el hash normalizado de imágenes, RUC + número de documento, número de
operación y una combinación de proveedor, monto, fecha, moneda y descripción. Las coincidencias se
marcan; no se borran automáticamente.

## Persistencia intercambiable

`DocumentRepository` evita que la lógica conozca detalles de openpyxl. Una futura clase
`GoogleSheetsRepository` podrá reemplazar `ExcelRepository` sin modificar `AgenteComprobantes`.

## Estados

- `VERIFICADO`: no se detectaron incidencias.
- `REVISAR`: hay advertencias o campos inciertos.
- `ERROR`: falta un campo crítico, el tipo no coincide o existe una inconsistencia severa.
- `POSIBLE DUPLICADO`: existe una coincidencia con un documento previo.

