from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agente_comprobantes.configuracion import Settings
from agente_comprobantes.dominio import DocumentType
from agente_comprobantes.excepciones import InvoiceAgentError
from agente_comprobantes.fabrica import build_agent, build_repository


def build_parser() -> argparse.ArgumentParser:
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
            for document_type in DocumentType
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
    return parser


def _settings_from_args(args: argparse.Namespace) -> Settings:
    return Settings(workbook_path=args.workbook) if args.workbook else Settings()


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = _settings_from_args(args)

    try:
        if args.command == "iniciar":
            repository = build_repository(settings)
            repository.initialize()
            print(f"Excel preparado: {repository.location}")
            return

        if args.command == "ver":
            repository = build_repository(settings)
            repository.initialize()
            records = repository.read_sheet(args.hoja)
            print(json.dumps(records, ensure_ascii=False, indent=2, default=str))
            return

        agent = build_agent(settings)

        if args.command == "extraer":
            result = agent.preview_extraction(
                DocumentType(args.tipo),
                args.imagenes,
            )
        elif args.command == "cotizacion":
            result = agent.register_quotation(
                args.codigo,
                args.imagenes,
            )
        elif args.command == "factura":
            result = agent.register_invoice(
                args.cotizacion,
                args.imagenes,
            )
        elif args.command == "pago":
            result = agent.register_payment(
                args.cotizacion,
                args.imagenes,
                invoice_id=args.factura,
            )
        else:  # vincular-pago
            result = agent.link_payment(
                args.pago,
                args.factura,
            )

        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    except (InvoiceAgentError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        print("\nOperación cancelada.", file=sys.stderr)
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
