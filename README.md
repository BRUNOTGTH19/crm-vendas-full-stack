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

## Gestão de dados (admin)

Usuários com papel **admin** têm acesso à área **Dados (admin)** (`#/admin/dados`),
com três operações protegidas pela dependência `require_admin` (403 para não-admins):

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

Testes: `python -m pytest tests/test_admin.py` (autorização, reset com/sem
confirmação, exportação, importação skip/overwrite e auditoria).


# Deploy (100% gratuito, sem cartão)

## ⚠️ Importante — conta obrigatória

Todos os cadastros devem ser feitos com o e-mail **brunodesousa.ti@gmail.com**
ou com a conta GitHub **BRUNOTGTH19** (que está vinculada a esse e-mail).
**Não usar nenhuma outra conta.**

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