# Redefinição de senha por token gerado pelo admin

## Resumo

O administrador gera um token de uso único para um usuário específico. O
usuário confirma a nova senha na tela pública `#/reset-password`. A troca de
senha invalida **todos** os access e refresh tokens emitidos antes dela.

Desde a versão com "Esqueci minha senha", o próprio usuário também pode pedir o
token por e-mail (`POST /auth/forgot-password`), desde que o backend tenha SMTP
configurado. Sem SMTP, vale o fluxo manual: o admin entrega o token pessoalmente.

## Fluxo

1. O admin autenticado abre **Dados (admin) → Usuários** e clica em
   **Gerar token de redefinição**.
2. A API devolve o token em texto **uma única vez**; o banco guarda apenas o
   hash SHA-256. O modal mostra o aviso de 15 minutos e o botão **Copiar token**.
3. O admin repassa o token ao usuário por um canal pessoal.
4. O usuário abre `#/reset-password`, informa o token e a nova senha.
5. A API troca a senha, consome o token e incrementa `users.token_version`.
6. Access e refresh tokens antigos passam a responder **401**. O usuário faz
   login novamente com a senha nova.

Gerar um novo token marca como usados os tokens ainda pendentes do mesmo
usuário. A confirmação também consome qualquer outro token pendente dele.

## Endpoints

| Método e rota | Quem pode usar | Resultado |
| --- | --- | --- |
| `POST /admin/users/{user_id}/reset-token` | admin | `200` com `{ token, expires_at }`; `400` para o próprio admin; `403` para usuário comum; `404` para alvo inexistente |
| `POST /auth/reset-password/confirm` | público | `204` em caso de sucesso; `400` genérico para token inexistente, usado ou expirado; `429` no rate limit |
| `GET /auth/password-reset/config` | público | `200` com `{ self_service: bool }` (só a configuração do servidor) |
| `POST /auth/forgot-password` | público | `202` sempre com a mesma mensagem; `429` no rate limit |

Corpo da confirmação:

```json
{ "token": "<token recebido>", "new_password": "<8 a 72 caracteres>" }
```

Corpo do pedido de recuperação:

```json
{ "email": "<e-mail da conta>" }
```

O token em texto só aparece na resposta da geração. Ele não é gravado em log,
não é persistido e não aparece em nenhuma outra rota.

## Segurança

- Token gerado com `secrets.token_urlsafe(32)` e persistido somente como
  SHA-256 hexadecimal (índice único).
- Validade de 15 minutos, uso único e vínculo ao `user_id`.
- Admin não pode gerar token para si mesmo por esta rota.
- A política de senha é a mesma já usada no cadastro: 8 a 72 caracteres.
- A resposta de falha é sempre `Token inválido ou expirado.`, sem revelar
  usuário, e-mail ou se o token existiu.
- O rate limit por IP é o mesmo do endpoint público antigo (10 chamadas por
  10 minutos, em memória, por processo).
- Logs registram apenas `reset_token_created admin_id=... target_user_id=...`
  e `password_reset_confirmed user_id=...`; token, senha, hash e JWT nunca são
  registrados.
- O endpoint público existente `POST /auth/reset-password` não foi alterado
  funcionalmente. Ele também passa a incrementar `token_version` ao trocar a
  senha.

## Recuperação self-service (SMTP opcional)

`GET /auth/password-reset/config` diz apenas se o servidor tem SMTP; a tela
`#/forgot-password` usa isso para mostrar o formulário ou as instruções com o
administrador.

Com `SMTP_HOST`/`SMTP_FROM` definidos:

1. `POST /auth/forgot-password` valida o rate limit por IP (o mesmo balde do
   reset, 10 chamadas por 10 minutos).
2. Se o e-mail existir, cria o token (hash no banco) e agenda o envio em segundo
   plano — o tempo de resposta não denuncia se a conta existe.
3. O e-mail traz o link `APP_PUBLIC_URL/#/reset-password?token=...` e o token em
   texto, para o caso de o link falhar.
4. Falha de SMTP é registrada como `password_reset_email_failed` **sem** e-mail,
   token ou senha; a requisição continua respondendo `202`.

