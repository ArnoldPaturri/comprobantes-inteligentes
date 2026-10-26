"""Los comandos de control financiero no requieren llamadas a IA."""

import json
from decimal import Decimal

from agente_comprobantes.consola import main
from agente_comprobantes.control_financiero.integracion import BorradorFlete
from agente_comprobantes.control_financiero.modelos import OperacionFlete
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)
from agente_comprobantes.dominio.enumeraciones import Moneda


def test_comando_borrador_y_lectura_no_instancia_agente(
    monkeypatch, tmp_path, capsys
) -> None:
    from agente_comprobantes import consola

    class RepositorioLectura:
        pass

    def sin_ia(*_args, **_kwargs):
        raise AssertionError("Este comando no debe instanciar Groq ni Cohere.")

    monkeypatch.setattr(consola, "crear_agente", sin_ia)
    monkeypatch.setattr(consola, "crear_repositorio", lambda _settings: RepositorioLectura())

    op = OperacionFlete(
        identificador="FAC-1",
        numero_factura="F001-1",
        moneda=Moneda.PEN,
        monto_facturado=Decimal("100"),
    )

    def preparar(_repo, identificador):
        assert identificador == "FAC-1"
        return BorradorFlete(operacion=op, advertencias=["Pendiente de evidencias."])

    monkeypatch.setattr(consola, "crear_borrador_desde_repositorio", preparar)
    control = tmp_path / "control_fletes.json"
    libro = tmp_path / "registros.xlsx"
    main([
        "--workbook", str(libro),
        "flete-borrador", "--factura", "FAC-1", "--control", str(control),
    ])
    salida = json.loads(capsys.readouterr().out)
    assert salida["estado"]["situacion"] == "PENDIENTE"
    assert salida["operacion"]["identificador"] == "FAC-1"
    assert RepositorioControlFletes(control).obtener("FAC-1") == op

    main(["fletes-ver", "--control", str(control)])
    estados = json.loads(capsys.readouterr().out)
    assert [item["identificador"] for item in estados] == ["FAC-1"]


def test_comando_impide_sobrescribir_excel(tmp_path, capsys) -> None:
    import pytest

    libro = tmp_path / "registros.xlsx"
    with pytest.raises(SystemExit) as error:
        main([
            "--workbook", str(libro),
            "fletes-ver", "--control", str(libro),
        ])
    assert error.value.code == 1
    assert "no puede reemplazar el Excel" in capsys.readouterr().err
