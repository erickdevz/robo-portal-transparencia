"""Testes das funções puras de utilidade e das exceções (mensagens exatas)."""
from app.exceptions import SemResultadosError, TempoRespostaError
from app.models import TipoBusca
from app.utils import apenas_digitos, detectar_tipo, termo_de_busca


def test_apenas_digitos():
    assert apenas_digitos("111.111.111-11") == "11111111111"
    assert apenas_digitos("João 123") == "123"


def test_detectar_tipo_auto_cpf():
    assert detectar_tipo("11111111111", TipoBusca.AUTO) == TipoBusca.CPF


def test_detectar_tipo_auto_nome():
    assert detectar_tipo("João da Silva", TipoBusca.AUTO) == TipoBusca.NOME


def test_detectar_tipo_explicito_respeitado():
    assert detectar_tipo("11111111111", TipoBusca.NIS) == TipoBusca.NIS


def test_termo_de_busca_limpa_cpf():
    assert termo_de_busca("111.111.111-11", TipoBusca.CPF) == "11111111111"


def test_termo_de_busca_mantem_nome():
    assert termo_de_busca("  João da Silva ", TipoBusca.NOME) == "João da Silva"


def test_mensagem_erro_timeout():
    assert (
        TempoRespostaError().mensagem
        == "Não foi possível retornar os dados no tempo de resposta solicitado"
    )


def test_mensagem_erro_sem_resultados():
    err = SemResultadosError("Nome Inexistente")
    assert err.mensagem == "Foram encontrados 0 resultados para o termo Nome Inexistente"
