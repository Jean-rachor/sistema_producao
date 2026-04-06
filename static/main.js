const API_URL = '';
const API_KEY = 'senai-cibersistemas-2026-chave-segura';
const HORA_FORMATTER = new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit'
});
const DATA_FORMATTER = new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit'
});

let mensagemTimeoutId = null;
let ordensCache = [];
let filtroStatusAtual = '';
let termoBuscaAtual = '';

function criarHeadersAutenticados(extraHeaders = {}) {
    return {
        ...extraHeaders,
        'X-API-Key': API_KEY
    };
}

function definirTexto(id, valor) {
    const elemento = document.getElementById(id);
    if (elemento) {
        elemento.textContent = String(valor);
    }
}

function normalizarTexto(valor) {
    return String(valor)
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '');
}

function atualizarCarimboDeLeitura() {
    const agora = new Date();
    definirTexto('last-sync', `${HORA_FORMATTER.format(agora)} | ${DATA_FORMATTER.format(agora)}`);
}

function aplicarStatusApi(tipo, texto) {
    const badge = document.getElementById('api-status');
    if (!badge) {
        return;
    }

    badge.className = `status-chip ${tipo}`;
    badge.textContent = texto;
}

function obterClasseStatus(status) {
    if (status === 'Pendente') {
        return 'badge-warning';
    }
    if (status === 'Em andamento') {
        return 'badge-primary';
    }
    return 'badge-success';
}

