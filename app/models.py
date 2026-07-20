"""
Modelos Pydantic de entrada e saída da API / do robô.

Definem o contrato do JSON gerado e são usados pelo FastAPI para gerar
automaticamente a documentação OpenAPI/Swagger.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class TipoBusca(str, Enum):
    """Como interpretar o termo informado."""

    AUTO = "auto"  # detecta automaticamente CPF/NIS vs. nome
    CPF = "cpf"
    NIS = "nis"
    NOME = "nome"


class ConsultaRequest(BaseModel):
    """Parâmetros de entrada da consulta."""

    termo: str = Field(
        ...,
        min_length=2,
        description="Nome completo, CPF ou NIS a ser consultado.",
        examples=["11111111111", "João da Silva"],
    )
    tipo: TipoBusca = Field(
        default=TipoBusca.AUTO,
        description="Tipo do termo. 'auto' detecta CPF/NIS (só dígitos) ou nome.",
    )
    filtro_programa_social: bool = Field(
        default=False,
        description="Aplica o filtro 'Beneficiário de Programa Social'.",
    )

    @model_validator(mode="after")
    def _normaliza(self) -> "ConsultaRequest":
        self.termo = self.termo.strip()
        return self


class StatusConsulta(str, Enum):
    SUCESSO = "sucesso"
    ERRO = "erro"


class Beneficio(BaseModel):
    """Detalhe de um benefício social encontrado no panorama."""

    tipo: str = Field(..., description="Nome do benefício (ex.: Bolsa Família).")
    detalhes: dict[str, Any] = Field(
        default_factory=dict,
        description="Pares rótulo/valor coletados na tela de detalhe.",
    )


class DadosPessoa(BaseModel):
    """Dados cadastrais e relações coletadas do panorama."""

    nome: str | None = None
    cpf: str | None = None
    nis: str | None = None
    localidade: str | None = None
    # Seções genéricas do panorama (rótulo -> conteúdo), preserva o que o
    # portal exibir mesmo que o layout mude.
    secoes: dict[str, Any] = Field(default_factory=dict)
    beneficios: list[Beneficio] = Field(default_factory=list)


class ConsultaResponse(BaseModel):
    """Envelope de resposta — mesmo formato para sucesso e erro."""

    status: StatusConsulta
    identificador_unico: str = Field(
        ...,
        description="ID único da consulta (usado como nome de arquivo na Parte 2).",
    )
    termo_consultado: str
    tipo_busca: TipoBusca
    data_hora: datetime = Field(..., description="Momento da consulta (ISO 8601).")
    dados: DadosPessoa | None = Field(
        default=None, description="Preenchido apenas em caso de sucesso."
    )
    evidencia_base64: str | None = Field(
        default=None,
        description="Screenshot da tela em Base64 (PNG). Apenas em sucesso.",
    )
    mensagem_erro: str | None = Field(
        default=None,
        description="Mensagem de erro (texto exato dos cenários de teste). Apenas em caso de erro.",
    )
    explicacao: str | None = Field(
        default=None,
        description=(
            "Mesma informação de mensagem_erro, em linguagem simples para "
            "exibição a um usuário leigo. Apenas em caso de erro."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "sucesso",
                    "identificador_unico": "a1b2c3d4",
                    "termo_consultado": "11111111111",
                    "tipo_busca": "cpf",
                    "data_hora": "2026-07-20T10:00:00",
                    "dados": {
                        "nome": "FULANO DE TAL",
                        "cpf": "***.111.111-**",
                        "beneficios": [
                            {"tipo": "Bolsa Família", "detalhes": {"Valor": "R$ 600,00"}}
                        ],
                    },
                    "evidencia_base64": "iVBORw0KGgoAAAANSUhEUg...",
                    "mensagem_erro": None,
                    "explicacao": None,
                }
            ]
        }
    }


class HiperautomacaoResponse(BaseModel):
    """
    Resultado do fluxo da Parte 2: consulta ao robô + armazenamento no Drive
    + registro na planilha centralizada.
    """

    status: StatusConsulta
    identificador_unico: str
    nome_arquivo_drive: str | None = Field(
        default=None, description="Nome do arquivo salvo no Drive (só em sucesso)."
    )
    link_drive: str | None = Field(
        default=None, description="Link direto para o arquivo no Drive (só em sucesso)."
    )
    mensagem_erro: str | None = Field(
        default=None, description="Mensagem técnica de erro (própria ou propagada do robô)."
    )
    explicacao: str | None = Field(
        default=None,
        description="Mesma informação de mensagem_erro, em linguagem simples.",
    )