Garantias: resposta idêntica para e-mail existente ou não; token nunca vai para
log; um pedido novo invalida os tokens pendentes anteriores; sem SMTP nenhum
token é gerado.

## Invalidação de sessões

- `users.token_version` é `INTEGER NOT NULL DEFAULT 0`.
- Access e refresh tokens recebem o claim `tv` com o valor atual.
- `get_current_user` e `refresh_tokens` comparam `tv` com o banco; tokens sem
  `tv` ou com valor divergente são rejeitados com 401.
- Toda troca de senha incrementa `token_version` na mesma transação.
- A chave Redis `session:{user_id}` é removida em modo *best-effort* depois do
  commit. A fonte autoritativa da invalidação é o banco; Redis é complementar.

### Impacto medido

Antes da mudança, `GET /auth/me` executava **1 SELECT** (a consulta do usuário).
Depois da mudança continua executando **1 SELECT**: o `tv` é comparado na mesma
linha já carregada. Não foi adicionado cache nem leitura extra.

Tokens emitidos antes desta mudança não têm `tv` e serão rejeitados. **Todos os
usuários precisarão fazer login novamente uma vez** após o deploy.

## Migration e deploy

Migration: `e7f8a9b0c1d2_add_token_version_and_password_reset_tokens.py`

- Adiciona `users.token_version`.
- Cria `password_reset_tokens` com FK, `expires_at`, `used_at` e índices.
- `down_revision = c4d5e6f7a8b9` (migration de índices que precisa estar
  versionada para a cadeia do Alembic funcionar).

Validação local em SQLite (PowerShell, a partir de `backend`):

```powershell
$env:DATABASE_URL = "sqlite:///C:/caminho/para/teste.db"
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m alembic downgrade -1
..\.venv\Scripts\python.exe -m alembic upgrade head
```

Resultado: upgrade, downgrade e reaplicação aprovados; coluna, tabela e os três
índices aparecem e somem corretamente. Nunca foi usado o MySQL de produção.

No Render, o `backend/Procfile` contém:

```text
web: alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

O painel do Render pode sobrescrever o Start Command do repositório. Conferir em
**Settings → Start Command** se a migration roda antes do uvicorn.

## Frontend

- Painel admin: botão por usuário, modal com token, cópia e aviso de expiração.
- Tela pública `#/reset-password`: token, nova senha e confirmação, com erros
  genéricos.
- O token fica apenas no estado React; **não** é gravado em `localStorage`,
  `sessionStorage` ou cookie.
- Resposta 401 de sessão invalidada limpa a sessão e redireciona para `#/login`.

Validação visual real com Edge headless em **320, 375 e 414 px**: tela pública,
lista de usuários e modal do token sem overflow horizontal. Em 320 px os botões
**Gerar token de redefinição** e **Excluir** quebram linha corretamente. O fluxo
de login admin, geração do token e redirecionamento 401 também foi exercitado.

## Testes

- Backend: `148 passed`.
- Testes focados: `23 passed` (`test_password_reset_token.py`,
  `test_password_reset.py`, `test_auth_middleware.py`).
- Frontend: `41 passed` (`npm test`), `npm run build` aprovado, `npm run typecheck`
  aprovado.
- Migration: upgrade/downgrade/upgrade em SQLite aprovados.
- Cobertura principal: geração pelo admin, 403 para usuário comum, admin não
  gera para si, confirmação válida, token reutilizado/expirado, novo token
  invalida o anterior, escopo por usuário, access/refresh antigos, token sem
  `tv`, rate limit e logs sem segredos.

## Limitações e operação

- Sem SMTP configurado, a recuperação por link fica desativada e a entrega do
  token volta a ser manual (admin → usuário).
- O admin não recupera a própria senha por esta rota; use
  `python manage.py set-password --email ...` no servidor ou outro admin.
- Rate limit em memória não é compartilhado entre múltiplos processos/instâncias.
- A remoção da sessão Redis é best-effort; a invalidação efetiva é o
  `token_version` no banco.
- Se o Render não executar `alembic upgrade head`, a aplicação falhará ao
  consultar `token_version`/`password_reset_tokens`.
