const API_URL = '';
const SESSION_TOKEN_KEY = 'op_token';
const SESSION_USER_KEY = 'op_user';
const FX_RATES = {
    USD: 0.20,
    EUR: 0.18,
    JPY: 31.20,
    RUB: 18.70,
    GBP: 0.15,
    CNY: 1.43
};

const HORA_FORMATTER = new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit'
});
const DATA_HORA_FORMATTER = new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
});
const MOEDA_BRL = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
});
const MOEDA_FORMATTERS = {
    USD: new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }),
    EUR: new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }),
    JPY: new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY' }),
    RUB: new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' }),
    GBP: new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }),
    CNY: new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' })
};

const state = {
    token: null,
    user: null,
    orders: [],
    logs: [],
    forecasts: [],
    bottlenecks: [],
    statusFilter: '',
    searchTerm: '',
    sortMode: 'recent',
    ordersLoadedOnce: false
};

let mensagemTimeoutId = null;

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function normalizarTexto(value) {
    return String(value || '')
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '');
}

function formatCurrencyBRL(value) {
    return MOEDA_BRL.format(Number(value || 0));
}

function formatCurrencyByCode(code, value) {
    const formatter = MOEDA_FORMATTERS[code];
    if (!formatter) {
        return `${code} ${Number(value || 0).toFixed(2)}`;
    }
    return formatter.format(Number(value || 0));
}

function formatDateTime(value) {
    if (!value) {
        return '-';
    }

    const date = new Date(value.replace(' ', 'T'));
    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return DATA_HORA_FORMATTER.format(date);
}

function preencherLogin(username, password) {
    document.getElementById('login-username').value = username;
    document.getElementById('login-password').value = password;
}

function salvarSessao(token, user) {
    state.token = token;
    state.user = user;
    sessionStorage.setItem(SESSION_TOKEN_KEY, token);
    sessionStorage.setItem(SESSION_USER_KEY, JSON.stringify(user));
}

function limparSessao() {
    state.token = null;
    state.user = null;
    state.orders = [];
    state.logs = [];
    state.forecasts = [];
    state.bottlenecks = [];
    state.ordersLoadedOnce = false;
    sessionStorage.removeItem(SESSION_TOKEN_KEY);
    sessionStorage.removeItem(SESSION_USER_KEY);
}

