"""
Smoke test manual contra o Portal da Transparência real.

Uso:
    python scripts/smoke.py "MARIA"
    python scripts/smoke.py "11111111111"

Imprime um resumo do resultado (sem despejar o Base64 inteiro).
"""
import asyncio
import sys

from app.browser import browser_manager
from app.models import ConsultaRequest
from app.scraper import consultar


async def main(termo: str) -> None:
    await browser_manager.start()
    try:
        req = ConsultaRequest(termo=termo)
        r = await consultar(req)
        print("status .............", r.status)
        print("tipo_busca .........", r.tipo_busca)
        print("identificador ......", r.identificador_unico)
        if r.mensagem_erro:
            print("erro ...............", r.mensagem_erro)
        if r.dados:
            print("nome ...............", r.dados.nome)
            print("cpf ................", r.dados.cpf)
            print("secoes (chaves) ....", list(r.dados.secoes.keys()))
            print("beneficios .........", [b.tipo for b in r.dados.beneficios])
        if r.evidencia_base64:
            print("evidencia (bytes) ..", len(r.evidencia_base64), "chars base64")
    finally:
        await browser_manager.stop()


if __name__ == "__main__":
    termo = sys.argv[1] if len(sys.argv) > 1 else "MARIA"
    asyncio.run(main(termo))
