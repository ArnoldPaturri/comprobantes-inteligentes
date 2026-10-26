from agente_comprobantes.dominio.enumeraciones import DocumentType


def _nullable(value_schema: dict) -> dict:
    return {"anyOf": [value_schema, {"type": "null"}]}


DOCUMENT_TYPE_VALUES = [item.value for item in DocumentType]

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {"type": "string", "enum": DOCUMENT_TYPE_VALUES},
        "provider": _nullable({"type": "string"}),
        "provider_tax_id": _nullable({"type": "string"}),
        "concept": _nullable({"type": "string"}),
        "document_number": _nullable({"type": "string"}),
        "document_date": _nullable({"type": "string", "format": "date"}),
        "total_amount_raw": _nullable({"type": "string"}),
        "total_amount": _nullable({"type": "number"}),
        "currency": _nullable(
            {"type": "string", "enum": ["PEN", "USD", "EUR", "OTRA"]}
        ),
        "operation_number": _nullable({"type": "string"}),
        "payment_entity": _nullable({"type": "string"}),
        "quotation_reference": _nullable({"type": "string"}),
        "confidence": {"type": "number"},
        "uncertain_fields": {"type": "array", "items": {"type": "string"}},
        "observations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "document_type",
        "provider",
        "provider_tax_id",
        "concept",
        "document_number",
        "document_date",
        "total_amount_raw",
        "total_amount",
        "currency",
        "operation_number",
        "payment_entity",
        "quotation_reference",
        "confidence",
        "uncertain_fields",
        "observations",
    ],
    "additionalProperties": False,
}


def build_extraction_prompt(
    expected_type: DocumentType,
    page_count: int,
) -> str:
    return f"""
Analiza las {page_count} imagen(es) adjuntas como un único expediente documental.
El usuario espera registrar un documento de tipo {expected_type.value}.

Si el tipo esperado es CONSTANCIA_PAGO, clasifica el documento real como
TRANSFERENCIA_BANCARIA, YAPE, PLIN, VOUCHER_POS, DEPOSITO o CONSTANCIA_PAGO.

Devuelve exclusivamente un objeto JSON plano con los datos extraídos.
La raíz debe contener directamente document_type, provider, provider_tax_id
y los demás campos solicitados.
No devuelvas una definición JSON Schema y no incluyas las claves type,
properties, required ni additionalProperties.

Reglas generales obligatorias:
1. Clasifica el tipo real del documento; no copies automáticamente el esperado.
2. Extrae únicamente información visible y legible.
3. Nunca inventes, completes o deduzcas valores ausentes.
4. Si un dato no existe o no puede confirmarse, devuelve null.
5. Si un campo es dudoso, devuelve null y agrega su nombre exacto a
   uncertain_fields.
6. Si varias imágenes pertenecen al mismo documento, combina la información
   sin duplicarla.
7. Usa fechas en formato YYYY-MM-DD.
8. Usa PEN, USD, EUR u OTRA para currency. No conviertas monedas.
9. No determines si una fecha es pasada o futura. Limítate a transcribirla.
10. observations debe contener solamente incidencias visuales útiles y breves.

Reglas estrictas para montos:
1. total_amount_raw debe reproducir exactamente el texto completo del monto
   visible, incluyendo símbolo, espacios, puntos y comas.
2. total_amount debe ser la normalización numérica de total_amount_raw.
3. Conserva todos los grupos de dígitos situados a la izquierda del decimal.
4. Ejemplos equivalentes:
   "30 117.62" -> 30117.62
   "30,117.62" -> 30117.62
   "30.117,62" -> 30117.62
   "S/ 30 117.62" -> 30117.62
5. Verifica visualmente el monto una segunda vez antes de responder.
6. Nunca uses 0 para representar un monto desconocido o ilegible.
7. Si no puedes leer el monto completo, devuelve null tanto en
   total_amount_raw como en total_amount y agrega "total_amount" a
   uncertain_fields.
8. total_amount es el total final del documento. En comprobantes de pago es
   el importe efectivamente pagado o amortizado, no el saldo, subtotal,
   impuesto ni monto original de una deuda.

Reglas para cotizaciones y facturas:
1. provider es el beneficiario, comercio, servicio o proveedor pagado.
   Devuelve solamente su nombre, sin etiquetas como GIRADO=, BENEFICIARIO:
   o PROVEEDOR:
2. provider_tax_id es el identificador tributario del emisor.
3. document_number es el número de cotización, factura, boleta, nota o recibo.
4. operation_number y payment_entity deben ser null si no corresponden.

Reglas para pagos:
1. provider es el beneficiario, comercio, servicio o proveedor pagado.
2. payment_entity es el banco o billetera utilizado, por ejemplo BCP, BBVA,
   Interbank, Yape o Plin.
3. No uses el banco como provider si solamente actúa como entidad de pago.
4. provider_tax_id corresponde al beneficiario. No uses el RUC del banco que
   aparezca en encabezados, pies de página o información legal.
5. operation_number es el código o número identificador de la operación.
6. Una fecha o una hora nunca debe devolverse como operation_number.
7. Si no existe un número de operación legible, devuelve null y agrega
   "operation_number" a uncertain_fields.
8. Para pagos, document_number debe ser null salvo que exista un número de
   documento distinto del número de operación.

confidence debe estar entre 0 y 1. Si total_amount es incierto o ilegible,
confidence no puede ser mayor que 0.69.
""".strip()