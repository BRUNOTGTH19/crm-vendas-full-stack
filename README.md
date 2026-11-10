# CRM Vendas Full Stack

CRM de vendas em PWA — backend **FastAPI** + frontend **React**, com fila de cobranças, dashboard e relatórios.

## Estrutura

```
backend/   API FastAPI (auth JWT, clientes, vendas, dashboard, relatórios, fila de PDF em Redis)
frontend/  PWA React + Vite + TypeScript + Tailwind CSS
```

## Backend

Requisitos: MySQL 8, Redis, Python 3.12+ (venv `.venv` na raíz do repo — o `backend/venv` está incompleto).

```bash
# a partir da raíz
.venv\Scripts\activate
cd backend
uvicorn main:app --reload --port 8000
```

- Documentação interativa: <http://127.0.0.1:8000/docs>
- Config em `backend/.env` (MySQL e Redis). Veja o modelo em `backend/.env.example`.
- Testes funcionais: `python smoke_test.py`, `python smoke_test_sales.py`,
  `python smoke_test_payments.py`, `python smoke_test_collections.py` (com TestClient)
  e `python smoke_test_e2e.py` (requiere o servidor em execução).
- Limpieza de dados de teste: `python cleanup_test_data.py`.

## Cobrança personalizada no WhatsApp (100% grátis)

Funcionalidade que integra o **alerta de vencimento** (APScheduler) à cobrança:

- `GET /collections/reminders` — vendas **vencidas ou que vencem hoje**, vindas do
  mesmo universo sinalizado pelo `scheduler.check_due_charges` (Redis
  `pending:reminders`).
- `GET /collections/message/{sale_id}` — **mensagem de cobrança personalizada**
  (nome do cliente, valor em aberto, vencimento e situação) + **link `wa.me`**
  já com o texto preenchido.

O envio é feito pelo **deep-link oficial do WhatsApp** (`https://wa.me/<número>?text=...`):
abre o app/WhatsApp Web com a mensagem pronta e o usuário confirma em 1 clique.
Não usa API paga nem automação não-oficial (que arrisca banimento). O **recibo em
PDF** é gerado pela fila existente (`/queue/pdf/{sale_id}`).

Template e nome da empresa são configuráveis no `backend/.env`:

```
COMPANY_NAME="Minha Loja"
COLLECTION_MESSAGE_TEMPLATE="Olá {cliente}! ... {valor} ... {vencimento} ... {situacao} ..."
```

Placeholders: `{cliente}`, `{venda}`, `{valor}`, `{vencimento}`, `{situacao}`, `{empresa}`.

No PWA, a tela **Cobranças** exibe o banner de alerta e o botão **Cobrar** que abre
o modal com a mensagem editável, **Copiar**, **Baixar PDF** e **Abrir WhatsApp**.

## Assistente de IA (opcional)

O botão flutuante **Assistente** aparece em todas as telas logadas (inclusive no
celular) e abre um único chat: a IA conversa com contexto, escolhe uma das
ferramentas fixas de leitura do CRM ou pesquisa na internet e devolve a resposta
em linguagem natural. O histórico recente (até 12 mensagens) é enviado pelo
frontend para manter o fio da conversa.

Endpoint (exige `Authorization: Bearer <JWT>`):

| Endpoint | O quê |
| --- | --- |
| `POST /ai/chat` | Chat com function calling. Corpo: `{"message": "...", "history": [{"role": "user", "content": "..."}]}` (histórico opcional, só `user`/`assistant`, máx. 12). |
| `POST /ai/status-message` | Legado: gera uma frase de status. Sem uso na interface; mantido por compatibilidade. |

Ferramentas disponíveis, todas **somente leitura**:

- CRM: `get_dashboard_overview` (visão geral do escopo), `get_cashflow` (caixa
  por mês), `get_sales_summary`, `list_overdue`, `get_sale_status`,
  `search_clients`, `get_client_details`, `list_sales`, `get_sale_details`
  (itens e pagamentos), `list_payments`, `top_products`, `client_ranking`,
  `global_search` e `get_my_profile`;
- Administração (somente admin): `list_users` e `get_user_summary`;
- Web: `web_search` e `fetch_url` (texto de páginas públicas).

Regras de segurança e escopo:

