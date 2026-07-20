"""
Integração real com Google Drive e Google Sheets via service account
(OAuth 2.0 servidor-a-servidor). Usada quando GOOGLE_INTEGRATION_MODE=google.

Configuração necessária (variáveis de ambiente, nunca credenciais em código):
    GOOGLE_CREDENTIALS_PATH  caminho do JSON da service account.
    GOOGLE_DRIVE_FOLDER_ID   pasta do Drive compartilhada com a service account.
    GOOGLE_SHEETS_ID         planilha compartilhada com a service account.

Escopos usados (least privilege):
    - drive.file:    a aplicação só enxerga/edita arquivos que ela mesma criou,
                      nunca o Drive inteiro da conta.
    - spreadsheets:  leitura/escrita da planilha informada.

Importante (LGPD): os dados armazenados incluem CPF e evidências pessoais.
NÃO torne a pasta do Drive pública — compartilhe apenas com as contas que
realmente precisam do acesso (ex.: a própria service account e a equipe).
"""
from __future__ import annotations

import asyncio
import json
from functools import lru_cache

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

from ..config import settings

_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]


@lru_cache
def _credentials() -> service_account.Credentials:
    if not settings.google_credentials_path:
        raise RuntimeError(
            "GOOGLE_CREDENTIALS_PATH não configurado (obrigatório no modo 'google')."
        )
    return service_account.Credentials.from_service_account_file(
        settings.google_credentials_path, scopes=_SCOPES
    )


class GoogleDriveClient:
    def __init__(self) -> None:
        self._service = build(
            "drive", "v3", credentials=_credentials(), cache_discovery=False
        )

    async def upload_json(self, nome_arquivo: str, conteudo: dict) -> str:
        return await asyncio.to_thread(self._upload_sync, nome_arquivo, conteudo)

    def _upload_sync(self, nome_arquivo: str, conteudo: dict) -> str:
        media = MediaInMemoryUpload(
            json.dumps(conteudo, ensure_ascii=False, indent=2).encode("utf-8"),
            mimetype="application/json",
        )
        metadata: dict = {"name": nome_arquivo}
        if settings.google_drive_folder_id:
            metadata["parents"] = [settings.google_drive_folder_id]
        arquivo = (
            self._service.files()
            .create(body=metadata, media_body=media, fields="id, webViewLink")
            .execute()
        )
        return arquivo["webViewLink"]


class GoogleSheetsClient:
    def __init__(self) -> None:
        self._service = build(
            "sheets", "v4", credentials=_credentials(), cache_discovery=False
        )

    async def append_row(
        self,
        identificador_unico: str,
        nome: str | None,
        cpf: str | None,
        data_hora: str,
        link_drive: str,
    ) -> None:
        await asyncio.to_thread(
            self._append_sync, identificador_unico, nome, cpf, data_hora, link_drive
        )

    def _append_sync(
        self,
        identificador_unico: str,
        nome: str | None,
        cpf: str | None,
        data_hora: str,
        link_drive: str,
    ) -> None:
        if not settings.google_sheets_id:
            raise RuntimeError(
                "GOOGLE_SHEETS_ID não configurado (obrigatório no modo 'google')."
            )
        self._service.spreadsheets().values().append(
            spreadsheetId=settings.google_sheets_id,
            range="A:E",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={
                "values": [
                    [identificador_unico, nome or "", cpf or "", data_hora, link_drive]
                ]
            },
        ).execute()
