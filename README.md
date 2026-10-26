# Agente IA de comprobantes

Versión: **0.2.0**

Backend modular para registrar cotizaciones desde imágenes, asociarles facturas, comparar
automáticamente lo cotizado con lo facturado y conciliar comprobantes de pago. La extracción
visual usa Cohere Command A Vision; las validaciones, cálculos, duplicados y escritura del Excel
se realizan en Python.

## Alcance de esta versión

- Una o varias imágenes se procesan como un solo documento.
- Registro de cotizaciones con un código interno ingresado por el usuario.
- Registro de facturas asociadas a una cotización existente.
- Comparación de proveedor, moneda y montos.
- Cálculo determinista de diferencia y porcentaje de desvío.
- Detección de posibles duplicados sin eliminarlos automáticamente.
- Registro de Yape, Plin, transferencias, vouchers, depósitos y constancias de pago.
- Pagos totales y parciales acumulables, con detección de moneda distinta y sobrepago.
- Los pagos dudosos o duplicados se registran, pero no se aplican a la factura.
- Estados `VERIFICADO`, `REVISAR`, `ERROR` y `POSIBLE DUPLICADO`.
- Excel con hojas `COTIZACIONES`, `FACTURAS`, `COMPARATIVA` y `PAGOS`.
- Puerto de proveedor desacoplado para poder añadir Gemini u otro modelo más adelante.

## Arquitectura

```text
Imágenes (1..N)
      │
      ▼
ImageService ── valida, orienta, reduce y calcula hash
      │
      ▼
VisionProvider ── Cohere Vision → JSON estructurado
      │
      ├── ValidationService
      ├── DuplicateService
      ├── ReconciliationService
      └── PaymentReconciliationService
                  │
                  ▼
            ExcelRepository
```

`ReceiptAgent` coordina el caso de uso, pero cada responsabilidad vive en una clase independiente.
La futura interfaz Streamlit podrá llamar a `register_quotation()`, `register_invoice()` y
`register_payment()` sin contener lógica de negocio.

## Instalación en Windows

Desde VS Code o Cursor, abre una terminal en la carpeta del proyecto:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edita `.env` y coloca tu clave:

```dotenv
COHERE_API_KEY=tu_clave_real
```

El archivo `.env` está excluido de Git. Nunca subas ni compartas tu API key.

## Uso

Inicializar el Excel:

```powershell
python main.py iniciar
```

Registrar una cotización de una o varias páginas:

```powershell
python main.py cotizacion --codigo COT-2026-001 foto_1.jpg foto_2.jpg
```

Registrar la factura relacionada:

```powershell
python main.py factura --cotizacion COT-2026-001 factura.jpg
```

Registrar un comprobante asociado al ID interno de una factura:

```powershell
python main.py pago --factura FAC-ABC1234567 comprobante_pago.png
```

Consultar la comparativa:

```powershell
python main.py ver --hoja COMPARATIVA
```

También puedes instalar el comando y usar `agente-comprobantes` en vez de `python main.py`.

## Reglas relevantes

- El código de cotización es único y lo ingresa el usuario.
- Una factura solo se procesa si la cotización indicada ya existe; así se evita gastar una llamada
  de IA inútil.
- Los datos no legibles quedan vacíos y el registro se marca para revisión.
- Una coincidencia de duplicado no borra la evidencia: el nuevo registro se conserva marcado.
- Un pago `VERIFICADO` actualiza las hojas `FACTURAS` y `COMPARATIVA`; un pago dudoso o duplicado
  queda en `PAGOS`, pero no modifica el saldo de la factura.
- Los pagos parciales se acumulan hasta completar el monto facturado.
- Reenviar exactamente el mismo código de cotización se bloquea porque ese código es la clave que
  relaciona futuras facturas.
- `Diferencia = Monto facturado - Monto cotizado`.
- `% Desvío = Diferencia / Monto cotizado × 100`.
- Aún no se aplican tolerancias comerciales inventadas; por ahora el diagnóstico solo indica si el
  monto está por encima, coincide o está por debajo.

## Límites de imágenes

Por defecto se aceptan hasta 20 imágenes y 20 MB procesados por expediente. Se corrige la
orientación EXIF, se limita la imagen a 1536 × 2048 y se envía con detalle alto para conservar
texto pequeño. Los formatos admitidos son JPEG, PNG, WEBP y GIF no animado.

## Pruebas y calidad

```powershell
pytest
ruff check .
pytest --cov=invoice_agent --cov-report=term-missing
```

Las pruebas usan un proveedor de visión falso; no consumen llamadas ni tokens de Cohere.

Si Cohere devuelve un valor con formato inesperado, el mensaje mostrará los campos problemáticos
y guardará la respuesta original en `output/diagnostics/`. Ese archivo facilita el diagnóstico y
puede contener información extraída del documento, por lo que no debe compartirse públicamente.

## Estructura

```text
agente_comprobantes/
├── input/samples/
├── output/
├── src/invoice_agent/
│   ├── domain/
│   ├── prompts/
│   ├── providers/
│   ├── repositories/
│   ├── services/
│   ├── agent.py
│   ├── cli.py
│   ├── config.py
│   └── factory.py
├── tests/
├── .env.example
├── main.py
├── pyproject.toml
└── requirements.txt
```

## Próximas fases

1. Probar documentos reales y ajustar el prompt con evidencia.
2. Añadir un repositorio de Google Sheets usando el mismo contrato de persistencia.
3. Construir Streamlit sobre los casos de uso ya probados.
