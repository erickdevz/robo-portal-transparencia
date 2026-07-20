"""
Contratos das integrações de armazenamento da Parte 2.

Definidos como Protocol para que a orquestração (`app/hiperautomacao.py`)
não precise saber se está falando com o Google de verdade ou com o stand-in
local usado para demonstração/testes — só troca a implementação (ver
`app/integrations/factory.py`).
"""
from __future__ import annotations

from typing import Protocol


class DriveClient(Protocol):
    async def upload_json(self, nome_arquivo: str, conteudo: dict) -> str:
        """Envia o JSON e devolve um link direto para o arquivo salvo."""
        ...


class SheetsClient(Protocol):
    async def append_row(
        self,
        identificador_unico: str,
        nome: str | None,
        cpf: str | None,
        data_hora: str,
        link_drive: str,
    ) -> None:
        """Acrescenta uma linha com os dados da consulta na planilha."""
        ...