function exibirMensagem(texto, tipo = 'sucesso') {
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

async function apiRequest(path, options = {}) {
    const {
        method = 'GET',
        body,
        auth = false,
        responseType = 'json'
    } = options;

    const headers = {};
    if (auth && state.token) {
        headers.Authorization = `Bearer ${state.token}`;
    }
    if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${API_URL}${path}`, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined
    });

    if (auth && response.status === 401) {
        logout(false);
        throw new Error('Sessao expirada. Faca login novamente.');
    }

    if (responseType === 'blob') {
        const blob = await response.blob();
        return { response, data: blob };
    }

    let data = null;
    try {
        data = await response.json();
    } catch (error) {
        data = null;
    }

    return { response, data };
}

function mostrarTelaLogin() {
    document.getElementById('auth-screen').classList.remove('oculto');
    document.getElementById('app-root').classList.add('oculto');
}

function mostrarAplicacao() {
    document.getElementById('auth-screen').classList.add('oculto');
    document.getElementById('app-root').classList.remove('oculto');
}

function roleClass(role) {
    if (role === 'admin') return 'role-admin';
    if (role === 'operador') return 'role-operador';
    return 'role-visualizador';
}

function aplicarSessaoNaUI() {
    if (!state.user) {
        return;
    }

    document.getElementById('session-user').textContent = state.user.username;

    const roleBadge = document.getElementById('session-role');
    roleBadge.textContent = state.user.role;
    roleBadge.className = `role-badge ${roleClass(state.user.role)}`;

    const note = document.getElementById('permission-note');
    const form = document.getElementById('form-ordem');
    const controls = form.querySelectorAll('input, select, button');
    const podeCriar = state.user.role === 'admin';

    controls.forEach((control) => {
        if (control.id === 'busca-ordem') {
            return;
        }
        if (control.id === 'btn-cadastrar' || control.matches('.choice-chip') || control.matches('.quantity-btn') || control.matches('#ordem-pai') || control.matches('#produto') || control.matches('#quantidade') || control.matches('#valor-unitario') || control.matches('#data-prevista')) {
            control.disabled = !podeCriar;
        }
    });

    if (podeCriar) {
        note.classList.add('oculto');
        return;
    }

    note.classList.remove('oculto');
    note.textContent = state.user.role === 'operador'
        ? 'Perfil operador pode atualizar status, exportar dados e acompanhar logs, mas nao cria nem exclui ordens.'
        : 'Perfil visualizador acessa somente leitura do painel, sem cadastro, exclusao ou alteracao de status.';
}

function podeAtualizarStatus() {
    return state.user && (state.user.role === 'admin' || state.user.role === 'operador');
}

function podeExcluirOrdem() {
    return state.user && state.user.role === 'admin';
}

async function realizarLogin() {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value.trim();
    const botao = document.getElementById('btn-login');

    if (!username || !password) {
        exibirMensagem('Informe usuario e senha.', 'erro');
        return;
    }

    botao.disabled = true;
    botao.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Entrando';

    try {
        const { response, data } = await apiRequest('/login', {
            method: 'POST',
            body: { username, password }
        });

        if (!response.ok) {
            throw new Error(data?.erro || 'Falha no login.');
        }

        salvarSessao(data.token, data.usuario);
        aplicarSessaoNaUI();
        mostrarAplicacao();
        atualizarResumoFinanceiro();
        await carregarDashboard();
        exibirMensagem(`Sessao iniciada como ${data.usuario.username}.`, 'sucesso');
    } catch (error) {
        exibirMensagem(error.message || 'Falha no login.', 'erro');
    } finally {
        botao.disabled = false;
        botao.innerHTML = '<i class="fas fa-right-to-bracket"></i> Entrar no sistema';
    }
}

async function restaurarSessao() {
    const token = sessionStorage.getItem(SESSION_TOKEN_KEY);
    const userRaw = sessionStorage.getItem(SESSION_USER_KEY);
    if (!token || !userRaw) {
        mostrarTelaLogin();
        atualizarResumoFinanceiro();
        return;
    }

    try {
        state.token = token;
        state.user = JSON.parse(userRaw);
        const { response } = await apiRequest('/me', { auth: true });
        if (!response.ok) {
            throw new Error('Sessao invalida.');
        }

        aplicarSessaoNaUI();
        mostrarAplicacao();
        atualizarResumoFinanceiro();
        await carregarDashboard();
    } catch (error) {
        limparSessao();
        mostrarTelaLogin();
        atualizarResumoFinanceiro();
    }
}

function logout(showMessage = true) {
    limparSessao();
    mostrarTelaLogin();
    document.getElementById('login-form').reset();
    atualizarResumoFinanceiro();
    if (showMessage) {
        exibirMensagem('Sessao encerrada.', 'sucesso');
    }
}

function aplicarStatusApi(tipo, texto) {
    const badge = document.getElementById('api-status');
    badge.className = `status-chip ${tipo}`;
    badge.textContent = texto;
}

function atualizarAvisoChegada(novosIds = [], primeiraLeitura = false) {
    const badge = document.getElementById('arrival-status');
    if (!badge) {
        return;
    }

    if (primeiraLeitura) {
        badge.className = 'arrival-chip arrival-init';
        badge.innerHTML = '<i class="fas fa-bell"></i> Monitorando novas ordens';
        return;
    }

    if (novosIds.length > 0) {
        const label = novosIds.length === 1
            ? `Chegou 1 ordem nova`
            : `Chegaram ${novosIds.length} ordens novas`;
        badge.className = 'arrival-chip arrival-new';
        badge.innerHTML = `<i class="fas fa-circle-check"></i> ${label}`;
        return;
    }

    badge.className = 'arrival-chip arrival-idle';
    badge.innerHTML = '<i class="fas fa-clock"></i> Nenhuma ordem nova';
}

function atualizarUltimaLeitura() {
    const agora = new Date();
    document.getElementById('last-sync').textContent = `${HORA_FORMATTER.format(agora)} | ${agora.toLocaleDateString('pt-BR')}`;
}

function atualizarMetricas(ordens) {
    const total = ordens.length;
    const pendentes = ordens.filter((ordem) => ordem.status === 'Pendente').length;
    const andamento = ordens.filter((ordem) => ordem.status === 'Em andamento').length;
    const concluidas = ordens.filter((ordem) => ordem.status === 'Concluida').length;
    const risco = ordens.filter((ordem) => ordem.prazo_em_risco).length;

    document.getElementById('metric-total').textContent = total;
    document.getElementById('metric-pendente').textContent = pendentes;
    document.getElementById('metric-andamento').textContent = andamento;
    document.getElementById('metric-concluida').textContent = concluidas;
    document.getElementById('pipeline-count').textContent = pendentes + andamento;
    document.getElementById('risk-count').textContent = risco;
    atualizarUltimaLeitura();
}

function preencherSelectPai() {
    const select = document.getElementById('ordem-pai');
    const atual = select.value;
    const options = ['<option value="">Sem dependencia</option>'];

    state.orders.forEach((ordem) => {
        options.push(
            `<option value="${ordem.id}">#${ordem.id} - ${escapeHtml(ordem.produto)} (${ordem.status})</option>`
        );
    });

    select.innerHTML = options.join('');
    if ([...select.options].some((option) => option.value === atual)) {
        select.value = atual;
    }
}

