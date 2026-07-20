"""
API FastAPI que expõe o robô da Parte 1 e o fluxo de hiperautomação da Parte 2.

- GET  /                            -> front-end web (formulário de consulta).
- POST /consulta                    -> executa o robô e devolve o JSON (dados + evidência).
- POST /hiperautomacao/processar    -> chama o robô, salva no Drive e registra no Sheets.
- GET  /health                      -> healthcheck.
- Swagger UI em /docs, OpenAPI em /openapi.json.

Projetada para **execuções simultâneas**: cada requisição roda em seu próprio
browser context (ver app/browser.py), limitado por um semáforo de concorrência.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .browser import browser_manager
from .config import settings
from .hiperautomacao import processar as processar_hiperautomacao
from .models import ConsultaRequest, ConsultaResponse, HiperautomacaoResponse
from .scraper import consultar

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Sobe o navegador uma vez na inicialização e encerra no shutdown."""
    await browser_manager.start()
    yield
    await browser_manager.stop()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=(
        "Robô de coleta de dados de Pessoa Física no **Portal da Transparência**.\n\n"
        "Recebe Nome, CPF ou NIS e devolve um JSON com os dados do panorama, os "
        "benefícios sociais e uma evidência (screenshot) em Base64."
    ),
    lifespan=lifespan,
)


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/health", tags=["infra"], summary="Healthcheck")
async def health() -> dict[str, str]:
    return {"status": "ok", "versao": settings.api_version}


@app.post(
    "/consulta",
    response_model=ConsultaResponse,
    tags=["consulta"],
    summary="Consulta uma Pessoa Física no Portal da Transparência",
    response_description="JSON com dados coletados e evidência, ou mensagem de erro.",
)
async def post_consulta(req: ConsultaRequest) -> JSONResponse:
    """
    Executa o robô para o termo informado.

    Retorna sempre HTTP 200 com um envelope `status` em `sucesso`/`erro`,
    conforme os cenários de teste do desafio. O status HTTP 422 fica reservado
    para erros de validação de entrada.
    """
    resultado: ConsultaResponse = await consultar(req)
    # HTTP 200 em ambos os casos; o campo `status` diferencia sucesso/erro.
    return JSONResponse(
        status_code=200,
        content=resultado.model_dump(mode="json"),
    )


@app.post(
    "/hiperautomacao/processar",
    response_model=HiperautomacaoResponse,
    tags=["hiperautomação"],
    summary="Parte 2: consulta o robô, salva no Google Drive e registra no Google Sheets",
    response_description="Nome do arquivo e link no Drive, ou mensagem de erro propagada.",
)
async def post_hiperautomacao(req: ConsultaRequest) -> JSONResponse:
    """
    Executa o fluxo completo da Parte 2 (Hiperautomação).

    Modo controlado por `GOOGLE_INTEGRATION_MODE`: `local` (padrão, grava em
    `storage/` para demonstração/testes) ou `google` (Drive/Sheets reais via
    service account).
    """
    resultado: HiperautomacaoResponse = await processar_hiperautomacao(req)
    return JSONResponse(
        status_code=200,
        content=resultado.model_dump(mode="json"),
    )
