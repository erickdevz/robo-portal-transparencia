const form = document.getElementById("form-consulta");
const btnConsultar = document.getElementById("btn-consultar");

const statusEl = document.getElementById("status");
const statusTitulo = document.getElementById("status-titulo");
const statusDetalhe = document.getElementById("status-detalhe");
const statusTecnico = document.getElementById("status-tecnico");
const statusTecnicoTexto = document.getElementById("status-tecnico-texto");

const loadingEl = document.getElementById("loading");
const resultadoEl = document.getElementById("resultado");
const cardDados = document.getElementById("card-dados");
const dadosGrid = document.getElementById("dados-grid");
const dadosHint = document.getElementById("dados-hint");
const cardBeneficios = document.getElementById("card-beneficios");
const beneficiosLista = document.getElementById("beneficios-lista");
const cardDrive = document.getElementById("card-drive");
const driveGrid = document.getElementById("drive-grid");
const cardEvidencia = document.getElementById("card-evidencia");
const evidenciaImg = document.getElementById("evidencia-img");
const jsonRaw = document.getElementById("json-raw");

const MENSAGEM_CONEXAO_FALHOU =
  "Não conseguimos falar com o servidor. Verifique se a API está rodando e tente novamente.";
const MENSAGEM_ERRO_GENERICO =
  "Não foi possível concluir a consulta. Tente novamente em instantes.";

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();

  const termo = document.getElementById("termo").value.trim();
  const tipo = document.getElementById("tipo").value;
  const filtroSocial = document.getElementById("filtro_programa_social").checked;
  const salvarDrive = document.getElementById("salvar_drive").checked;

  if (termo.length < 2) {
    hide(resultadoEl);
    showStatusErro("Digite pelo menos 2 letras ou números para buscar.");
    return;
  }

  setLoading(true);
  hide(statusEl);
  hide(resultadoEl);

  const endpoint = salvarDrive ? "/hiperautomacao/processar" : "/consulta";
  const body = { termo, tipo, filtro_programa_social: filtroSocial };

  try {
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    let data;
    try {
      data = await resp.json();
    } catch {
      showStatusErro(
        "O servidor respondeu de um jeito inesperado.",
        `HTTP ${resp.status} (resposta não era JSON válido)`
      );
      return;
    }

    if (!resp.ok) {
      const detalheTecnico =
        typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
      showStatusErro(
        "Não foi possível processar essa consulta. Verifique os dados informados e tente novamente.",
        detalheTecnico
      );
      return;
    }

    renderResultado(data, salvarDrive);
  } catch (err) {
    showStatusErro(MENSAGEM_CONEXAO_FALHOU, err.message);
  } finally {
    setLoading(false);
  }
});

function setLoading(isLoading) {
  loadingEl.hidden = !isLoading;
  btnConsultar.disabled = isLoading;
  btnConsultar.textContent = isLoading ? "Consultando..." : "Consultar";
}

function hide(el) {
  el.hidden = true;
}

function show(el) {
  el.hidden = false;
}

/** Banner de sucesso: título amigável + código da consulta como subtítulo. */
function showStatusSucesso(salvouCopia, identificador) {
  statusEl.hidden = false;
  statusEl.className = "status status-sucesso";
  statusTitulo.textContent = salvouCopia
    ? "Encontramos os dados e salvamos uma cópia"
    : "Encontramos os dados dessa pessoa";
  statusDetalhe.textContent = `Código da consulta: ${identificador}`;
  show(statusDetalhe);
  hide(statusTecnico);
}

/**
 * Banner de erro: título em linguagem simples (a explicação vinda da API, ou
 * um texto local para falhas de conexão/validação) + detalhe técnico opcional
 * escondido atrás de um "Ver detalhe técnico".
 */
function showStatusErro(titulo, detalheTecnico) {
  statusEl.hidden = false;
  statusEl.className = "status status-erro";
  statusTitulo.textContent = titulo || MENSAGEM_ERRO_GENERICO;
  hide(statusDetalhe);
  if (detalheTecnico && detalheTecnico !== titulo) {
    statusTecnicoTexto.textContent = detalheTecnico;
    show(statusTecnico);
  } else {
    hide(statusTecnico);
  }
}

function renderResultado(data, viaHiperautomacao) {
  jsonRaw.textContent = JSON.stringify(data, null, 2);

  if (data.status !== "sucesso") {
    showStatusErro(data.explicacao || MENSAGEM_ERRO_GENERICO, data.mensagem_erro);
    show(resultadoEl);
    hide(cardDados);
    hide(cardBeneficios);
    hide(cardDrive);
    hide(cardEvidencia);
    return;
  }

  showStatusSucesso(viaHiperautomacao, data.identificador_unico);
  show(resultadoEl);
  show(cardDados);
  dadosGrid.innerHTML = "";

  if (viaHiperautomacao) {
    // Resposta do fluxo da Parte 2 (HiperautomacaoResponse): não traz os
    // dados completos da pessoa, só o resultado do armazenamento.
    show(cardDrive);
    driveGrid.innerHTML = "";
    addDado(driveGrid, "Código da consulta", data.identificador_unico);
    addDado(driveGrid, "Arquivo salvo", data.nome_arquivo_drive);

    const link = document.createElement("a");
    link.href = data.link_drive;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = data.link_drive;
    addDado(driveGrid, "Link", link);

    dadosHint.textContent =
      'Desmarque "Salvar uma cópia automaticamente" para ver os dados completos e o print aqui na tela.';
    show(dadosHint);
    hide(dadosGrid);

    hide(cardBeneficios);
    hide(cardEvidencia);
    return;
  }

  hide(cardDrive);
  show(cardEvidencia);
  hide(dadosHint);
  show(dadosGrid);

  const dados = data.dados || {};
  addDado(dadosGrid, "Nome", dados.nome);
  addDado(dadosGrid, "CPF", dados.cpf);
  addDado(dadosGrid, "NIS", dados.nis);
  addDado(dadosGrid, "Localidade", dados.localidade);

  const beneficios = dados.beneficios || [];
  if (beneficios.length) {
    show(cardBeneficios);
    beneficiosLista.innerHTML = "";
    beneficios.forEach((b) => beneficiosLista.appendChild(renderBeneficio(b)));
  } else {
    hide(cardBeneficios);
  }

  if (data.evidencia_base64) {
    evidenciaImg.src = `data:image/png;base64,${data.evidencia_base64}`;
  }
}

function renderBeneficio(beneficio) {
  const wrapper = document.createElement("div");
  wrapper.className = "beneficio";

  const titulo = document.createElement("h3");
  titulo.textContent = beneficio.tipo;
  wrapper.appendChild(titulo);

  const dl = document.createElement("dl");
  dl.className = "dados-grid";
  Object.entries(beneficio.detalhes || {}).forEach(([rotulo, valor]) => {
    addDado(dl, rotulo, String(valor));
  });
  wrapper.appendChild(dl);

  return wrapper;
}

function addDado(grid, rotulo, valor) {
  if (!valor) return;
  const dt = document.createElement("dt");
  dt.textContent = rotulo;
  const dd = document.createElement("dd");
  if (valor instanceof Node) {
    dd.appendChild(valor);
  } else {
    dd.textContent = valor;
  }
  grid.appendChild(dt);
  grid.appendChild(dd);
}
