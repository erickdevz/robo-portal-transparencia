"""
Stand-ins locais de Drive/Sheets.

Usados no modo de demonstração (GOOGLE_INTEGRATION_MODE=local, o padrão) para
exercitar o fluxo completo da Parte 2 sem depender de credenciais do Google
Cloud: gravam em disco (storage/drive/*.json e storage/sheet.csv) exatamente
os mesmos dados que as versões reais enviariam ao Google.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from ..config import settings


class LocalDriveClient:
    def __init__(self) -> None:
        self._dir = Path(settings.local_storage_dir) / "drive"
        self._dir.mkdir(parents=True, exist_ok=True)

    async def upload_json(self, nome_arquivo: str, conteudo: dict) -> str:
        caminho = self._dir / nome_arquivo
        caminho.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return caminho.resolve().as_uri()


class LocalSheetsClient:
    _CABECALHO = ["identificador_unico", "nome", "cpf", "data_hora", "link_drive"]

    def __init__(self) -> None:
        self._arquivo = Path(settings.local_storage_dir) / "sheet.csv"
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        if not self._arquivo.exists():
            with self._arquivo.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self._CABECALHO)

    async def append_row(
        self,
        identificador_unico: str,
        nome: str | None,
        cpf: str | None,
        data_hora: str,
        link_drive: str,
    ) -> None:
        with self._arquivo.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [identificador_unico, nome or "", cpf or "", data_hora, link_drive]
            )