function converterMoedasNoFront(valorTotal) {
    return Object.entries(FX_RATES).map(([moeda, taxa]) => ({
        moeda,
        valor: (Number(valorTotal || 0) * taxa).toFixed(2)
    }));
}

function atualizarResumoFinanceiro() {
    const quantidade = Number(document.getElementById('quantidade')?.value || 0);
    const valorUnitario = Number(document.getElementById('valor-unitario')?.value || 0);
    const total = quantidade * valorUnitario;

    const totalEl = document.getElementById('financial-total-brl');
    if (totalEl) {
        totalEl.textContent = formatCurrencyBRL(total);
    }

    const currencyGrid = document.getElementById('currency-grid');
    if (currencyGrid) {
        currencyGrid.innerHTML = converterMoedasNoFront(total)
            .map((item) => `
                <article class="currency-card">
                    <span>${item.moeda}</span>
                    <strong>${formatCurrencyByCode(item.moeda, item.valor)}</strong>
                </article>
            `)
            .join('');
    }
}

function ajustarQuantidade(delta) {
    const input = document.getElementById('quantidade');
    const valorAtual = Math.max(Number(input.value || 1), 1);
    input.value = Math.max(valorAtual + delta, 1);
    atualizarResumoFinanceiro();
}

function selecionarChip(event) {
    const botao = event.currentTarget;
    const field = botao.dataset.field;
    const value = botao.dataset.value;
    const input = document.getElementById(field);
    if (input.disabled) {
        return;
    }

    input.value = value;
    botao.parentElement.querySelectorAll('.choice-chip').forEach((chip) => {
        chip.classList.remove('choice-chip-active');
    });
    botao.classList.add('choice-chip-active');
}

function deadlineInfo(dataPrevista) {
    if (!dataPrevista) {
        return { texto: 'Sem data', classe: 'table-note' };
    }

    const hoje = new Date();
    hoje.setHours(0, 0, 0, 0);

    const prazo = new Date(`${dataPrevista}T00:00:00`);
    const diff = Math.ceil((prazo - hoje) / (1000 * 60 * 60 * 24));

    if (diff <= 7) {
        return { texto: diff < 0 ? `Atrasada ${Math.abs(diff)} d` : `${diff} d restantes`, classe: 'deadline-badge deadline-red' };
    }
    if (diff <= 14) {
        return { texto: `${diff} d restantes`, classe: 'deadline-badge deadline-yellow' };
    }
    return { texto: `${diff} d restantes`, classe: 'deadline-badge deadline-green' };
}

function prioridadeBadge(prioridade) {
    if (prioridade === 'Alta') {
        return '<span class="priority-badge priority-high">Alta</span>';
    }
    if (prioridade === 'Baixa') {
        return '<span class="priority-badge priority-low">Baixa</span>';
    }
    return '<span class="priority-badge priority-medium">Media</span>';
}

function obterClasseStatus(status) {
    if (status === 'Pendente') return 'badge-warning';
    if (status === 'Em andamento') return 'badge-primary';
    return 'badge-success';
}

