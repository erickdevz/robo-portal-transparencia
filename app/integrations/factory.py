"""Seleciona a implementação de Drive/Sheets conforme GOOGLE_INTEGRATION_MODE."""
from __future__ import annotations

from functools import lru_cache

from ..config import settings
from .base import DriveClient, SheetsClient


@lru_cache
def get_drive_client() -> DriveClient:
    if settings.google_integration_mode == "google":
        from .google_client import GoogleDriveClient

        return GoogleDriveClient()
    from .local_client import LocalDriveClient

    return LocalDriveClient()


@lru_cache
def get_sheets_client() -> SheetsClient:
    if settings.google_integration_mode == "google":
        from .google_client import GoogleSheetsClient

        return GoogleSheetsClient()
    from .local_client import LocalSheetsClient

    return LocalSheetsClient()
