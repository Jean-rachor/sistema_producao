# Como Funciona o Backend (Resumão Bruto)

Aqui tá o resumo direto ao ponto de como o backend do sistema de ordens de produção funciona:

## 1. `app.py` (O Garçom)
É o servidor principal feito em **Flask**. Ele que recebe as requisições do frontend e devolve as respostas.
- **O que faz:** Tem todas as rotas (URLs) da API. Trata o login (gerando token JWT), gerencia as ordens (listar, criar, atualizar status, deletar) e também tem rotas de analytics e exportação de PDF/Excel.
- **Segurança:** Controla quem pode fazer o que. Se um usuário não admin tentar deletar algo importante, ele bloqueia.

## 2. `database.py` (O Construtor)
É o arquivo que cuida exclusivamente da comunicação e estrutura do banco de dados.
- **O que faz:** Abre e fecha a conexão com o banco.
- **Inicialização (`init_db`):** Toda vez que o app inicia, ele confere se as tabelas (ordens, usuários, logs) já existem. Se não existirem, ele cria.
- **Usuários:** Já planta usuários padrão (admin, usuario, visualizador) com senhas criptografadas pra você conseguir logar na primeira vez.

## 3. `ordens.db` (O Cofre / Banco de Dados SQLite)
É um arquivo físico gerado na sua pasta. Ele é o próprio banco de dados (SQLite). Nele ficam salvos os dados reais:
- **`ordens`:** O que deve ser produzido, a quantidade, status, prioridades, etc.
- **`usuarios`:** Logins, níveis de acesso (roles) e senhas criptografadas (pra ninguém ler em texto puro).
- **`log_acao`:** Um histórico que dedura tudo o que acontece (quem criou, quem deletou qual ordem), servindo como auditoria.

**Resumo da obra:** O site chama o `app.py`, que valida as regras e usa o `database.py` pra abrir o `ordens.db` e ler ou gravar a informação. Simples e sem enrolação!
