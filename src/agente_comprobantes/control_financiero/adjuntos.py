"""Adjuntar o reemplazar respaldos sin alterar las hojas Excel.

El vínculo nuevo invalida la acreditación documental previa, si existe.
No convierte el nombre original en una ruta de archivo y no acredita pagos.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from agente_comprobantes.control_financiero.archivos import (
    AlmacenAdjuntos,
    preparar_adjunto,
)
from agente_comprobantes.control_financiero.modelos import (
    OperacionFlete,
    RevisionExpediente,
)
from agente_comprobantes.control_financiero.registro_ajustes import (
    preparar_registro_evidencia,
)
from agente_comprobantes.control_financiero.repositorio_json import (
    RepositorioControlFletes,
)

DestinoRespaldo = Literal["pago", "detraccion", "nota_credito"]
CAMPOS = {
    "pago": "movimientos_bancarios",
    "detraccion": "depositos_detraccion",
    "nota_credito": "notas_credito",
}


def preparar_vinculacion(
    operacion: OperacionFlete,
    *,
    destino: DestinoRespaldo,
    indice: int,
    referencia_archivo: str,
    nombre_original: str,
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
) -> OperacionFlete:
    if len(operacion.revisiones) != version_esperada:
        raise ValueError("El expediente cambió; actualiza la pantalla.")
    if destino not in CAMPOS:
        raise ValueError("Tipo documental desconocido.")
    campo = CAMPOS[destino]
    items = getattr(operacion, campo)
    if isinstance(indice, bool) or not isinstance(indice, int) or not 0 <= indice < len(items):
        raise ValueError("La evidencia seleccionada no existe.")
    if not referencia_archivo.startswith("adjunto:"):
        raise ValueError("La referencia de archivo no es válida.")
    if not confirmacion or len(motivo.strip()) < 10:
        raise ValueError("Confirma la vinculación e indica un motivo de al menos 10 caracteres.")

    anterior = items[indice]
    if anterior.documento_respaldo == referencia_archivo:
        raise ValueError("Ese mismo archivo ya está vinculado a la evidencia.")
    datos = operacion.model_dump(mode="python")
    datos[campo][indice]["documento_respaldo"] = referencia_archivo
    datos[campo][indice]["verificada"] = False
    datos["conciliacion_cerrada"] = False
    datos["revisiones"] = [
        *operacion.revisiones,
        RevisionExpediente(
            fecha=datetime.now(UTC),
            motivo=motivo.strip(),
            cambios={
                "accion": "vincular_adjunto",
                "tipo": destino,
                "indice": str(indice),
                "archivo_original": nombre_original,
                "respaldo_anterior": anterior.documento_respaldo or "",
                "respaldo_nuevo": referencia_archivo,
                "acreditacion_anterior": str(anterior.verificada),
                "acreditacion_actual": "False",
            },
        ),
    ]
    return OperacionFlete.model_validate(datos)


def guardar_adjunto_existente(
    repositorio: RepositorioControlFletes,
    almacen: AlmacenAdjuntos,
    identificador: str,
    *,
    destino: DestinoRespaldo,
    indice: int,
    nombre: str,
    contenido: bytes,
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
) -> OperacionFlete:
    actual = repositorio.obtener(identificador)
    if actual is None:
        raise ValueError(f"No existe el expediente {identificador}.")
    preparado = preparar_adjunto(nombre, contenido)
    cambiado = preparar_vinculacion(
        actual,
        destino=destino,
        indice=indice,
        referencia_archivo=preparado.referencia,
        nombre_original=nombre,
        motivo=motivo,
        confirmacion=confirmacion,
        version_esperada=version_esperada,
    )
    almacen.guardar(preparado)
    repositorio.actualizar(cambiado)
    return cambiado


def guardar_ajuste_con_archivo(
    repositorio: RepositorioControlFletes,
    almacen: AlmacenAdjuntos,
    identificador: str,
    *,
    tipo: Literal["detraccion", "nota_credito"],
    referencia: str,
    monto: str,
    numero: str | None,
    nombre: str,
    contenido: bytes,
    motivo: str,
    confirmacion: bool,
    version_esperada: int,
) -> OperacionFlete:
    """Primero valida expediente y documento; después persiste ambos.

    Si falla la escritura JSON posterior, el adjunto puede quedar huérfano,
    pero ningún registro financiero ni Excel será sobrescrito.
    """
    actual = repositorio.obtener(identificador)
    if actual is None:
        raise ValueError(f"No existe el expediente {identificador}.")
    preparado = preparar_adjunto(nombre, contenido)
    actualizado = preparar_registro_evidencia(
        actual,
        tipo=tipo,
        referencia=referencia,
        respaldo=preparado.referencia,
        monto=monto,
        numero=numero,
        motivo=motivo,
        confirmacion=confirmacion,
        version_esperada=version_esperada,
    )
    # El nombre original se conserva solo en el historial, nunca como ruta.
    actualizado.revisiones[-1].cambios["archivo_original"] = nombre
    almacen.guardar(preparado)
    repositorio.actualizar(actualizado)
    return actualizado