function escaparHtml(valor) {
    return String(valor)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function atualizarIndicadores(ordens) {
    const total = ordens.length;
    const pendentes = ordens.filter((ordem) => ordem.status === 'Pendente').length;
    const emAndamento = ordens.filter((ordem) => ordem.status === 'Em andamento').length;
    const concluidas = ordens.filter((ordem) => ordem.status === 'Concluida').length;

    definirTexto('metric-total', total);
    definirTexto('metric-pendente', pendentes);
    definirTexto('metric-andamento', emAndamento);
    definirTexto('metric-concluida', concluidas);
    definirTexto('pipeline-count', pendentes + emAndamento);
    atualizarCarimboDeLeitura();
}

function atualizarBotoesFiltro() {
    document.querySelectorAll('.filter-chip').forEach((botao) => {
        const ativo = botao.dataset.filter === filtroStatusAtual;
        botao.classList.toggle('filter-chip-active', ativo);
    });
}

function atualizarEstadoVazio(totalBase, totalVisivel) {
    const titulo = document.getElementById('empty-title');
    const texto = document.getElementById('empty-text');
    const acao = document.getElementById('empty-action');

    if (!titulo || !texto || !acao) {
        return;
    }

    if (totalBase === 0) {
        titulo.textContent = 'Nenhuma ordem cadastrada';
        texto.textContent = 'Assim que uma ordem entrar no sistema, ela aparece aqui com o status operacional.';
        acao.innerHTML = '<i class="fas fa-arrow-left"></i> Criar primeira ordem';
        acao.onclick = () => document.getElementById('produto').focus();
        acao.classList.remove('oculto');
        return;
    }

    if (totalVisivel === 0) {
        titulo.textContent = 'Nenhum resultado encontrado';
        texto.textContent = 'Ajuste a busca ou troque o filtro de status para localizar outras ordens.';
        acao.innerHTML = '<i class="fas fa-filter"></i> Limpar filtros';
        acao.onclick = () => resetarFiltrosMonitoramento();
        acao.classList.remove('oculto');
    }
}

function obterOrdensFiltradas() {
    return ordensCache.filter((ordem) => {
        const atendeStatus = !filtroStatusAtual || ordem.status === filtroStatusAtual;

        if (!atendeStatus) {
            return false;
        }

        if (!termoBuscaAtual) {
            return true;
        }

        const produto = normalizarTexto(ordem.produto);
        const id = String(ordem.id);

        return produto.includes(termoBuscaAtual) || id.includes(termoBuscaAtual);
    });
}

function atualizarResultados(totalVisivel) {
    definirTexto('results-count', totalVisivel);
}

function renderizarTabela(ordens) {
    const corpo = document.getElementById('corpo-tabela');
    const tabela = document.getElementById('tabela-ordens');
    const semDados = document.getElementById('sem-dados');

    corpo.innerHTML = '';

    if (!Array.isArray(ordens) || ordens.length === 0) {
        tabela.classList.add('oculto');
        semDados.classList.remove('oculto');
        atualizarEstadoVazio(ordensCache.length, 0);
        return;
    }

    tabela.classList.remove('oculto');
    semDados.classList.add('oculto');

    ordens.forEach((ordem) => {
        const linha = document.createElement('tr');
        linha.id = `linha-${ordem.id}`;
        linha.innerHTML = `
            <td data-label="ID">
                <span class="order-id">#${ordem.id}</span>
            </td>
            <td data-label="Produto">
                <div class="product-cell">
                    <span class="product-name">${escaparHtml(ordem.produto)}</span>
                    <span class="product-sub">Ordem industrial em monitoramento</span>
                </div>
            </td>
            <td data-label="Quantidade">
                <span class="qty-pill">${ordem.quantidade} un.</span>
            </td>
            <td data-label="Status">
                ${renderizarBadge(ordem.status, ordem.id)}
            </td>
            <td data-label="Acoes">
                <button class="btn-icon" onclick="excluirOrdem(${ordem.id})" title="Excluir ordem ${ordem.id}">
                    <i class="fas fa-trash"></i>
                    Excluir
                </button>
            </td>
        `;
        corpo.appendChild(linha);
    });
}

function aplicarFiltrosERenderizar() {
    const ordensFiltradas = obterOrdensFiltradas();
    atualizarBotoesFiltro();
    atualizarResultados(ordensFiltradas.length);
    renderizarTabela(ordensFiltradas);
}

function resetarFiltrosMonitoramento() {
    filtroStatusAtual = '';
    termoBuscaAtual = '';

    const busca = document.getElementById('busca-ordem');
    if (busca) {
        busca.value = '';
    }

    aplicarFiltrosERenderizar();
}

function definirFiltroStatus(status) {
    filtroStatusAtual = status;
    aplicarFiltrosERenderizar();
}

function filtrarOrdensLocais() {
    const busca = document.getElementById('busca-ordem');
    termoBuscaAtual = normalizarTexto(busca ? busca.value.trim() : '');
    aplicarFiltrosERenderizar();
}

async function verificarStatus() {
    try {
        aplicarStatusApi('status-loading', 'Sincronizando painel...');

        const resposta = await fetch(`${API_URL}/status`);
        const dados = await resposta.json();

        if (resposta.ok) {
            const totalOrdens = dados.total_ordens ?? dados?.banco?.total_ordens ?? 0;
            aplicarStatusApi('status-online', `API online | ${totalOrdens} ordens`);
            atualizarCarimboDeLeitura();
        } else {
            aplicarStatusApi('status-offline', 'Falha ao ler status da API');
        }
    } catch (erro) {
        console.error(erro);
        aplicarStatusApi('status-offline', 'API indisponivel no momento');
    }
}

function renderizarBadge(status, id = null) {
    const classe = obterClasseStatus(status);

    if (id !== null) {
        return `
            <div class="status-shell">
                <select
                    onchange="atualizarStatus(${id}, this.value)"
                    class="status-select ${classe}"
                    aria-label="Atualizar status da ordem ${id}">
                    <option value="Pendente" ${status === 'Pendente' ? 'selected' : ''}>Pendente</option>
                    <option value="Em andamento" ${status === 'Em andamento' ? 'selected' : ''}>Em andamento</option>
                    <option value="Concluida" ${status === 'Concluida' ? 'selected' : ''}>Concluida</option>
                </select>
            </div>
        `;
    }

    return `<span class="status-select ${classe}">${status}</span>`;
}

async function carregarOrdens() {
    try {
        const resposta = await fetch(`${API_URL}/ordens`);
        const ordens = await resposta.json();

        if (!resposta.ok) {
            throw new Error('Falha ao carregar ordens');
        }

        ordensCache = Array.isArray(ordens) ? ordens : [];
        atualizarIndicadores(ordensCache);
        aplicarFiltrosERenderizar();
    } catch (erro) {
        console.error(erro);
        exibirMensagem('Falha ao carregar ordens.', 'erro');
    }
}

async function criarOrdem() {
    const produto = document.getElementById('produto').value.trim();
    const quantidade = document.getElementById('quantidade').value;
    const status = document.getElementById('status-novo').value;

    if (!produto) {
        exibirMensagem('Preencha o nome do produto.', 'erro');
        document.getElementById('produto').focus();
        return;
    }

    if (!quantidade || Number(quantidade) <= 0) {
        exibirMensagem('Informe uma quantidade valida.', 'erro');
        document.getElementById('quantidade').focus();
        return;
    }

    const botao = document.getElementById('btn-cadastrar');
    botao.disabled = true;
    botao.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gravando ordem';

    try {
        const resposta = await fetch(`${API_URL}/ordens`, {
            method: 'POST',
            headers: criarHeadersAutenticados({
                'Content-Type': 'application/json'
            }),
            body: JSON.stringify({
                produto,
                quantidade: Number(quantidade),
                status
            })
        });

        const dados = await resposta.json();

        if (resposta.ok) {
            resetarFiltrosMonitoramento();
            exibirMensagem(`Ordem #${dados.id} cadastrada com sucesso.`, 'sucesso');
            limparFormulario();
            await carregarOrdens();
            await verificarStatus();
        } else {
            exibirMensagem(dados.erro || 'Erro ao cadastrar ordem.', 'erro');
        }
    } catch (erro) {
        console.error(erro);
        exibirMensagem('Erro de conexao com a API.', 'erro');
    } finally {
        botao.disabled = false;
        botao.innerHTML = '<i class="fas fa-plus"></i> Registrar ordem';
    }
}

function limparFormulario() {
    document.getElementById('produto').value = '';
    document.getElementById('quantidade').value = '';
    document.getElementById('status-novo').value = 'Pendente';
}

async function atualizarStatus(id, novoStatus) {
    try {
        const resposta = await fetch(`${API_URL}/ordens/${id}`, {
            method: 'PUT',
            headers: criarHeadersAutenticados({
                'Content-Type': 'application/json'
            }),
            body: JSON.stringify({ status: novoStatus })
        });

        const dados = await resposta.json();

        if (resposta.ok) {
            exibirMensagem(`Ordem #${id} atualizada para ${novoStatus}.`, 'sucesso');
            await carregarOrdens();
            await verificarStatus();
        } else {
            exibirMensagem(dados.erro || 'Erro ao atualizar status.', 'erro');
            await carregarOrdens();
        }
    } catch (erro) {
        console.error(erro);
        exibirMensagem('Erro de conexao.', 'erro');
    }
}

async function excluirOrdem(id) {
    const confirmado = window.confirm(`Tem certeza que deseja excluir a Ordem #${id}? Esta acao e permanente.`);
    if (!confirmado) {
        return;
    }

    try {
        const resposta = await fetch(`${API_URL}/ordens/${id}`, {
            method: 'DELETE',
            headers: criarHeadersAutenticados()
        });

        const dados = await resposta.json();

        if (resposta.ok) {
            exibirMensagem(dados.mensagem, 'sucesso');
            await carregarOrdens();
            await verificarStatus();
        } else {
            exibirMensagem(dados.erro || 'Erro ao excluir ordem.', 'erro');
        }
    } catch (erro) {
        console.error(erro);
        exibirMensagem('Erro de conexao.', 'erro');
    }
}

function exibirMensagem(texto, tipo) {
    const div = document.getElementById('mensagem');
    div.textContent = texto;
    div.className = `mensagem ${tipo}`;
    div.classList.remove('oculto');

    if (mensagemTimeoutId) {
        clearTimeout(mensagemTimeoutId);
    }

    mensagemTimeoutId = setTimeout(() => {
        div.classList.add('oculto');
    }, 4000);
}

window.addEventListener('load', async () => {
    await Promise.all([verificarStatus(), carregarOrdens()]);
});
