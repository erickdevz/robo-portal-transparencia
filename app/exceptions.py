"""
Exceções do robô.

Cada erro carrega duas mensagens:
    - `mensagem`: o texto EXATO exigido pelos cenários de teste do desafio
      (não deve ser alterado — é o que valida a Parte 1).
    - `explicacao`: um texto em linguagem simples, para exibição amigável a
      qualquer usuário leigo (interface web, ou qualquer outro consumidor da
      API que queira mostrar algo mais claro que o texto técnico).
"""
from __future__ import annotations


class ScraperError(Exception):
    """Base para erros de negócio do robô (viram JSON de erro, não HTTP 500)."""

    def __init__(self, mensagem: str, explicacao: str | None = None) -> None:
        self.mensagem = mensagem
        self.explicacao = explicacao or (
            "Não foi possível concluir a consulta. Tente novamente em instantes."
        )
        super().__init__(mensagem)


class TempoRespostaError(ScraperError):
    """
    CPF/NIS inexistente ou panorama que não carrega no tempo esperado.

    Cenário de teste: "Erro (CPF)".
    """

    def __init__(self) -> None:
        super().__init__(
            "Não foi possível retornar os dados no tempo de resposta solicitado",
            explicacao=(
                "Não encontramos ninguém com esse CPF ou NIS no Portal da "
                "Transparência. Verifique se os números foram digitados "
                "corretamente e tente novamente."
            ),
        )


class SemResultadosError(ScraperError):
    """
    Nome sem nenhum resultado equivalente.

    Cenário de teste: "Erro (Nome)".
    """

    def __init__(self, termo: str) -> None:
        super().__init__(
            f"Foram encontrados 0 resultados para o termo {termo}",
            explicacao=(
                "Não encontramos ninguém com esse nome no Portal da "
                "Transparência. Confira se está escrito corretamente (evite "
                "abreviações) ou tente buscar pelo CPF/NIS da pessoa."
            ),
        )
