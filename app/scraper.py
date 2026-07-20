"""
Robô de consulta ao Portal da Transparência (Playwright async).

Fluxo (todos os seletores/rotas foram validados contra o portal real):
    1. Abre a busca de Pessoas Físicas com o termo na query string
       (+ filtro "Beneficiário de Programa Social" via query param, se pedido).
    2. Fecha o banner de cookies (LGPD) e aguarda a lista de resultados —
       ou detecta ausência de resultados via #countResultados == "0".
    3. Abre o primeiro resultado -> tela de panorama.
    4. Coleta dados cadastrais (.dados-tabelados) e expande as seções do
       accordion ("RECEBIMENTOS DE RECURSOS").
    5. Para cada benefício social, segue o link "Detalhar"
       (/beneficios/{tipo}/{id}) e coleta os dados da tela de detalhe.
    6. Captura screenshot da tela e converte para Base64.

Erros de negócio (cenários de teste) são levantados como exceções específicas
(ver app/exceptions.py) e traduzidos em JSON de erro pela função consultar().
"""
from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime
from urllib.parse import quote

from playwright.async_api import BrowserContext, Locator, Page
from playwright.async_api import TimeoutError as PWTimeoutError

from .browser import browser_manager
from .config import Selectors, settings
from .exceptions import ScraperError, SemResultadosError, TempoRespostaError
from .models import (
    Beneficio,
    ConsultaRequest,
    ConsultaResponse,
    DadosPessoa,
    StatusConsulta,
    TipoBusca,
)
from .utils import detectar_tipo, novo_identificador, termo_de_busca

logger = logging.getLogger(__name__)

# Mapeia o "slug" da URL de detalhe do benefício para um nome amigável.
BENEFICIO_SLUGS = {
    "auxilio-emergencial": "Auxílio Emergencial",
    "bolsa-familia": "Bolsa Família",
    "novo-bolsa-familia": "Novo Bolsa Família",
    "auxilio-brasil": "Auxílio Brasil",
    "seguro-defeso": "Seguro Defeso",
    "bpc": "BPC",
    "safra": "Garantia-Safra",
    "peti": "PETI",
}


# --------------------------------------------------------------------------- #
# Helpers de seletores                                                        #
# --------------------------------------------------------------------------- #
async def _primeiro_visivel(page: Page, seletores: list[str]) -> Locator | None:
    """Retorna o primeiro seletor da lista que possui ao menos 1 elemento."""
    for sel in seletores:
        loc = page.locator(sel).first
        try:
            if await loc.count() > 0:
                return loc
        except PWTimeoutError:
            continue
    return None


async def _clicar_seletores(page: Page, seletores: list[str], timeout: int = 4000) -> bool:
    """Tenta clicar no primeiro seletor visível da lista. Não lança exceção."""
    for sel in seletores:
        loc = page.locator(sel).first
        try:
            if await loc.count() and await loc.is_visible():
                await loc.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


# JS executado no navegador para extrair pares rótulo/valor de um bloco
# '.dados-tabelados': cada campo é um container com um <b>/<strong> (rótulo,
# a marcação varia entre o panorama e as telas de detalhe de benefício)
# seguido do valor (texto restante do container). Ler pela estrutura do DOM —
# e não por posição de linha de texto — evita desalinhar os pares quando um
# campo vem vazio (ex.: NIS em branco), que some da lista ao invés de virar
# uma linha vazia.
_JS_EXTRAIR_PARES = """
el => Array.from(el.querySelectorAll('b, strong')).map(rotulo => {
    const clone = rotulo.parentElement.cloneNode(true);
    const rotuloClone = clone.querySelector('b, strong');
    if (rotuloClone) rotuloClone.remove();
    return [rotulo.textContent.trim(), clone.textContent.trim()];
})
"""


async def _pares(bloco: Locator) -> dict[str, str]:
    """Converte um bloco '.dados-tabelados' em pares rótulo->valor, pela estrutura do DOM."""
    try:
        pares = await bloco.evaluate(_JS_EXTRAIR_PARES)
    except PWTimeoutError:
        return {}
    dados: dict[str, str] = {}
    for rotulo, valor in pares:
        # \xad é um hífen de quebra de linha invisível que o portal insere
        # em algumas palavras (ex.: "Benefí\xadcio") — não faz parte do texto.
        rotulo = rotulo.strip().replace("\xad", "")
        if rotulo and rotulo not in dados:
            dados[rotulo] = valor.strip().replace("\xad", "")
    return dados


# --------------------------------------------------------------------------- #
# Etapas de navegação                                                          #
# --------------------------------------------------------------------------- #
async def _dispensar_cookies(page: Page) -> None:
    """Fecha o banner de cookies (LGPD), que intercepta cliques se ficar aberto."""
    await _clicar_seletores(page, Selectors.COOKIE_ACEITAR)


