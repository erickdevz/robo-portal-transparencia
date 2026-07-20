"""
Testes da orquestração da Parte 2 (Hiperautomação).

Usam o modo local de Drive/Sheets (padrão do projeto) redirecionado para um
diretório temporário, e substituem a chamada HTTP ao robô por um fake — sem
tocar o Portal da Transparência nem qualquer serviço do Google.
"""
from datetime import datetime

import pytest

import app.hiperautomacao as hiper
from app.config import settings
from app.integrations import factory
from app.models import (
    ConsultaRequest,
    ConsultaResponse,
    DadosPessoa,
    StatusConsulta,
    TipoBusca,
)


@pytest.fixture(autouse=True)
def _storage_temporario(tmp_path, monkeypatch):
    """Isola cada teste em seu próprio diretório e limpa o cache dos clients."""
    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    factory.get_drive_client.cache_clear()
    factory.get_sheets_client.cache_clear()
    yield
    factory.get_drive_client.cache_clear()
    factory.get_sheets_client.cache_clear()


def _resposta_sucesso() -> ConsultaResponse:
    return ConsultaResponse(
        status=StatusConsulta.SUCESSO,
        identificador_unico="abc12345",
        termo_consultado="MARIA DA SILVA",
        tipo_busca=TipoBusca.NOME,
        data_hora=datetime(2026, 7, 20, 10, 0, 0),
        dados=DadosPessoa(nome="MARIA DA SILVA", cpf="***.111.111-**"),
        evidencia_base64="iVBORw0KGgo=",
    )


async def test_sucesso_grava_arquivo_no_drive_local(monkeypatch, tmp_path):
    async def fake_chamar_robo(req):
        return _resposta_sucesso()

    monkeypatch.setattr(hiper, "_chamar_robo", fake_chamar_robo)

    resultado = await hiper.processar(ConsultaRequest(termo="MARIA DA SILVA"))

    assert resultado.status == StatusConsulta.SUCESSO
    assert resultado.nome_arquivo_drive == "abc12345_20260720_100000.json"
    assert resultado.link_drive is not None

    arquivo = tmp_path / "drive" / resultado.nome_arquivo_drive
    assert arquivo.exists()


async def test_sucesso_registra_linha_na_planilha(monkeypatch, tmp_path):
    async def fake_chamar_robo(req):
        return _resposta_sucesso()

    monkeypatch.setattr(hiper, "_chamar_robo", fake_chamar_robo)

    await hiper.processar(ConsultaRequest(termo="MARIA DA SILVA"))

    sheet = (tmp_path / "sheet.csv").read_text(encoding="utf-8")
    assert "abc12345" in sheet
    assert "MARIA DA SILVA" in sheet


async def test_erro_nao_grava_nada(monkeypatch, tmp_path):
    async def fake_chamar_robo(req):
        return ConsultaResponse(
            status=StatusConsulta.ERRO,
            identificador_unico="zzz99999",
            termo_consultado="Fulano Inexistente",
            tipo_busca=TipoBusca.NOME,
            data_hora=datetime(2026, 7, 20, 10, 0, 0),
            mensagem_erro="Foram encontrados 0 resultados para o termo Fulano Inexistente",
        )

    monkeypatch.setattr(hiper, "_chamar_robo", fake_chamar_robo)

    resultado = await hiper.processar(ConsultaRequest(termo="Fulano Inexistente"))

    assert resultado.status == StatusConsulta.ERRO
    assert resultado.link_drive is None
    assert resultado.mensagem_erro == (
        "Foram encontrados 0 resultados para o termo Fulano Inexistente"
    )
    assert not (tmp_path / "drive").exists()
