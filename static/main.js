const API_URL = ''; // Usando caminho relativo, pois estao no mesmo backend

// ==========================================
// FUNÇÕES DE INFRAESTRUTURA
// ==========================================

async function verificarStatus() {
    try {
        const resposta = await fetch(`${API_URL}/status`);
        const dados = await resposta.json();
        const badge = document.getElementById('api-status');
        if (resposta.ok) {
            badge.textContent = `Online - ${dados.banco.total_ordens} ordens`;
            badge.style.color = 'var(--success)';
            badge.style.background = 'rgba(16, 185, 129, 0.1)';
        } else {
            badge.textContent = 'Erro ao conectar';
            badge.style.color = 'var(--danger)';
            badge.style.background = 'rgba(239, 68, 68, 0.1)';
        }
    } catch (erro) {
        console.error(erro);
    }
}

function renderizarBadge(status, id = null) {
    let classe = '';
    if (status === 'Pendente') classe = 'badge-warning';
    else if (status === 'Em andamento') classe = 'badge-primary';
    else if (status === 'Concluida') classe = 'badge-success';
    
    // Se passarmos o ID, vamos renderizar como um select interativo.
    // O texto Concluida na API nao tem acento, porem no visual pode ter "Concluida".
    if (id) {
        return `
            <select onchange="atualizarStatus(${id}, this.value)" class="status-select ${classe}">
                <option value="Pendente" ${status === 'Pendente' ? 'selected' : ''}>Pendente</option>
                <option value="Em andamento" ${status === 'Em andamento' ? 'selected' : ''}>Em andamento</option>
                <option value="Concluida" ${status === 'Concluida' ? 'selected' : ''}>Concluída</option>
            </select>
        `;
    }
    return '';
}

async function carregarOrdens() {
    try {
        const resposta = await fetch(`${API_URL}/ordens`);
        const ordens = await resposta.json();
        
        const corpo = document.getElementById('corpo-tabela');
        const tabela = document.getElementById('tabela-ordens');
        const semDados = document.getElementById('sem-dados');
        
        corpo.innerHTML = '';
        
        if (ordens.length === 0) {
            tabela.classList.add('oculto');
            semDados.classList.remove('oculto');
        } else {
            tabela.classList.remove('oculto');
            semDados.classList.add('oculto');
            
            ordens.forEach(o => {
                const tr = document.createElement('tr');
                tr.id = `linha-${o.id}`;
                tr.innerHTML = `
                    <td><strong>#${o.id}</strong></td>
                    <td>${o.produto}</td>
                    <td>${o.quantidade}</td>
                    <td>${renderizarBadge(o.status, o.id)}</td>
                    <td>
                        <button class="btn-icon btn-danger" onclick="excluirOrdem(${o.id})" title="Excluir">
                            <i class="fas fa-trash"></i> Excluir
                        </button>
                    </td>
                `;
                corpo.appendChild(tr);
            });
        }
    } catch (erro) {
        console.error(erro);
        exibirMensagem('Falha ao carregar ordens.', 'erro');
    }
}


// ==========================================
// CÓDIGO FORNECIDO (AULA 03)
// ==========================================