async def _aguardar_resultados(page: Page, timeout_ms: int) -> bool:
    """
    Espera até aparecer um resultado OU o contador indicar 0.

    Retorna True se há resultados, False se a busca retornou 0.
    Levanta PWTimeoutError se nada for decidido dentro do timeout.
    """
    loop = asyncio.get_event_loop()
    fim = loop.time() + timeout_ms / 1000

    while loop.time() < fim:
        item = await _primeiro_visivel(page, Selectors.RESULTADO_ITEM)
        if item is not None and await item.count() > 0:
            return True
        contador = await _primeiro_visivel(page, Selectors.CONTADOR_RESULTADOS)
        if contador is not None:
            try:
                if (await contador.inner_text()).strip() == "0":
                    return False
            except PWTimeoutError:
                pass
        await page.wait_for_timeout(400)

    raise PWTimeoutError("Timeout aguardando resultados da busca")


def _parse_contador(texto: str) -> int | None:
    """Converte '10.000' (formato BR, separador de milhar) em 10000."""
    limpo = texto.strip().replace(".", "").replace(",", "")
    return int(limpo) if limpo.isdigit() else None


async def _contar_resultados(page: Page) -> int | None:
    """Lê quantos resultados a busca encontrou (ex.: 10.000 para 'maria')."""
    contador = await _primeiro_visivel(page, Selectors.CONTADOR_RESULTADOS)
    if contador is None:
        return None
    try:
        return _parse_contador(await contador.inner_text())
    except PWTimeoutError:
        return None


async def _expandir_accordion(page: Page) -> None:
    """Expande todas as seções do accordion do panorama para carregar o conteúdo."""
    for sel in Selectors.ACCORDION_HEADER:
        headers = page.locator(sel)
        try:
            n = await headers.count()
        except PWTimeoutError:
            continue
        for i in range(n):
            try:
                h = headers.nth(i)
                if await h.is_visible():
                    await h.click(timeout=3000, force=True)
                    await page.wait_for_timeout(500)
            except Exception:
                continue
        if n:
            break


async def _coletar_secoes(page: Page) -> dict[str, str]:
    """Coleta cada seção do accordion do panorama como título -> texto."""
    secoes: dict[str, str] = {}
    itens = page.locator(Selectors.ACCORDION_ITEM[0])
    try:
        n = await itens.count()
    except PWTimeoutError:
        return secoes
    for i in range(n):
        item = itens.nth(i)
        titulo = f"secao_{i}"
        for sel in Selectors.ACCORDION_TITULO:
            t = item.locator(sel).first
            try:
                if await t.count():
                    titulo = (await t.inner_text()).strip() or titulo
                    break
            except PWTimeoutError:
                continue
        try:
            conteudo = (await item.inner_text()).strip()
        except PWTimeoutError:
            conteudo = ""
        if conteudo:
            secoes[titulo] = conteudo
    return secoes


async def _detalhar_beneficio(ctx: BrowserContext, url: str, tipo: str) -> Beneficio:
    """Abre a página de detalhe de um benefício e coleta seus dados."""
    detalhes: dict[str, str] = {}
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await _dispensar_cookies(page)
        bloco = await _primeiro_visivel(page, Selectors.PANORAMA_DADOS)
        if bloco is not None:
            detalhes = await _pares(bloco)
    except Exception:
        pass
    finally:
        await page.close()
    return Beneficio(tipo=tipo, detalhes=detalhes)


async def _coletar_beneficios(ctx: BrowserContext, page: Page) -> list[Beneficio]:
    """
    Localiza os links 'Detalhar' de benefícios no panorama e coleta cada um.

    O tipo do benefício é inferido a partir do slug da URL de detalhe
    (ex.: /beneficios/auxilio-emergencial/123 -> "Auxílio Emergencial").
    """
    links = page.locator(Selectors.DETALHAR_BENEFICIO[0])
    urls: list[tuple[str, str]] = []
    try:
        n = await links.count()
    except PWTimeoutError:
        n = 0
    for i in range(n):
        href = await links.nth(i).get_attribute("href")
        if not href:
            continue
        partes = [p for p in href.split("/") if p]
        # espera padrão: ['beneficios', '<slug>', '<id>']
        if len(partes) >= 3 and partes[0] == "beneficios" and partes[-1].isdigit():
            slug = partes[1]
            tipo = BENEFICIO_SLUGS.get(slug, slug.replace("-", " ").title())
            url = href if href.startswith("http") else f"{settings.portal_base_url}{href}"
            if (url, tipo) not in urls:
                urls.append((url, tipo))

    beneficios: list[Beneficio] = []
    for url, tipo in urls:
        beneficios.append(await _detalhar_beneficio(ctx, url, tipo))
    return beneficios


async def _extrair_dados(ctx: BrowserContext, page: Page) -> DadosPessoa:
    """Extrai dados cadastrais + seções + benefícios da tela de panorama."""
    dados = DadosPessoa()

    bloco = await _primeiro_visivel(page, Selectors.PANORAMA_DADOS)
    if bloco is not None:
        pares = await _pares(bloco)
        dados.nome = pares.get("Nome")
        dados.cpf = pares.get("CPF")
        dados.nis = pares.get("NIS")
        dados.localidade = pares.get("Localidade") or pares.get("Município")

    await _expandir_accordion(page)
    dados.secoes = await _coletar_secoes(page)
    dados.beneficios = await _coletar_beneficios(ctx, page)
    return dados