- o escopo vem de `resolve_data_owner`: usuário comum acessa **apenas** os
  próprios dados; administrador acessa o escopo global por padrão ou um usuário
  específico via `X-View-User`. O `user_id` nunca vem dos argumentos do modelo;
- os schemas das tools usam `extra="forbid"`; enviar `user_id`/`owner_id` é
  rejeitado (exceto o argumento explícito de `get_user_summary`, que só existe
  para admin);
- argumentos são validados com Pydantic (datas ISO, intervalos, IDs positivos);
- no máximo **4 rodadas** de tool calls e **6 tools** por requisição;
- cache Redis por `(escopo, ferramenta, parâmetros)`; a chave separa usuário e
  visão global para nunca reutilizar dados de outro dono;
- HTTP 429 do provedor free tier vira **429** com mensagem amigável; ausência de
  configuração vira **503** genérico (sem revelar variável ou valor);
- prompts, respostas, consultas web e chave **não são registrados em log**;
- CPF/CNPJ, e-mail, telefone e sequências longas de dígitos são redigidos da
  entrada antes do envio; a saída é renderizada como texto (sem HTML);
- a IA não cria, altera ou exclui registros e não gera SQL livre;
- `fetch_url` só aceita `http/https`, bloqueia IPs privados/loopback/metadata e
  revalida cada redirecionamento (proteção SSRF), com limite de tamanho e tempo;
- resultados da web são conteúdo não confiável: o prompt manda ignorar
  instruções vindas deles e citar as URLs usadas.

Configuração no **Render → Environment** (Web Service do backend):

| Variável | Exemplo/observação |
| --- | --- |
| `AI_API_URL` | URL **completa** do endpoint OpenAI-compatível, ex.: `https://api.groq.com/openai/v1/chat/completions` |
| `AI_API_KEY` | chave do provedor (Groq/Gemini). Nunca versionar |
| `AI_MODEL` | modelo disponível no provedor, ex.: `llama-3.1-8b-instant` |
| `TAVILY_API_KEY` | **opcional**; melhora a busca web. Sem ela, usa o fallback gratuito DuckDuckGo HTML |

Para Gemini, use o endpoint OpenAI-compatível
`https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` e um
modelo disponível na sua conta. A chave fica **somente no Render**; a Vercel não
recebe `AI_API_KEY`. Sem essas variáveis o restante do CRM continua funcionando
e o assistente responde 503.

Testes do backend (sem banco de produção e com provedor/Redis simulados):

```bash
python -m pytest tests/test_ai.py
```

Não há migration Alembic: o assistente não cria tabelas nem grava dados.

## Frontend

Requisitos: Node 20+.

```bash
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173  (faz proxy /api -> 127.0.0.1:8000)
npm run build      # build de produção em frontend/dist
```

Em produção, definir `VITE_API_URL` com a URL do backend (por padrão usa `/api`).
Veja o modelo em `frontend/.env.example`.
A PWA incluye `manifest.json`, ícono e `sw.js` (cache-first para estáticos, network-first para a API).

## Usuarios

Registrate a partir da tela de login, ou usa o usuário `bruno@crm.com` (admin) já existente na base local.

### Redefinição de senha com token

O admin gera um token de uso único (15 minutos) em **Administração → Dados e usuários**.
O usuário confirma em `#/reset-password`. Qualquer troca de senha invalida os
access e refresh tokens emitidos antes dela. Veja o fluxo completo, as decisões
de segurança e o passo de migration no Render em
[`docs/password-reset-token.md`](docs/password-reset-token.md).

## Relatórios em PDF (doc 2.5)

Todos os relatórios são gerados sob demanda, em memória (ReportLab), e entregues
como **download** (`Content-Disposition: attachment`, `Cache-Control: no-store`).

| Endpoint | O quê | Parâmetros |
| --- | --- | --- |
| `GET /reports/period` | Todas as vendas do período (pagas e pendentes), com status e totalizadores | `start`, `end` (obrigatórios) |
| `GET /reports/paid` | Somente vendas pagas | `start`, `end` (obrigatórios) |
| `GET /reports/pending` | Todas as vendas em aberto | — |
| `GET /reports/charges` | Cobranças com a situação de cada vencimento | — |
| `GET /reports/cashflow` | Fechamento de caixa do mês | `month` (`AAAA-MM`, opcional) |

