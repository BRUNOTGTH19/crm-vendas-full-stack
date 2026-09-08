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
- Testes funcionais: `python smoke_test.py`, `python smoke_test_sales.py` (com TestClient)
  e `python smoke_test_e2e.py` (requiere o servidor em execução).
- Limpieza de dados de teste: `python cleanup_test_data.py`.

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
