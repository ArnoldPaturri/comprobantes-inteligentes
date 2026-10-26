from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.control_financiero.conciliacion import conciliar_flete
from agente_comprobantes.control_financiero.integracion import crear_borrador_desde_repositorio
from agente_comprobantes.control_financiero.repositorio_json import RepositorioControlFletes
from agente_comprobantes.dominio import TipoDocumento
from agente_comprobantes.excepciones import ErrorAgenteComprobantes
from agente_comprobantes.fabrica import crear_agente, crear_repositorio


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agente-comprobantes",
        description="Extrae y concilia cotizaciones, facturas y pagos desde imágenes.",
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        help="Ruta alternativa para el archivo XLSX.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("iniciar", help="Crea o valida la estructura del Excel.")

    preview = subparsers.add_parser(
        "extraer",
        help="Extrae información sin guardar ni conciliar el documento.",
    )
    preview.add_argument(
        "--tipo",
        required=True,
        choices=tuple(
            document_type.value
            for document_type in TipoDocumento
        ),
        help="Tipo de documento esperado.",
    )
    preview.add_argument(
        "imagenes",
        nargs="+",
        help="Una o más imágenes del documento.",
    )

    quotation = subparsers.add_parser("cotizacion", help="Registra una cotización.")
    quotation.add_argument("--codigo", required=True, help="Código interno único.")
    quotation.add_argument("imagenes", nargs="+", help="Una o más imágenes del documento.")

    invoice = subparsers.add_parser("factura", help="Registra y compara una factura.")
    invoice.add_argument("--cotizacion", required=True, help="Código de cotización asociado.")
    invoice.add_argument("imagenes", nargs="+", help="Una o más imágenes del documento.")

    payment = subparsers.add_parser(
        "pago",
        help="Registra un pago asociado a una cotización.",
    )
    payment.add_argument(
        "--cotizacion",
        required=True,
        help="Código de cotización asociado.",
    )
    payment.add_argument(
        "--factura",
        help="ID interno de factura, si ya existe.",
    )
    payment.add_argument(
        "imagenes",
        nargs="+",
        help="Una o más imágenes del comprobante.",
    )

    payment_link = subparsers.add_parser(
        "vincular-pago",
        help="Vincula un pago pendiente con una factura existente.",
    )
    payment_link.add_argument(
        "--pago",
        required=True,
        help="ID interno del pago.",
    )
    payment_link.add_argument(
        "--factura",
        required=True,
        help="ID interno de la factura.",
    )

    show = subparsers.add_parser("ver", help="Muestra registros del Excel.")
    show.add_argument(
        "--hoja",
        choices=["COTIZACIONES", "FACTURAS", "COMPARATIVA", "PAGOS"],
        default="COMPARATIVA",
    )
    flete = subparsers.add_parser(
        "flete-borrador",
        help="Importa un control pendiente desde una factura existente del Excel.",
    )
    flete.add_argument("--factura", required=True, help="ID interno de factura.")
    flete.add_argument("--control", type=Path, help="Archivo JSON de control independiente.")

    listado = subparsers.add_parser(
        "fletes-ver",
        help="Muestra el estado de los controles de fletes registrados.",
    )
    listado.add_argument("--control", type=Path, help="Archivo JSON de control independiente.")
    return parser


def _configuracion_desde_argumentos(args: argparse.Namespace) -> Configuracion:
    return Configuracion(workbook_path=args.workbook) if args.workbook else Configuracion()


def main(argv: list[str] | None = None) -> None:
    parser = crear_parser()
    args = parser.parse_args(argv)
    settings = _configuracion_desde_argumentos(args)

    try:
        if args.command == "iniciar":
            repository = crear_repositorio(settings)
            repository.inicializar()
            print(f"Excel preparado: {repository.ubicacion}")
            return

        if args.command == "ver":
            repository = crear_repositorio(settings)
            repository.inicializar()
            records = repository.leer_hoja(args.hoja)
            print(json.dumps(records, ensure_ascii=False, indent=2, default=str))
            return

        if args.command in {"flete-borrador", "fletes-ver"}:
            ruta_control = args.control or settings.ruta_archivo_excel().with_name(
                "control_fletes.json"
            )
            if ruta_control.expanduser().resolve() == settings.ruta_archivo_excel().resolve():
                raise ValueError("El archivo de control no puede reemplazar el Excel.")
            control = RepositorioControlFletes(ruta_control)
            if args.command == "flete-borrador":
                borrador = crear_borrador_desde_repositorio(
                    crear_repositorio(settings), args.factura
                )
                control.agregar(borrador.operacion)
                respuesta = {
                    "control": control.ubicacion,
                    "operacion": borrador.operacion.model_dump(mode="json"),
                    "advertencias": borrador.advertencias,
                    "estado": conciliar_flete(borrador.operacion).model_dump(mode="json"),
                }
            else:
                respuesta = [
                    conciliar_flete(operacion).model_dump(mode="json")
                    for operacion in control.listar()
                ]
            print(json.dumps(respuesta, ensure_ascii=False, indent=2))
            return

        agent = crear_agente(settings)

        if args.command == "extraer":
            result = agent.previsualizar_extraccion(
                TipoDocumento(args.tipo),
                args.imagenes,
            )
        elif args.command == "cotizacion":
            result = agent.registrar_cotizacion(
                args.codigo,
                args.imagenes,
            )
        elif args.command == "factura":
            result = agent.registrar_factura(
                args.cotizacion,
                args.imagenes,
            )
        elif args.command == "pago":
            result = agent.registrar_pago(
                args.cotizacion,
                args.imagenes,
                invoice_id=args.factura,
            )
        else:  # vincular-pago
            result = agent.vincular_pago(
                args.pago,
                args.factura,
            )

        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    except (ErrorAgenteComprobantes, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        print("\nOperación cancelada.", file=sys.stderr)
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
