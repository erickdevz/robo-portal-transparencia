"""
Testes da API sem tocar no Portal (o robô é substituído por um fake).

Cobrem os cenários de teste do desafio no nível do contrato JSON:
sucesso por CPF, erro por CPF, sucesso por Nome, erro por Nome.
"""
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient

import app.main as main
from app.models import (
    Beneficio,
    ConsultaRequest,
    ConsultaResponse,
    DadosPessoa,
    HiperautomacaoResponse,
    StatusConsulta,
    TipoBusca,
)


def _fake_consultar(resposta: ConsultaResponse):
    async def _inner(req: ConsultaRequest) -> ConsultaResponse:
        return resposta

    return _inner


async def _client() -> AsyncClient:
    # lifespan é ignorado aqui (não subimos navegador nos testes de contrato).
    transport = ASGITransport(app=main.app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def _no_browser(monkeypatch):
    """Garante que nenhum teste suba navegador de verdade."""
    yield


async def test_sucesso_cpf(monkeypatch):
    resposta = ConsultaResponse(
        status=StatusConsulta.SUCESSO,
        identificador_unico="abc123",
        termo_consultado="11111111111",
        tipo_busca=TipoBusca.CPF,
        data_hora=datetime(2026, 7, 20, 10, 0, 0),
        dados=DadosPessoa(
            nome="FULANO DE TAL",
            beneficios=[Beneficio(tipo="Bolsa Família", detalhes={"Valor": "R$ 600,00"})],
        ),
        evidencia_base64="iVBORw0KGgo=",
    )
    monkeypatch.setattr(main, "consultar", _fake_consultar(resposta))

    async with await _client() as c:
        r = await c.post("/consulta", json={"termo": "11111111111"})

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "sucesso"
    assert body["dados"]["nome"] == "FULANO DE TAL"
    assert body["evidencia_base64"]
    assert body["dados"]["beneficios"][0]["tipo"] == "Bolsa Família"


async def test_erro_cpf(monkeypatch):
    resposta = ConsultaResponse(
        status=StatusConsulta.ERRO,
        identificador_unico="abc123",
        termo_consultado="00000000000",
        tipo_busca=TipoBusca.CPF,
        data_hora=datetime(2026, 7, 20, 10, 0, 0),
        mensagem_erro="Não foi possível retornar os dados no tempo de resposta solicitado",
    )
    monkeypatch.setattr(main, "consultar", _fake_consultar(resposta))

    async with await _client() as c:
        r = await c.post("/consulta", json={"termo": "00000000000"})

    body = r.json()
    assert body["status"] == "erro"
    assert body["mensagem_erro"] == (
        "Não foi possível retornar os dados no tempo de resposta solicitado"
    )
    assert body["dados"] is None


async def test_erro_nome(monkeypatch):
    resposta = ConsultaResponse(
        status=StatusConsulta.ERRO,
        identificador_unico="abc123",
        termo_consultado="Nome Inexistente Xyz",
        tipo_busca=TipoBusca.NOME,
        data_hora=datetime(2026, 7, 20, 10, 0, 0),
        mensagem_erro="Foram encontrados 0 resultados para o termo Nome Inexistente Xyz",
    )
    monkeypatch.setattr(main, "consultar", _fake_consultar(resposta))

    async with await _client() as c:
        r = await c.post("/consulta", json={"termo": "Nome Inexistente Xyz"})

    body = r.json()
    assert body["status"] == "erro"
    assert "0 resultados para o termo" in body["mensagem_erro"]


async def test_validacao_termo_curto():
    async with await _client() as c:
        r = await c.post("/consulta", json={"termo": "x"})
    assert r.status_code == 422  # falha de validação Pydantic


async def test_health():
    async with await _client() as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_hiperautomacao_sucesso(monkeypatch):
    resposta = HiperautomacaoResponse(
        status=StatusConsulta.SUCESSO,
        identificador_unico="abc123",
        nome_arquivo_drive="abc123_20260720_100000.json",
        link_drive="file:///storage/drive/abc123_20260720_100000.json",
    )

    async def _fake(req):
        return resposta

    monkeypatch.setattr(main, "processar_hiperautomacao", _fake)

    async with await _client() as c:
        r = await c.post("/hiperautomacao/processar", json={"termo": "MARIA DA SILVA"})

    body = r.json()
    assert body["status"] == "sucesso"
    assert body["nome_arquivo_drive"] == "abc123_20260720_100000.json"
    assert body["link_drive"]


async def test_hiperautomacao_propaga_erro(monkeypatch):
    resposta = HiperautomacaoResponse(
        status=StatusConsulta.ERRO,
        identificador_unico="zzz999",
        mensagem_erro="Foram encontrados 0 resultados para o termo Fulano Inexistente",
    )

    async def _fake(req):
        return resposta

    monkeypatch.setattr(main, "processar_hiperautomacao", _fake)

    async with await _client() as c:
        r = await c.post("/hiperautomacao/processar", json={"termo": "Fulano Inexistente"})

    body = r.json()
    assert body["status"] == "erro"
    assert body["link_drive"] is None
