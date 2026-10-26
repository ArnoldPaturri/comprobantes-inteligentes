from dataclasses import dataclass

import streamlit as st

from agente_comprobantes.agente import ReceiptAgent
from agente_comprobantes.configuracion import Settings
from agente_comprobantes.fabrica import build_agent, build_repository
from agente_comprobantes.repositorios import ExcelRepository

_CONTEXT_KEY = "_invoice_agent_context"


@dataclass(frozen=True, slots=True)
class AppContext:
    settings: Settings
    agent: ReceiptAgent
    repository: ExcelRepository


def get_app_context() -> AppContext:
    if _CONTEXT_KEY not in st.session_state:
        settings = Settings()
        repository = build_repository(settings)
        repository.initialize()

        st.session_state[_CONTEXT_KEY] = AppContext(
            settings=settings,
            agent=build_agent(
                settings,
                repository=repository,
            ),
            repository=repository,
        )

    context = st.session_state[_CONTEXT_KEY]

    if not isinstance(context, AppContext):
        raise TypeError(
            "El contexto de la aplicación tiene un formato inválido."
        )

    return context