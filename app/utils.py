"""Funções utilitárias puras (sem I/O), fáceis de testar."""
from __future__ import annotations

import re
import uuid

from .models import TipoBusca

_SO_DIGITOS = re.compile(r"\D+")


def apenas_digitos(valor: str) -> str:
    """Remove tudo que não for dígito."""
    return _SO_DIGITOS.sub("", valor or "")


def detectar_tipo(termo: str, tipo: TipoBusca) -> TipoBusca:
    """
    Resolve o tipo de busca.

    Se o chamador informou explicitamente CPF/NIS/NOME, respeita.
    No modo AUTO: termo só com dígitos (11) -> CPF; caso contrário -> NOME.
    """
    if tipo != TipoBusca.AUTO:
        return tipo

    digitos = apenas_digitos(termo)
    if digitos and digitos == termo.strip():
        # Termo puramente numérico: tratamos como CPF (NIS também é numérico;
        # o portal aceita ambos na mesma busca).
        return TipoBusca.CPF
    return TipoBusca.NOME


def termo_de_busca(termo: str, tipo: TipoBusca) -> str:
    """
    Normaliza o termo para envio ao portal: CPF/NIS vão só com dígitos;
    nome vai como está.
    """
    if tipo in (TipoBusca.CPF, TipoBusca.NIS):
        return apenas_digitos(termo)
    return termo.strip()


def novo_identificador() -> str:
    """Identificador único curto para a consulta (usado como nome de arquivo)."""
    return uuid.uuid4().hex[:8]