function renderizarStatus(ordem) {
    const classe = obterClasseStatus(ordem.status);
    if (!podeAtualizarStatus()) {
        return `<span class="status-select ${classe}">${ordem.status}</span>`;
    }

    const disabled = ordem.bloqueada_por_dependencia && ordem.status === 'Pendente' ? 'disabled' : '';
    return `
        <div class="status-shell">
            <select onchange="atualizarStatus(${ordem.id}, this.value)" class="status-select ${classe}" ${disabled}>
                <option value="Pendente" ${ordem.status === 'Pendente' ? 'selected' : ''}>Pendente</option>
                <option value="Em andamento" ${ordem.status === 'Em andamento' ? 'selected' : ''}>Em andamento</option>
                <option value="Concluida" ${ordem.status === 'Concluida' ? 'selected' : ''}>Concluida</option>
            </select>
        </div>
    `;
}

function renderizarConversoes(ordem) {
    const conversoes = ordem.conversoes_total || converterMoedasNoFront(ordem.valor_total);
    const entries = Array.isArray(conversoes)
        ? conversoes.map((item) => `${item.moeda} ${formatCurrencyByCode(item.moeda, item.valor)}`)
        : Object.entries(conversoes).map(([moeda, valor]) => `${moeda} ${formatCurrencyByCode(moeda, valor)}`);
    return entries.join(' | ');
}

function renderizarAcoes(ordem) {
    if (podeExcluirOrdem()) {
        return `
            <button class="btn-icon" onclick="excluirOrdem(${ordem.id})" title="Excluir ordem ${ordem.id}">
                <i class="fas fa-trash"></i>
                Excluir
            </button>
        `;
    }
    return '<span class="action-placeholder">Sem exclusao</span>';
}

function atualizarEstadoVazio(totalBase, totalVisivel) {
    const titulo = document.getElementById('empty-title');
    const texto = document.getElementById('empty-text');
    const acao = document.getElementById('empty-action');

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
        texto.textContent = 'Ajuste a busca ou troque o filtro para localizar outras ordens.';
        acao.innerHTML = '<i class="fas fa-filter"></i> Limpar filtros';
        acao.onclick = () => resetarFiltrosMonitoramento();
        acao.classList.remove('oculto');
    }
}

function ordensFiltradas() {
    return state.orders.filter((ordem) => {
        const atendeStatus = !state.statusFilter || ordem.status === state.statusFilter;
        if (!atendeStatus) {
            return false;
        }

        if (!state.searchTerm) {
            return true;
        }

        const base = [
            ordem.id,
            ordem.produto,
            ordem.prioridade,
            ordem.status,
            ordem.ordem_pai?.produto || ''
        ].map(normalizarTexto).join(' ');

        return base.includes(state.searchTerm);
    });
}

function atualizarBotoesFiltro() {
    document.querySelectorAll('.filter-chip').forEach((chip) => {
        chip.classList.toggle('filter-chip-active', chip.dataset.filter === state.statusFilter);
    });
}

