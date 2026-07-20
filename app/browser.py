"""
Gerência do ciclo de vida do navegador Playwright.

Mantém **um único** processo de navegador por processo Python e cria um
*browser context* isolado por consulta. Contexts são baratos e independentes
(cookies/estado separados), o que permite **execuções simultâneas** sem abrir
vários navegadores. Um semáforo limita quantas consultas rodam de fato em
paralelo, protegendo memória e CPU.

Windows + uvicorn --reload (ou --workers > 1): o Playwright abre o Chromium
como subprocesso, o que só o ProactorEventLoop suporta no Windows. O uvicorn,
quando `use_subprocess` é verdadeiro (reload ligado ou múltiplos workers),
força de propósito o SelectorEventLoop no processo do servidor — incompatível
(`uvicorn/loops/asyncio.py`). Para não depender de qual loop o uvicorn decidir
usar, todo o Playwright roda numa *thread dedicada* com seu próprio
ProactorEventLoop; as rotas FastAPI permanecem no loop principal do uvicorn e
só atravessam para essa thread via `run_coroutine_threadsafe`.
"""
from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Awaitable, Callable
from typing import TypeVar

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from .config import settings

T = TypeVar("T")

# Script injetado antes de qualquer script da página. Neutraliza os sinais mais
# comuns de automação (navegador controlado por WebDriver), o que é suficiente
# para passar pelo desafio anti-bot (AWS WAF) do Portal da Transparência mesmo
# em modo headless — validado empiricamente.
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
window.chrome = window.chrome || {runtime: {}};
"""


def _nova_loop() -> asyncio.AbstractEventLoop:
    """ProactorEventLoop no Windows (suporta subprocessos); padrão nos demais SOs."""
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()  # type: ignore[attr-defined]
    return asyncio.new_event_loop()


class BrowserManager:
    """
    Singleton do navegador compartilhado, isolado numa thread própria.

    Todas as chamadas públicas (`start`, `stop`, `run`) são corrotinas comuns,
    chamáveis normalmente do loop principal do FastAPI — a travessia para a
    thread do browser é interna e transparente para quem as chama.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_scrapes)

    def _garantir_thread(self) -> None:
        """Sobe a thread com o loop dedicado, se ainda não estiver rodando."""
        if self._thread is not None:
            return
        with self._start_lock:
            if self._thread is not None:
                return
            pronto = threading.Event()

            def _executar_loop() -> None:
                loop = _nova_loop()
                asyncio.set_event_loop(loop)
                self._loop = loop
                pronto.set()
                loop.run_forever()

            self._thread = threading.Thread(
                target=_executar_loop, daemon=True, name="playwright-loop"
            )
            self._thread.start()
            pronto.wait()

    async def _na_thread_do_browser(self, coro: Awaitable[T]) -> T:
        """Agenda `coro` na thread do browser e aguarda o resultado."""
        self._garantir_thread()
        assert self._loop is not None
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return await asyncio.wrap_future(future)

    async def start(self) -> None:
        """Inicia Playwright e o navegador (idempotente)."""
        await self._na_thread_do_browser(self._start_impl())

    async def _start_impl(self) -> None:
        if self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

    async def stop(self) -> None:
        """Encerra navegador, Playwright e a thread dedicada."""
        if self._thread is None:
            return
        await self._na_thread_do_browser(self._stop_impl())
        assert self._loop is not None
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._thread = None
        self._loop = None

    async def _stop_impl(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def run(self, tarefa: Callable[[BrowserContext], Awaitable[T]]) -> T:
        """
        Executa `tarefa(context)` inteiramente na thread do browser, com um
        BrowserContext isolado criado e fechado para essa chamada.

        Uso:
            async def minha_tarefa(ctx):
                page = await ctx.new_page()
                ...
            resultado = await browser_manager.run(minha_tarefa)
        """
        return await self._na_thread_do_browser(self._run_impl(tarefa))

    async def _run_impl(self, tarefa: Callable[[BrowserContext], Awaitable[T]]) -> T:
        if self._browser is None:
            await self._start_impl()
        assert self._browser is not None

        async with self._semaphore:
            ctx = await self._browser.new_context(
                user_agent=settings.user_agent,
                locale=settings.locale,
                viewport={"width": 1366, "height": 900},
            )
            ctx.set_default_timeout(settings.nav_timeout_ms)
            await ctx.add_init_script(_STEALTH_JS)
            try:
                return await tarefa(ctx)
            finally:
                await ctx.close()


# Instância global reutilizada pela API.
browser_manager = BrowserManager()
