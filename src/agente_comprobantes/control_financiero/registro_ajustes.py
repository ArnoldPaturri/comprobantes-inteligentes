"""Registro y revisión documental de detracciones y notas de crédito.

Nunca calcula automáticamente detracciones, consulta SUNAT o comprueba pagos
en el banco. Todas las evidencias nuevas empiezan sin acreditar.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from agente_comprobantes.control_financiero.modelos import (
    DepositoDetraccion,
    NotaCredito,
    OperacionFlete,
    RevisionExpediente,
    importe_positivo,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)

TipoEvidencia = Literal["detraccion", "nota_credito"]


def _validar_revision(
    operacion: OperacionFlete,
    version_esperada: int,
    motivo: str,
    confirmacion: bool,
) -> str:
    if len(operacion.revisiones) != version_esperada:
        raise ValueError("El expediente cambió. Actualiza la página antes de guardar.")
    if not confirmacion:
        raise ValueError("Confirma que revisaste la información presentada.")
    motivo = motivo.strip()
    if len(motivo) < 10:
        raise ValueError("El motivo de revisión requiere al menos diez caracteres.")
    return motivo


def _coleccion(tipo: TipoEvidencia) -> str:
    if tipo == "detraccion":
        return "depositos_detraccion"
    if tipo == "nota_credito":
        return "notas_credito"
    raise ValueError("Tipo documental no permitido.")


def _validar_importe(valor: str) -> Decimal:
    importe = importe_positivo(valor)
    if importe != importe.quantize(Decimal("0.01")):
        raise ValueError("El importe debe tener como máximo dos decimales.")
    return importe


def preparar_registro_evidencia(
    operacion: OperacionFlete,
    *,
    tipo: TipoEvidencia,
    referencia: str,
    respaldo: str,
    monto: str,
    numero: str | None = None,
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
) -> OperacionFlete:
    """Agrega evidencia no acreditada y registra el cambio en el historial."""
    motivo = _validar_revision(operacion, version_esperada, motivo, confirmacion)
    campo = _coleccion(tipo)
    referencia = referencia.strip()
    respaldo = respaldo.strip()
    if not referencia or not respaldo:
        raise ValueError("La evidencia requiere referencia y nombre de archivo de respaldo.")
    importe = _validar_importe(monto)

    if tipo == "detraccion":
        if operacion.es_flete is not True or operacion.detraccion_aplica is not True:
            raise ValueError(
                "Para registrar una detracción, confirma que es un flete "
                "y que corresponde una detracción."
            )
        if any(
            item.referencia and item.referencia.casefold() == referencia.casefold()
            for item in operacion.depositos_detraccion
        ):
            raise ValueError("Ya existe una detracción con esa referencia.")
        if importe > operacion.monto_facturado:
            raise ValueError("La detracción no puede superar el importe de la factura.")
        evidencia = DepositoDetraccion(
            referencia=referencia,
            documento_respaldo=respaldo,
            importe=importe,
            moneda=operacion.moneda,
            verificada=False,
        )
    else:
        numero = (numero or "").strip()
        if not numero:
            raise ValueError("La nota de crédito requiere un número de documento.")
        if any(
            item.numero.casefold() == numero.casefold()
            for item in operacion.notas_credito
        ):
            raise ValueError("Ya existe una nota de crédito con ese número.")
        importe_registrado = sum(
            (item.importe for item in operacion.notas_credito), Decimal("0")
        )
        if importe_registrado + importe > operacion.monto_facturado:
            raise ValueError(
                "El importe acumulado de las notas de crédito supera la factura."
            )
        evidencia = NotaCredito(
            numero=numero,
            referencia=referencia,
            documento_respaldo=respaldo,
            importe=importe,
            moneda=operacion.moneda,
            verificada=False,
        )

    datos = operacion.model_dump(mode="python")
    datos[campo] = [
        *datos[campo],
        evidencia.model_dump(mode="python"),
    ]
    revision = RevisionExpediente(
        fecha=datetime.now(UTC),
        motivo=motivo,
        cambios={
            "accion": "registro_sin_acreditacion",
            "tipo": tipo,
            "referencia": referencia,
            "importe": str(importe),
            "moneda": operacion.moneda.value,
            "respaldo_declarado": respaldo,
        },
    )
    datos["revisiones"] = [*operacion.revisiones, revision]
    datos["conciliacion_cerrada"] = False
    return OperacionFlete.model_validate(datos)


def guardar_registro_evidencia(
    repositorio: RepositorioControlFletes,
    identificador: str,
    **argumentos,
) -> OperacionFlete:
    actual = repositorio.obtener(identificador)
    if actual is None:
        raise ValueError(f"No existe el expediente {identificador}.")
    actualizado = preparar_registro_evidencia(actual, **argumentos)
    repositorio.actualizar(actualizado)
    return actualizado


def preparar_revision_evidencia(
    operacion: OperacionFlete,
    *,
    tipo: TipoEvidencia,
    indice: int,
    acreditar: bool,
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
) -> OperacionFlete:
    """Acredita o revoca evidencia declarada tras comprobación humana."""
    motivo = _validar_revision(operacion, version_esperada, motivo, confirmacion)
    campo = _coleccion(tipo)
    lista = getattr(operacion, campo)
    if isinstance(indice, bool) or not isinstance(indice, int) or not 0 <= indice < len(lista):
        raise ValueError("El documento seleccionado no existe.")
    original = lista[indice]
    if original.verificada == acreditar:
        raise ValueError("La acreditación seleccionada ya estaba registrada.")
    if acreditar:
        if not original.referencia or not original.referencia.strip():
            raise ValueError("No se puede acreditar sin referencia.")
        if not original.documento_respaldo or not original.documento_respaldo.strip():
            raise ValueError("No se puede acreditar sin respaldo identificado.")
        if original.moneda != operacion.moneda:
            raise ValueError("La moneda del documento no coincide con la factura.")
        if tipo == "detraccion" and (
            operacion.es_flete is not True or operacion.detraccion_aplica is not True
        ):
            raise ValueError("La detracción no corresponde a un flete confirmado.")

    datos = operacion.model_dump(mode="python")
    datos[campo][indice]["verificada"] = acreditar
    datos["revisiones"] = [
        *operacion.revisiones,
        RevisionExpediente(
            fecha=datetime.now(UTC),
            motivo=motivo,
            cambios={
                "accion": "acreditar" if acreditar else "retirar_acreditacion",
                "tipo": tipo,
                "indice": str(indice),
                "referencia": original.referencia or "",
                "importe": str(original.importe),
                "respaldo_declarado": original.documento_respaldo or "",
            },
        ),
    ]
    datos["conciliacion_cerrada"] = False
    return OperacionFlete.model_validate(datos)


def guardar_revision_evidencia(
    repositorio: RepositorioControlFletes,
    identificador: str,
    **argumentos,
) -> OperacionFlete:
    actual = repositorio.obtener(identificador)
    if actual is None:
        raise ValueError(f"No existe el expediente {identificador}.")
    actualizado = preparar_revision_evidencia(actual, **argumentos)
    repositorio.actualizar(actualizado)
    return actualizado