async function criarOrdem() {
    // Captura os valores dos campos HTML
    const produto = document.getElementById('produto').value.trim();
    const quantidade = document.getElementById('quantidade').value;
    const status = document.getElementById('status-novo').value;
    // Validacao no front-end (antes de chamar a API)
    if (!produto) {
        exibirMensagem('Preencha o nome do produto.', 'erro');
        document.getElementById('produto').focus();
        return;
    }
    if (!quantidade || Number(quantidade) <= 0) {
        exibirMensagem('Informe uma quantidade valida (numero positivo).', 'erro');
        document.getElementById('quantidade').focus();
        return;
    }
    // Desabilita o botao para evitar duplo clique
    const btn = document.getElementById('btn-cadastrar');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Cadastrando...';
    
    try {
        const resposta = await fetch(`${API_URL}/ordens`, {
            method: 'POST',
            // Content-Type diz ao Flask que o body e JSON
            headers: { 'Content-Type': 'application/json' },
            // JSON.stringify converte objeto JS em string JSON
            body: JSON.stringify({
                produto: produto,
                quantidade: Number(quantidade),
                status: status
            })
        });
        
        const dados = await resposta.json();
        if (resposta.ok) { // resposta.ok = true para status 200-299
            exibirMensagem(`Ordem #${dados.id} cadastrada com sucesso!`, 'sucesso');
            limparFormulario();
            await carregarOrdens(); // Atualiza a tabela
            await verificarStatus(); // Atualiza o contador no cabecalho
        } else {
            // Exibe a mensagem de erro retornada pelo Flask
            exibirMensagem(dados.erro || 'Erro ao cadastrar.', 'erro');
        }
    } catch (erro) {
        exibirMensagem('Erro de conexao com a API.', 'erro');
        console.error(erro);
    } finally {
        // O bloco finally executa SEMPRE, com ou sem erro
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save"></i> Cadastrar Ordem';
    }
}

// Limpa os campos do formulario apos cadastro bem-sucedido
function limparFormulario() {
    document.getElementById('produto').value = '';
    document.getElementById('quantidade').value = '';
    document.getElementById('status-novo').value = 'Pendente';
}

async function atualizarStatus(id, novoStatus) {
    try {
        const resposta = await fetch(`${API_URL}/ordens/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: novoStatus })
        });
        const dados = await resposta.json();
        if (resposta.ok) {
            exibirMensagem(`Status da Ordem #${id} atualizado para '${novoStatus}'.`, 'sucesso');
            // Atualiza apenas o badge na linha, sem recarregar tudo
            const linha = document.getElementById(`linha-${id}`);
            if (linha) {
                const tdStatus = linha.cells[3];
                // renderizarBadge agr aceita id pra funcionar cm os selects tb
                tdStatus.innerHTML = renderizarBadge(novoStatus, id);
            }
            await verificarStatus();
        } else {
            exibirMensagem(dados.erro || 'Erro ao atualizar status.', 'erro');
            // Recarrega a tabela para restaurar o select ao valor correto
            await carregarOrdens();
        }
    } catch (erro) {
        exibirMensagem('Erro de conexao.', 'erro');
        console.error(erro);
    }
}

async function excluirOrdem(id) {
    // Confirmacao do usuario antes de deletar
    const confirmado = window.confirm(`Tem certeza que deseja excluir a Ordem #${id}? Esta acao e permanente.`);
    if (!confirmado) return; // Usuario clicou em Cancelar
    try {
        const resposta = await fetch(`${API_URL}/ordens/${id}`, {
            method: 'DELETE'
            // DELETE nao tem body
        });
        const dados = await resposta.json();
        if (resposta.ok) {
            exibirMensagem(dados.mensagem, 'sucesso');
            // Remove a linha da tabela sem recarregar tudo
            const linha = document.getElementById(`linha-${id}`);
            if (linha) linha.remove();
            
            // Se nao houver mais linhas, exibe 'Nenhuma ordem'
            const corpo = document.getElementById('corpo-tabela');
            if (corpo.children.length === 0) {
                document.getElementById('tabela-ordens').classList.add('oculto');
                document.getElementById('sem-dados').classList.remove('oculto');
            }
            await verificarStatus();
        } else {
            exibirMensagem(dados.erro || 'Erro ao excluir.', 'erro');
        }
    } catch (erro) {
        exibirMensagem('Erro de conexao.', 'erro');
        console.error(erro);
    }
}

function exibirMensagem(texto, tipo) {
    const div = document.getElementById('mensagem');
    div.textContent = texto;
    div.className = `mensagem ${tipo}`; // 'mensagem sucesso' ou 'mensagem erro'
    div.classList.remove('oculto');
    // Esconde automaticamente apos 4 segundos
    setTimeout(() => div.classList.add('oculto'), 4000);
}

// Executa ao carregar a pagina
window.onload = async function() {
    await verificarStatus();
    await carregarOrdens();
};