async def _screenshot_base64(page: Page) -> str:
    """Captura a tela inteira e devolve como string Base64 (PNG)."""
    png_bytes = await page.screenshot(full_page=True, type="png")
    return base64.b64encode(png_bytes).decode("ascii")


def _montar_url_busca(termo: str, filtro_social: bool) -> str:
    url = f"{settings.portal_base_url}{settings.busca_pf_path}?termo={quote(termo)}"
    if filtro_social:
        url += f"&{settings.filtro_social_param}=true"
    return url


async def _executar(ctx: BrowserContext, req: ConsultaRequest) -> tuple[DadosPessoa, str]:
    """Faz a navegação completa e devolve (dados, screenshot_base64)."""
    tipo = detectar_tipo(req.termo, req.tipo)
    termo = termo_de_busca(req.termo, tipo)

    page = await ctx.new_page()
    await page.goto(_montar_url_busca(termo, req.filtro_programa_social),
                    wait_until="domcontentloaded")
    await _dispensar_cookies(page)

    # 1) aguarda resultados (ou detecta ausência)
    try:
        tem_resultados = await _aguardar_resultados(page, settings.nav_timeout_ms)
    except PWTimeoutError:
        tem_resultados = False

    if not tem_resultados:
        if tipo == TipoBusca.NOME:
            raise SemResultadosError(req.termo)
        raise TempoRespostaError()

    total_resultados = await _contar_resultados(page)

    # 2) abre o primeiro resultado
    item = await _primeiro_visivel(page, Selectors.RESULTADO_ITEM)
    if item is None:
        raise TempoRespostaError()
    try:
        await item.click()
        await page.wait_for_load_state("domcontentloaded")
    except PWTimeoutError:
        raise TempoRespostaError()

    # 3) confirma que o panorama carregou (bloco de dados cadastrais)
    try:
        await page.wait_for_selector(
            Selectors.PANORAMA_DADOS[0], timeout=settings.nav_timeout_ms
        )
    except PWTimeoutError:
        raise TempoRespostaError()

    # 4) coleta dados + evidência (screenshot após expandir as seções)
    dados = await _extrair_dados(ctx, page)
    dados.total_resultados_encontrados = total_resultados
    evidencia = await _screenshot_base64(page)
    return dados, evidencia


async def consultar(req: ConsultaRequest) -> ConsultaResponse:
    """
    Ponto de entrada do robô. Sempre devolve um ConsultaResponse — nunca
    propaga exceção de negócio: erros viram JSON de erro (status='erro').
    """
    tipo = detectar_tipo(req.termo, req.tipo)
    base = dict(
        identificador_unico=novo_identificador(),
        termo_consultado=req.termo,
        tipo_busca=tipo,
        data_hora=datetime.now(),
    )

    async def _tarefa(ctx: BrowserContext) -> tuple[DadosPessoa, str]:
        return await asyncio.wait_for(
            _executar(ctx, req), timeout=settings.query_timeout_ms / 1000
        )

    try:
        dados, evidencia = await browser_manager.run(_tarefa)
        return ConsultaResponse(
            status=StatusConsulta.SUCESSO,
            dados=dados,
            evidencia_base64=evidencia,
            **base,
        )
    except SemResultadosError as e:
        return ConsultaResponse(
            status=StatusConsulta.ERRO,
            mensagem_erro=e.mensagem,
            explicacao=e.explicacao,
            **base,
        )
    except (TempoRespostaError, asyncio.TimeoutError):
        logger.warning(
            "Timeout consultando termo=%r tipo=%s identificador=%s",
            req.termo, tipo, base["identificador_unico"],
        )
        erro_padrao = TempoRespostaError()
        return ConsultaResponse(
            status=StatusConsulta.ERRO,
            mensagem_erro=erro_padrao.mensagem,
            explicacao=erro_padrao.explicacao,
            **base,
        )
    except ScraperError as e:
        return ConsultaResponse(
            status=StatusConsulta.ERRO,
            mensagem_erro=e.mensagem,
            explicacao=e.explicacao,
            **base,
        )
    except Exception:
        # Falha inesperada (seletor quebrado, portal fora do ar, etc.): loga o
        # traceback real para investigação, mas devolve a mensagem padrão do
        # desafio ao cliente — nunca um 500 cru.
        logger.exception(
            "Falha inesperada consultando termo=%r tipo=%s identificador=%s",
            req.termo, tipo, base["identificador_unico"],
        )
        erro_padrao = TempoRespostaError()
        return ConsultaResponse(
            status=StatusConsulta.ERRO,
            mensagem_erro=erro_padrao.mensagem,
            explicacao=erro_padrao.explicacao,
            **base,
        )
