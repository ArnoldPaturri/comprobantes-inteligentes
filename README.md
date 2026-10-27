# Comprobantes Inteligentes

Agente en Python para extraer información de cotizaciones, facturas, boletas y constancias de pago usando IA; validar datos, identificar posibles duplicados, comparar montos y conciliar pagos parciales o totales. Incluye interfaz Streamlit y comandos de consola.

## Qué hace

- Procesa varias imágenes como un único documento (Cohere / Groq Vision).
- Permite revisar y corregir la extracción antes de registrarla.
- Registra cotizaciones, facturas y comprobantes de pago vinculados.
- Detecta duplicados y conserva el registro para su revisión.
- Calcula diferencias, saldos y pagos aplicados mediante reglas deterministas.
- Mantiene hojas Excel: `COTIZACIONES`, `FACTURAS`, `COMPARATIVA` y `PAGOS`.
- Permite pagos anticipados que se vinculan con la factura posteriormente.

## Estructura de carpetas

```text
comprobantes-inteligentes/
├── src/agente_comprobantes/
│   ├── casos_uso/          Operaciones de cotizaciones, facturas y pagos
│   ├── dominio/            Entidades y modelos del sistema
│   ├── proveedores/        Proveedores de IA: Groq y Cohere
│   ├── repositorios/       Persistencia y operaciones Excel
│   ├── servicios/          Validación, duplicados y conciliación
│   ├── interfaz/           Páginas y componentes Streamlit
│   ├── prompts/            Instrucciones de extracción
│   ├── agente.py           Fachada del agente
│   ├── configuracion.py    Configuración y rutas
│   ├── consola.py          Interfaz de comandos
│   └── fabrica.py          Ensamblaje de dependencias
├── pruebas/                Pruebas automáticas
├── documentacion/          Registro de decisiones
├── entrada/ejemplos/       Solo archivos de ejemplo públicos
├── salida/                 Datos generados (privados y excluidos de Git)
├── principal.py            Entrada para consola
├── aplicacion.py           Entrada para Streamlit
├── pyproject.toml
└── .env.example
```

## Instalar en Windows

Desde la raíz del proyecto:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Si todavía no tienes tu archivo `.env`, crea uno desde `.env.example` y configura las API keys necesarias. Nunca subas el archivo `.env` ni credenciales de Google o documentos privados.

## Recorrido recomendado

1. Abre **Inicio** y sigue la guía rápida que aparece en pantalla.
2. Registra primero la cotización y revisa los campos extraídos antes de guardar.
3. Registra la factura y selecciona su cotización; las diferencias quedan para revisión.
4. Si existe un pago, regístralo desde su imagen y verifica sus datos.
5. En **Control financiero**, usa **Crear expediente financiero desde una factura registrada**. Ya no necesitas ir a la consola para este paso.
6. Adjunta los vouchers y documentos de sustento. Un importe registrado por OCR no se considera acreditado hasta revisar su evidencia.
7. Usa la importación XLSX para lotes; revisa la vista previa, duplicados y advertencias antes de confirmar.

**Formatos:** el OCR de cotizaciones, facturas y pagos trabaja con imágenes aceptadas por cada pantalla. Convierte los PDF a PNG/JPG para esos flujos. Los PDF se pueden usar como evidencia financiera y el importador masivo recibe XLSX.

Consulta [la guía de uso y pruebas de aceptación](documentacion/GUIA_USO_Y_PRUEBAS.md) para el recorrido completo y los resultados esperados.

## Ejecutar

Interfaz gráfica:

```powershell
streamlit run aplicacion.py
```

Consola:

```powershell
python principal.py iniciar
python principal.py cotizacion --codigo COT-2026-001 foto_cotizacion.jpg
python principal.py factura --cotizacion COT-2026-001 foto_factura.jpg
python principal.py pago --cotizacion COT-2026-001 --factura FAC-ABC1234567 foto_pago.png
python principal.py ver --hoja COMPARATIVA
```

Las llamadas a IA no se requieren para ejecutar las pruebas.

## Validación

```powershell
python -m pytest
python -m ruff check .
python -m pytest --cov=agente_comprobantes --cov-report=term-missing
```

## Migración desde el proyecto anterior

- **No borres** las carpetas antiguas `input/`, `output/` ni tu archivo `.env`: pueden contener documentos y registros reales. Siguen excluidas del repositorio.
- El proyecto nuevo utiliza `entrada/` y `salida/`. Los archivos Excel anteriores **no se trasladan automáticamente**.
- Si existe `output/registros.xlsx`, la configuración por defecto de Python lo prioriza para evitar perder continuidad. **Si tu `.env` contiene `WORKBOOK_PATH`, prevalece esa variable**, por lo que deberás revisar esa ruta antes de cambiarla.
- Las estructuras JSON y los nombres de columnas Excel se conservan en inglés o español según su contrato previo, para no romper datos persistidos.
- La rama `main` mantiene el estado anterior; esta reorganización se desarrolla por separado hasta completar su validación.

## Próximas mejoras

Se evaluará integrar LangChain y LangGraph cuando la refactorización, las pruebas y la aplicación estén estabilizadas.
