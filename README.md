# crm-vendas-full-stack
CRM de vendas em PWA — backend **FastAPI** + frontend **React**, com fila de cobranzas, dashboard e relatórios.

## Estrutura

```
backend/   API FastAPI (auth JWT, clientes, vendas, dashboard, relatórios, fila de PDF em Redis)
frontend/  PWA React + Vite + TypeScript + Tailwind CSS
```

## Backend

Requisitos: MySQL 8, Redis, Python 3.14 (venv `.venv` na raíz do repo — o `backend/venv` está incompleto).

```bash
# a partir da raíz
.venv\Scripts\activate
cd backend
uvicorn main:app --reload --port 8000
```

- Documentação interativa: <http://127.0.0.1:8000/docs>
- Config em `backend/.env` (MySQL e Redis).
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

Em producción, definir `VITE_API_URL` com a URL do backend (por padrão usa `/api`).
A PWA incluye `manifest.json`, ícono e `sw.js` (cache-first para estáticos, network-first para a API).

## Usuarios

Registrate a partir da tela de login, ou usa o usuário `bruno@crm.com` (admin) já existente na base local.