Na tela **Relatórios**, o botão **“Gerar e baixar PDF”** do cartão *Vendas por
período* filtra o período **e** baixa o PDF correspondente (`/reports/period`) —
antes ele só atualizava os números na tela e nenhum arquivo era emitido.
Período invertido (`start > end`) responde **400** nas duas rotas.

Testes: `python -m pytest backend/tests/test_reports.py` (emissão, filtros de
período/status, escopo por dono, validação e robustez do gerador).

## Timeout de sessão por inatividade (2 minutos)

Por segurança, a sessão do frontend expira após **2 minutos sem atividade**
(clique, toque, tecla, rolagem, movimento do mouse ou foco na janela):

- aos **30 segundos restantes** aparece um aviso com contagem regressiva e o
  botão **“Continuar logado”** (com o aviso aberto, a atividade passa a ser
  ignorada — só o botão renova a sessão);
- se o prazo estourar, o token é apagado do `localStorage`, o usuário volta
  para a tela de login e precisa informar e-mail e senha novamente;
- a verificação roda a cada 1s e **também** em `visibilitychange`/`pageshow`,
  porque navegadores congelam timers de abas em segundo plano.

O token JWT do backend continua válido por 8h (`ACCESS_TOKEN_EXPIRE_MINUTES`):
a expiração por inatividade é controlada no cliente
(`frontend/src/lib/session-idle.ts` + `lib/use-idle-session.ts`), porque a
autenticação é 100% JWT, sem estado no servidor.

Testes: `npm test` em `frontend/` (`tests/session-idle.test.mjs`).

## Gestão de dados (admin)

Usuários com papel **admin** têm acesso à área **Administração → Dados e usuários**
(`#/admin/dados`), com três operações protegidas pela dependência `require_admin`
(403 para não-admins):

- `POST /admin/database/reset` — zera as tabelas de dados. Exige `{"confirm": true}`.
  **Preserva a tabela `users`** (não desloga o admin). Apaga, respeitando as FKs:
  `sale_items`, `payments`, `push_subscriptions`, `sales`, `clients`.
  Controlado pela flag `ALLOW_DATABASE_RESET` (padrão `true`); se `false`, responde 403.
- `GET /admin/database/export` — baixa um JSON consolidado (`crm_vendas_export.json`)
  com todos os registros das tabelas de dados.
- `POST /admin/database/import?mode=skip|overwrite` — reinsere dados do arquivo
  exportado, validados por Pydantic. `skip` (padrão) ignora IDs existentes;
  `overwrite` atualiza os registros existentes.

Toda ação é registrada na tabela de auditoria `audit_logs` (quem, quando, o quê).

### Como virar admin

O cadastro público cria **sempre** usuário comum (`role="user"`); o campo `role`
do `POST /auth/register` só aceita esse valor (enviar `admin` retorna 422).

Há dois caminhos para liberar a área administrativa:

**1. Código de ativação (mais simples, sem SQL)**

1. cadastre e entre normalmente na sua conta;
2. o backend gera um código aleatório na primeira vez que o app é aberto sem
   existir administrador e o registra **apenas no log do servidor**
   (`admin_setup_code_generated ...`). No Render, veja **Logs**; localmente, o
   terminal do backend;
3. no app, clique em **Ativar acesso admin** (sidebar ou ícone no topo), cole o
   código e confirme. A partir daí a área administrativa é liberada.

O código gerado é **de uso único**: após a ativação ele é apagado e a ativação
por código fica encerrada, então ninguém mais consegue usá-lo. Se preferir
escolher o código, defina `ADMIN_SETUP_CODE` no Render. Nesse caso a variável é
uma **chave mestra**: vale a qualquer momento, inclusive se já existir um
administrador (serve para recuperar o acesso). Trate esse valor como senha —
quem souber a chave consegue ativar o admin. O endpoint é
`POST /auth/activate-admin` `{ "code": "..." }`, autenticado e com rate limit
por IP.

**2. E-mail fixo (`ADMIN_EMAIL`)**

1. cadastre normalmente a conta na tela de login;
2. no **Render → Environment**, defina `ADMIN_EMAIL` com o e-mail dessa conta;
3. faça login novamente (ou recarregue o app, que revalida via `GET /auth/me`).
   A promoção é idempotente e não cria conta nenhuma.

A área aparece na sidebar como **Administração → Dados e usuários** e também na
barra inferior do celular.

