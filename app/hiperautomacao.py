"""
Orquestração da Parte 2 (Hiperautomação).

Reproduz em Python o mesmo fluxo que uma automação low-code (Make,
Activepieces, Zapier) executaria:
    1. Chama a API do robô da Parte 1 (POST /consulta) via HTTP.
    2. Se a consulta teve sucesso, salva o JSON no Google Drive com o nome
       padrão [IDENTIFICADOR_UNICO]_[DATA_HORA].json.
    3. Registra uma linha na planilha centralizada do Google Sheets com o
       identificador, nome, CPF, data/hora e link do arquivo no Drive.

Erros da consulta (status='erro') são apenas propagados — nada é gravado no
Drive/Sheets nesse caso, já que não há dado útil para armazenar. Falhas de
infraestrutura (robô inacessível, Drive/Sheets fora do ar) também nunca
propagam como HTTP 500: viram um HiperautomacaoResponse com status='erro',
no mesmo espírito da Parte 1.
"""
from __future__ import annotations

import httpx

from .config import settings
from .integrations.factory import get_drive_client, get_sheets_client
from .models import (
    ConsultaRequest,
    ConsultaResponse,
    HiperautomacaoResponse,
    StatusConsulta,
)
from .utils import novo_identificador


async def _chamar_robo(req: ConsultaRequest) -> ConsultaResponse:
    """Requisição HTTP à API do robô — o mesmo endpoint que um workflow externo chamaria."""
    timeout = settings.query_timeout_ms / 1000 + 10
    async with httpx.AsyncClient(base_url=settings.robo_api_base_url, timeout=timeout) as client:
        resp = await client.post("/consulta", json=req.model_dump(mode="json"))
        resp.raise_for_status()
        return ConsultaResponse.model_validate(resp.json())


def _nome_arquivo(resultado: ConsultaResponse) -> str:
    carimbo = resultado.data_hora.strftime("%Y%m%d_%H%M%S")
    return f"{resultado.identificador_unico}_{carimbo}.json"


async def processar(req: ConsultaRequest) -> HiperautomacaoResponse:
    """Executa o fluxo completo da Parte 2 e devolve o resultado."""
    try:
        resultado = await _chamar_robo(req)
    except httpx.HTTPError as e:
        return HiperautomacaoResponse(
            status=StatusConsulta.ERRO,
            identificador_unico=novo_identificador(),
            mensagem_erro=f"Não foi possível conectar à API do robô: {e}",
            explicacao=(
                "Não conseguimos falar com o robô da Parte 1. Verifique se a "
                "API está rodando e tente novamente."
            ),
        )

    if resultado.status != StatusConsulta.SUCESSO:
        return HiperautomacaoResponse(
            status=resultado.status,
            identificador_unico=resultado.identificador_unico,
            mensagem_erro=resultado.mensagem_erro,
            explicacao=resultado.explicacao,
        )

    try:
        nome_arquivo = _nome_arquivo(resultado)
        link_drive = await get_drive_client().upload_json(
            nome_arquivo, resultado.model_dump(mode="json")
        )
        await get_sheets_client().append_row(
            identificador_unico=resultado.identificador_unico,
            nome=resultado.dados.nome if resultado.dados else None,
            cpf=resultado.dados.cpf if resultado.dados else None,
            data_hora=resultado.data_hora.isoformat(),
            link_drive=link_drive,
        )
    except Exception as e:
        return HiperautomacaoResponse(
            status=StatusConsulta.ERRO,
            identificador_unico=resultado.identificador_unico,
            mensagem_erro=f"Consulta OK, mas falhou ao gravar no Drive/Sheets: {e}",
            explicacao=(
                "Encontramos os dados da pessoa, mas não conseguimos salvar "
                "no Google Drive/Sheets. Tente novamente ou verifique as "
                "credenciais do Google configuradas."
            ),
        )

    return HiperautomacaoResponse(
        status=resultado.status,
        identificador_unico=resultado.identificador_unico,
        nome_arquivo_drive=nome_arquivo,
        link_drive=link_drive,
    )