function renderizarTabelaOrdens() {
    const ordens = ordensFiltradas();
    const corpo = document.getElementById('corpo-tabela');
    const tabela = document.getElementById('tabela-ordens');
    const vazio = document.getElementById('sem-dados');

    document.getElementById('results-count').textContent = ordens.length;
    atualizarBotoesFiltro();

    if (ordens.length === 0) {
        corpo.innerHTML = '';
        tabela.classList.add('oculto');
        vazio.classList.remove('oculto');
        atualizarEstadoVazio(state.orders.length, 0);
        return;
    }

    tabela.classList.remove('oculto');
    vazio.classList.add('oculto');

    corpo.innerHTML = ordens.map((ordem) => {
        const prazo = deadlineInfo(ordem.data_prevista);
        const bloqueio = ordem.bloqueada_por_dependencia
            ? `<span class="dependency-pill">Bloqueada pela #${ordem.ordem_pai?.id}</span>`
            : '';
        const risco = ordem.prazo_em_risco
            ? '<span class="forecast-badge alert">Prazo em risco</span>'
            : '<span class="forecast-badge">Fluxo estavel</span>';

        return `
            <tr id="linha-${ordem.id}">
                <td data-label="ID">
                    <span class="order-id">#${ordem.id}</span>
                </td>
                <td data-label="Produto">
                    <div class="product-cell">
                        <div class="product-topline">
                            <span class="product-name">${escapeHtml(ordem.produto)}</span>
                            ${bloqueio}
                        </div>
                        <span class="product-sub">
                            ${ordem.ordem_pai ? `Pai #${ordem.ordem_pai.id} - ${escapeHtml(ordem.ordem_pai.produto)} (${ordem.ordem_pai.status})` : 'Ordem principal sem dependencia'}
                        </span>
                    </div>
                </td>
                <td data-label="Prioridade">
                    ${prioridadeBadge(ordem.prioridade)}
                </td>
                <td data-label="Quantidade e valor">
                    <div class="value-stack">
                        <div class="value-main">
                            <span class="qty-pill">${ordem.quantidade} un.</span>
                            <span class="value-total">${formatCurrencyBRL(ordem.valor_total)}</span>
                        </div>
                        <span class="mini-conversions">${renderizarConversoes(ordem)}</span>
                    </div>
                </td>
                <td data-label="Prazo">
                    <div class="deadline-stack">
                        <span class="${prazo.classe}">${prazo.texto}</span>
                        <span class="inline-note">${ordem.data_prevista || 'Sem data prevista'}</span>
                    </div>
                </td>
                <td data-label="Tempo previsto">
                    <div class="forecast-stack">
                        <span class="forecast-badge">${escapeHtml(ordem.tempo_previsto_producao_texto || 'Sem historico')}</span>
                        ${risco}
                    </div>
                </td>
                <td data-label="Status">
                    <div class="status-stack">
                        ${renderizarStatus(ordem)}
                    </div>
                </td>
                <td data-label="Acoes">
                    <div class="actions-stack">
                        ${renderizarAcoes(ordem)}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function renderizarLogs() {
    const body = document.getElementById('audit-body');
    if (!state.logs.length) {
        body.innerHTML = '<tr><td colspan="4" class="analytics-empty">Nenhum log disponivel.</td></tr>';
        return;
    }

    body.innerHTML = state.logs.slice(0, 12).map((log) => `
        <tr>
            <td>
                <span class="log-user">${escapeHtml(log.usuario)}</span>
                <span class="log-role">${escapeHtml(log.role || '-')}</span>
            </td>
            <td>${escapeHtml(log.acao)}</td>
            <td>${log.ordem_id ? `#${log.ordem_id}` : '-'}</td>
            <td>${formatDateTime(log.timestamp)}</td>
        </tr>
    `).join('');
}

function renderizarAnalytics() {
    const forecastGlobal = document.getElementById('forecast-global');
    forecastGlobal.textContent = state.forecasts.media_global_horas
        ? `${state.forecasts.media_global_horas} h`
        : 'Sem historico';

    const forecastList = document.getElementById('forecast-list');
    const produtos = state.forecasts.produtos || [];
    forecastList.innerHTML = produtos.length
        ? produtos.slice(0, 5).map((item) => `
            <article class="analytics-item">
                <strong>${escapeHtml(item.produto)}</strong>
                <p>${item.tempo_texto} em media | ${item.amostras} amostras | qtd media ${item.media_quantidade}</p>
            </article>
        `).join('')
        : '<p class="analytics-empty">Ainda nao ha historico suficiente para previsoes por produto.</p>';

    const bottleneckList = document.getElementById('bottleneck-list');
    bottleneckList.innerHTML = state.bottlenecks.length
        ? state.bottlenecks.slice(0, 5).map((item) => `
            <article class="analytics-item">
                <strong>${escapeHtml(item.produto)}</strong>
                <p>${item.ordens_ativas} ativas | ${item.ordens_em_risco} em risco | ${item.ordens_bloqueadas} bloqueadas | score ${item.score_gargalo}</p>
            </article>
        `).join('')
        : '<p class="analytics-empty">Nenhum gargalo relevante detectado no momento.</p>';
}

async function carregarStatus() {
    const { response, data } = await apiRequest('/status');
    if (response.ok) {
        aplicarStatusApi('status-online', `API online | ${data.total_ordens ?? 0} ordens`);
        atualizarUltimaLeitura();
        return;
    }
    aplicarStatusApi('status-offline', 'Falha ao ler status da API');
}

async function carregarOrdens() {
    const endpoint = state.sortMode === 'priority' ? '/ordens/prioridade' : '/ordens';
    const { response, data } = await apiRequest(endpoint);
    if (!response.ok) {
        throw new Error(data?.erro || 'Falha ao carregar ordens.');
    }
    const ordensRecebidas = Array.isArray(data) ? data : [];
    const idsAnteriores = new Set(state.orders.map((ordem) => ordem.id));
    const primeiraLeitura = !state.ordersLoadedOnce;

    state.orders = ordensRecebidas;
    state.ordersLoadedOnce = true;

    const novosIds = primeiraLeitura
        ? []
        : ordensRecebidas
            .map((ordem) => ordem.id)
            .filter((id) => !idsAnteriores.has(id));

    atualizarAvisoChegada(novosIds, primeiraLeitura);
    atualizarMetricas(state.orders);
    preencherSelectPai();
    renderizarTabelaOrdens();
}

async function carregarLogs() {
    const { response, data } = await apiRequest('/logs?limit=20', { auth: true });
    if (!response.ok) {
        throw new Error(data?.erro || 'Falha ao carregar logs.');
    }
    state.logs = Array.isArray(data) ? data : [];
    renderizarLogs();
}

async function carregarAnalytics() {
    const [previsoes, gargalos] = await Promise.all([
        apiRequest('/analytics/previsoes', { auth: true }),
        apiRequest('/analytics/gargalos', { auth: true })
    ]);

    if (!previsoes.response.ok) {
        throw new Error(previsoes.data?.erro || 'Falha ao carregar previsoes.');
    }
    if (!gargalos.response.ok) {
        throw new Error(gargalos.data?.erro || 'Falha ao carregar gargalos.');
    }

    state.forecasts = previsoes.data || { produtos: [] };
    state.bottlenecks = Array.isArray(gargalos.data) ? gargalos.data : [];
    renderizarAnalytics();
}

async function carregarDashboard() {
    try {
        aplicarStatusApi('status-loading', 'Sincronizando painel...');
        await Promise.all([
            carregarStatus(),
            carregarOrdens(),
            carregarLogs(),
            carregarAnalytics()
        ]);
    } catch (error) {
        console.error(error);
        exibirMensagem(error.message || 'Falha ao atualizar painel.', 'erro');
    }
}

function resetarFiltrosMonitoramento() {
    state.statusFilter = '';
    state.searchTerm = '';
    document.getElementById('busca-ordem').value = '';
    renderizarTabelaOrdens();
}

function definirFiltroStatus(status) {
    state.statusFilter = status;
    renderizarTabelaOrdens();
}

function filtrarOrdensLocais() {
    state.searchTerm = normalizarTexto(document.getElementById('busca-ordem').value.trim());
    renderizarTabelaOrdens();
}

async function alternarOrdenacao() {
    state.sortMode = state.sortMode === 'recent' ? 'priority' : 'recent';
    const botao = document.getElementById('sort-priority-btn');
    botao.innerHTML = state.sortMode === 'priority'
        ? '<i class="fas fa-list-check"></i> Ordenacao por prioridade ativa'
        : '<i class="fas fa-arrow-down-wide-short"></i> Ordenar por prioridade';
    await carregarOrdens();
}

function payloadNovaOrdem() {
    const ordemPaiId = document.getElementById('ordem-pai').value;
    return {
        produto: document.getElementById('produto').value.trim(),
        quantidade: Number(document.getElementById('quantidade').value),
        status: document.getElementById('status-novo').value,
        prioridade: document.getElementById('prioridade-nova').value,
        valorUnitario: Number(document.getElementById('valor-unitario').value || 0),
        dataPrevista: document.getElementById('data-prevista').value || null,
        ordemPaiId: ordemPaiId ? Number(ordemPaiId) : null
    };
}

function validarNovaOrdem(payload) {
    if (!payload.produto) {
        return 'Preencha o nome do produto.';
    }
    if (!payload.quantidade || payload.quantidade <= 0) {
        return 'Informe uma quantidade valida.';
    }
    if (payload.valorUnitario < 0) {
        return 'Valor unitario nao pode ser negativo.';
    }
    return null;
}

function resetarFormulario() {
    document.getElementById('produto').value = '';
    document.getElementById('quantidade').value = '1';
    document.getElementById('valor-unitario').value = '0.00';
    document.getElementById('data-prevista').value = '';
    document.getElementById('ordem-pai').value = '';
    document.getElementById('status-novo').value = 'Pendente';
    document.getElementById('prioridade-nova').value = 'Media';

    document.querySelectorAll('#status-choice-group .choice-chip').forEach((chip) => {
        chip.classList.toggle('choice-chip-active', chip.dataset.value === 'Pendente');
    });
    document.querySelectorAll('#priority-choice-group .choice-chip').forEach((chip) => {
        chip.classList.toggle('choice-chip-active', chip.dataset.value === 'Media');
    });

    atualizarResumoFinanceiro();
}

async function criarOrdem() {
    const payload = payloadNovaOrdem();
    const erro = validarNovaOrdem(payload);
    if (erro) {
        exibirMensagem(erro, 'erro');
        return;
    }

    const botao = document.getElementById('btn-cadastrar');
    botao.disabled = true;
    botao.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gravando ordem';

    try {
        const { response, data } = await apiRequest('/ordens', {
            method: 'POST',
            auth: true,
            body: payload
        });

        if (!response.ok) {
            throw new Error(data?.erro || 'Erro ao cadastrar ordem.');
        }

        resetarFormulario();
        resetarFiltrosMonitoramento();
        await carregarDashboard();
        exibirMensagem(`Ordem #${data.id} cadastrada com sucesso.`, 'sucesso');
    } catch (error) {
        exibirMensagem(error.message || 'Erro ao cadastrar ordem.', 'erro');
    } finally {
        botao.disabled = false;
        botao.innerHTML = '<i class="fas fa-plus"></i> Registrar ordem';
    }
}

async function atualizarStatus(id, novoStatus) {
    try {
        const { response, data } = await apiRequest(`/ordens/${id}`, {
            method: 'PUT',
            auth: true,
            body: { status: novoStatus }
        });

        if (!response.ok) {
            throw new Error(data?.erro || 'Erro ao atualizar status.');
        }

        await carregarDashboard();
        exibirMensagem(`Ordem #${id} atualizada para ${novoStatus}.`, 'sucesso');
    } catch (error) {
        exibirMensagem(error.message || 'Erro ao atualizar status.', 'erro');
        await carregarOrdens();
    }
}

async function excluirOrdem(id) {
    if (!window.confirm(`Tem certeza que deseja excluir a Ordem #${id}?`)) {
        return;
    }

    try {
        const { response, data } = await apiRequest(`/ordens/${id}`, {
            method: 'DELETE',
            auth: true
        });

        if (!response.ok) {
            throw new Error(data?.erro || 'Erro ao excluir ordem.');
        }

        await carregarDashboard();
        exibirMensagem(data?.mensagem || 'Ordem removida.', 'sucesso');
    } catch (error) {
        exibirMensagem(error.message || 'Erro ao excluir ordem.', 'erro');
    }
}

async function exportarOrdens(formato) {
    const botaoId = formato === 'pdf' ? 'btn-export-pdf' : 'btn-export-xlsx';
    const botao = document.getElementById(botaoId);
    const textoOriginal = botao.innerHTML;
    botao.disabled = true;
    botao.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Baixando';

    try {
        const { response, data } = await apiRequest(`/ordens/exportar?formato=${formato}`, {
            auth: true,
            responseType: 'blob'
        });

        if (!response.ok) {
            const text = await data.text();
            throw new Error(text || 'Falha na exportacao.');
        }

        const blobUrl = URL.createObjectURL(data);
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = formato === 'pdf' ? 'ordens_producao.pdf' : 'ordens_producao.xlsx';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(blobUrl);
        exibirMensagem(`Exportacao ${formato.toUpperCase()} iniciada.`, 'sucesso');
    } catch (error) {
        exibirMensagem(error.message || 'Falha na exportacao.', 'erro');
    } finally {
        botao.disabled = false;
        botao.innerHTML = textoOriginal;
    }
}

window.addEventListener('load', async () => {
    atualizarResumoFinanceiro();
    await restaurarSessao();
});