Testes: `python -m pytest tests/test_admin.py tests/test_admin_users.py
tests/test_admin_activation.py` (autorização, reset com/sem confirmação,
exportação, importação skip/overwrite, auditoria, rejeição de `role=admin` no
cadastro, bootstrap por `ADMIN_EMAIL`, código gerado/definido, uso único e rate
limit).


# Deploy (100% gratuito, sem cartão)

Stack de hospedagem (todos gratuitos e sem cartão de crédito):

| Serviço | Papel | Cadastro |
| --- | --- | --- |
| Vercel | Frontend (PWA) | GitHub |
| Render | Backend (FastAPI) | GitHub |
| Clever Cloud | MySQL | GitHub |
| Upstash | Redis | GitHub |
| Uptime Robot | Anti-hibernação | E-mail |

## 1. MySQL — Clever Cloud

1. Acesse <https://clever-cloud.com>
2. Cadastre-se com GitHub (sem cartão)
3. Create Application → MySQL
4. Copie as credenciais: host, port, user, password, database
5. Monte a `DATABASE_URL`: `mysql+pymysql://user:password@host:port/dbname`

## 2. Redis — Upstash

1. Acesse <https://upstash.com>
2. Cadastre-se com GitHub (sem cartão)
3. Create Database → Redis → região São Paulo
4. Copie a `REDIS_URL` (começa com `rediss://`)

## 3. Backend — Render

1. Acesse <https://render.com>
2. Cadastre-se com GitHub (sem cartão)
3. New Web Service → conectar repositório `BRUNOTGTH19/crm-vendas-full-stack`
4. Root Directory: `backend`
5. Build Command: `pip install -r requirements.txt`
6. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   (também disponível no `backend/Procfile`)
7. Adicionar variáveis de ambiente:
   - `DATABASE_URL` (do Clever Cloud)
   - `REDIS_URL` (do Upstash)
   - `JWT_SECRET_KEY` (gerar com: `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `ENVIRONMENT=production`
   - **(opcional)** `ADMIN_EMAIL=voce@exemplo.com` — promove essa conta já
     cadastrada a administrador no login/revalidação. O cadastro público nunca
     cria admin.
   - **(opcional)** `ADMIN_SETUP_CODE=segredo-forte` — código digitado em
     **Ativar acesso admin** para virar admin sem depender do e-mail. Se vazio,
     o backend gera um código de uso único e o mostra no log do servidor.
   - **(opcional)** `ALLOW_DATABASE_RESET=true` — habilita o botão "Zerar dados"
     no painel admin. O padrão já é `true`; use `false` para bloquear totalmente.
   - **(opcional)** `CORS_ALLOW_ORIGINS=*` — origens permitidas (separadas por
     vírgula). `*` libera todas; para restringir, informe o domínio do frontend
     (ex.: `https://seu-app.vercel.app`).
   - **Web Push (opcional):** `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` e
     `VAPID_SUBJECT` (ex.: `mailto:admin@crm-vendas.com`). Gere o par com
     `python gen_vapid_keys.py`. **Se não definir, o backend gera e persiste
     as chaves automaticamente no banco na primeira chamada** — funciona sem
     configuração manual, mas definir explicitamente é recomendado para
     controlar a rotação das chaves.
   - **Assistente de IA (opcional):** `AI_API_URL` (URL completa do endpoint
     OpenAI-compatível), `AI_API_KEY` e `AI_MODEL`. Sem elas, o assistente
     responde 503 e o restante do CRM continua normal. A chave fica **apenas
     no Render**, nunca na Vercel.
8. Deploy — aguardar o build finalizar
9. Rodar migrations: no Render Shell executar `alembic upgrade head`
   (cria as tabelas `push_subscriptions` e `app_settings`)

## 4. Frontend — Vercel

1. Acesse <https://vercel.com>
2. Cadastre-se com GitHub (sem cartão)
3. New Project → importar `BRUNOTGTH19/crm-vendas-full-stack`
4. Root Directory: `frontend`
5. Adicionar variável de ambiente:
   - `VITE_API_URL=https://URL-DO-SEU-BACKEND.onrender.com`
6. Deploy

## 5. Anti-hibernação — Uptime Robot

1. Acesse <https://uptimerobot.com>
2. Cadastre-se com e-mail (sem cartão)
3. New Monitor → HTTP(s)
4. URL: `https://URL-DO-SEU-BACKEND.onrender.com/health`
5. Interval: 5 minutes
6. Save
