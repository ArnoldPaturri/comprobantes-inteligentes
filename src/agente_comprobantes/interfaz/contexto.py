from dataclasses import dataclass

import streamlit as st

from agente_comprobantes.agente import AgenteComprobantes
from agente_comprobantes.configuracion import Configuracion
from agente_comprobantes.fabrica import crear_agente, crear_repositorio
from agente_comprobantes.repositorios import RepositorioExcel

_CONTEXT_KEY = "_invoice_agent_context"


@dataclass(frozen=True, slots=True)
class ContextoAplicacion:
    settings: Configuracion
    agent: AgenteComprobantes
    repository: RepositorioExcel


def obtener_contexto_aplicacion() -> ContextoAplicacion:
    if _CONTEXT_KEY not in st.session_state:
        settings = Configuracion()
        repository = crear_repositorio(settings)
        repository.inicializar()

        st.session_state[_CONTEXT_KEY] = ContextoAplicacion(
            settings=settings,
            agent=crear_agente(
                settings,
                repository=repository,
            ),
            repository=repository,
        )

    context = st.session_state[_CONTEXT_KEY]

    if not isinstance(context, ContextoAplicacion):
        raise TypeError(
            "El contexto de la aplicación tiene un formato inválido."
        )

    return context