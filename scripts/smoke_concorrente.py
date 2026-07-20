"""Dispara N consultas em paralelo para validar execução simultânea real."""
import asyncio
import time

from app.browser import browser_manager
from app.models import ConsultaRequest
from app.scraper import consultar

TERMOS = ["MARIA DA SILVA", "JOSE DOS SANTOS", "ANA OLIVEIRA"]


async def main() -> None:
    await browser_manager.start()
    try:
        inicio = time.monotonic()
        resultados = await asyncio.gather(
            *[consultar(ConsultaRequest(termo=t)) for t in TERMOS]
        )
        duracao = time.monotonic() - inicio
        for t, r in zip(TERMOS, resultados):
            print(f"{t:25s} -> {r.status.value:8s} id={r.identificador_unico}")
        print(f"\n{len(TERMOS)} consultas concorrentes em {duracao:.1f}s")
    finally:
        await browser_manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
