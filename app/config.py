"""
Configuração central da aplicação.

Todos os parâmetros ajustáveis (timeouts, URLs, headless, concorrência) e,
principalmente, os **seletores** do Portal da Transparência ficam concentrados
aqui. Isso deixa o scraper resiliente a mudanças de layout do portal: se um
seletor mudar, basta ajustar neste módulo, sem tocar na lógica de navegação.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações lidas de variáveis de ambiente (ou do arquivo .env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Portal da Transparência ---
    portal_base_url: str = "https://portaldatransparencia.gov.br"
    # Página de busca de pessoas físicas. O portal aceita o termo direto na
    # query string, o que evita depender de digitar no campo de busca.
    busca_pf_path: str = "/pessoa-fisica/busca/lista"
    # Query param que ativa o filtro "Beneficiário de Programa Social" — aplicar
    # o filtro pela URL é bem mais robusto do que clicar no checkbox (validado).
    filtro_social_param: str = "beneficiarioProgramaSocial"

    # --- Playwright ---
    headless: bool = True
    # Timeout de navegação/espera por seletores (ms).
    nav_timeout_ms: int = 30_000
    # Tempo máximo total de uma consulta antes de considerar timeout (ms).
    query_timeout_ms: int = 60_000
    # User agent "de navegador real" reduz bloqueios pelo WAF do portal.
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    # Idioma pt-BR para garantir os textos esperados nas mensagens.
    locale: str = "pt-BR"

    # --- Concorrência ---
    # Nº máximo de navegações simultâneas por processo. Protege memória/CPU
    # mesmo que a API receba muitas requisições ao mesmo tempo.
    max_concurrent_scrapes: int = 4

    # --- API ---
    api_title: str = "Robô Portal da Transparência"
    api_version: str = "1.0.0"

    # --- Parte 2: Hiperautomação (Google Drive + Sheets) ---
    # "local": grava em disco (storage/) — usado para demonstração e testes,
    #          sem precisar de credenciais do Google Cloud.
    # "google": envia de verdade ao Drive/Sheets via service account.
    google_integration_mode: str = "local"
    # Caminho do JSON da service account (obrigatório no modo "google").
    google_credentials_path: str | None = None
    # Pasta do Drive e planilha onde os dados serão gravados (modo "google").
    google_drive_folder_id: str | None = None
    google_sheets_id: str | None = None
    # Diretório usado pelo modo "local" para simular Drive (arquivos) e
    # Sheets (CSV).
    local_storage_dir: str = "storage"

    # URL onde a própria API do robô (Parte 1) está servindo. O endpoint de
    # hiperautomação chama POST /consulta por HTTP nessa URL — exatamente
    # como um workflow externo (Make/Activepieces/Zapier) faria.
    robo_api_base_url: str = "http://localhost:8000"


settings = Settings()


# ---------------------------------------------------------------------------
# Seletores do Portal da Transparência.
#
# São mantidos aqui de forma centralizada e com múltiplos fallbacks, porque o
# portal é uma SPA e o layout muda com alguma frequência. Cada campo lista os
# seletores em ordem de preferência; o scraper tenta um a um.
# ---------------------------------------------------------------------------
class Selectors:
    # Botão para fechar/aceitar o banner de cookies (LGPD) do portal, que
    # sobrepõe a página e intercepta cliques se não for dispensado.
    COOKIE_ACEITAR = [
        "#cookiebar button:has-text('Aceitar todos')",
        "#cookiebar button:has-text('Rejeitar cookies opcionais')",
        "button:has-text('Aceitar todos')",
        ".br-cookiebar button.primary",
    ]

    # Cada item/card de resultado da busca (link para o panorama da pessoa).
    RESULTADO_ITEM = [
        "#resultados a.link-busca-nome",
        "a.link-busca-nome",
    ]

    # Contador de resultados. Quando vale "0", a busca não retornou ninguém.
    CONTADOR_RESULTADOS = [
        "#countResultados",
    ]

    # --- Página de panorama (Pessoa Física) ---
    # Bloco de dados cadastrais (Nome, CPF/NIS, Localidade). Sua presença também
    # confirma que a página de panorama terminou de carregar.
    PANORAMA_DADOS = [
        ".dados-tabelados",
    ]

    # Cabeçalho de cada seção do panorama (accordion). Clicar expande/carrega
    # o conteúdo (ex.: "RECEBIMENTOS DE RECURSOS").
    ACCORDION_HEADER = [
        "div.br-accordion button.header",
        "button.header",
    ]

    # Cada item (seção) do accordion, já com título + conteúdo.
    ACCORDION_ITEM = [
        "div.br-accordion div.item",
    ]

    # Título de uma seção do accordion.
    ACCORDION_TITULO = ["span.title", ".header"]

    # Links "Detalhar" de benefícios sociais dentro do panorama.
    # Ex.: /beneficios/auxilio-emergencial/55504153
    DETALHAR_BENEFICIO = [
        "a[href*='/beneficios/']",
    ]
