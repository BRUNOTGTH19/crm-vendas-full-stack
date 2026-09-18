# Validação de lembretes Web Push

## Estado desta validação

**Resultado: validação automatizada aprovada; entrega em dispositivo real NÃO VALIDADA.**
Nenhuma subscription real foi usada, nenhum push de produção foi disparado e nenhum
registro existente foi alterado durante estes testes. Alterações na branch
`fix/push-scheduler-validation`, ainda sem deploy nesta etapa.

- Backend: `python -m pytest tests -q --tb=short --disable-warnings -p no:cacheprovider`
  — **28 passed**, 8 avisos de depreciação.
- Service worker: `node --test tests/sw.test.mjs` (no frontend) — **7 passed**.
- Frontend: `npm run typecheck` e `npm run build` aprovados; aviso de bundle >500 kB.
- O teste usa SQLite em memória e simula `webpush`. Exercita o job real, datas,
  destinatários, payload, VAPID, erros 404/410/401/403/503 e timeout.
- Testes do worker executam JavaScript em Node com APIs simuladas. NÃO representam
  Android/iOS reais nem provam que o sistema operacional exibiu uma notificação.

## Regra e execução

Job `pending-reminders`, função `check_due_charges`, iniciado no lifespan da API.
Seleciona vendas `pending`, com `due_date` preenchida e menor/igual à data atual
no fuso configurado + `REMINDER_DAYS_BEFORE`. Agrupa por `Sale.user_id` e envia
somente às subscriptions desse responsável. Não envia push ao cliente devedor.

Padrões, preservando a antecedência zero da regra original:

```env
REMINDER_TIMEZONE=UTC
REMINDER_HOUR=8
REMINDER_DAYS_BEFORE=0
```

Executa uma vez ao dia às **08:00 UTC (05:00 em São Paulo)**. Para antecipar um dia
e executar às 08:00 de Brasília, configurar `REMINDER_DAYS_BEFORE=1` e
`REMINDER_TIMEZONE=America/Sao_Paulo`. Reiniciar a API após mudar a configuração.
O cron agora recebe fuso explicitamente; antes dependia do fuso local do servidor.

- Pagas, sem vencimento e além do limite são excluídas.
- Cobranças ainda pendentes podem gerar novo lembrete no dia seguinte.
- Envio manual confirmado pode repetir notificações; não há deduplicação por dia.
- `max_instances=1`, `coalesce=True`, tolerância de atraso de 3600 segundos.
- Lock impede execução cron/manual simultânea **somente no mesmo processo**.
- Operar com **um worker/uma instância do scheduler**, continuamente ativo.
  Cada processo web cria seu próprio scheduler. Réplicas podem duplicar alertas.
- Render suspenso/desligado no horário: job em memória NÃO garante recuperação
  após reinício. Para garantia operacional, é necessário serviço sempre ativo
  ou agendamento externo persistente. `/health` 200 não prova que o cron executou.

## VAPID, payload e falhas

Ativação usa `GET /push/vapid-key`; o sender usa o mesmo `get_vapid_keys`.
Prioridade atual: par em env, par persistido no banco, fallback derivado do JWT.
Produção deve ter um par VAPID estável. Trocar o par exige reinscrição dos aparelhos;
HTTP 200 da chave pública não confirma correspondência com subscriptions antigas.
JWT autentica a API; endpoint + `p256dh` + `auth` identificam a subscription Web Push.
Não há token FCM gerenciado pelo aplicativo.

Payload: título, corpo com contagem/data limite, `url=/#/queue`, ícone PNG existente,
tag e `data.run_id`. O worker usa `event.waitUntil(showNotification(...))` sem
condicionar a existência/visibilidade da janela. Clique navega/foca ou abre o app.
O sistema operacional ainda controla permissão, foco, economia de energia e exibição.

Cada envio tem timeout de 10 segundos e TTL de 3600 segundos. 404/410 removem a
subscription; 401/403/503 e erros de rede são registrados e mantêm a subscription.
Falha de um dispositivo não interrompe os demais. Não há retry imediato automático.

Logs correlacionados, sem endpoint completo, JWT, chaves ou dados do cliente:
`reminder_scheduler_started` (próxima execução), `reminder_started`, `reminder_found`,
`reminder_notify`, `push_targets`, `push_attempt`, `push_accepted` / `push_failed`,
`push_subscription_removed`, `reminder_finished`.
Falhas de consulta/configuração/limpeza têm eventos próprios.
`push_accepted` = provedor aceitou; **não significa entrega física**.
`users_failed` conta exceções por responsável, não todos os dispositivos rejeitados;
consultar `push_finished` para accepted/failed por dispositivo.
No console do worker: `push_displayed` (promise de exibição resolvida) ou
`push_display_failed`, com o mesmo `run_id`. Esses logs não são enviados ao backend.

## Disparo manual (admin)

`POST /admin/reminders/run`, com Bearer JWT de administrador.
Pode ser chamado pelo Swagger `/docs` depois de autenticar; não compartilhar JWT
em tickets, prints, logs ou no repositório.

Prévia sem envio, sem gravação de lembretes Redis (apenas auditoria):

```json
{"user_id": 123, "dry_run": true}
```

Enviar de fato, apenas para o responsável 123:

```json
{"user_id": 123, "dry_run": false, "confirm": true}
```

Use o ID real do usuário de teste no lugar de 123. Sem `user_id`, considera TODOS
os responsáveis; evite isso durante homologação. Corpo vazio faz apenas prévia.
Resposta inclui `run_id`, `date`, `cutoff`, `timezone`, `sales_found`, `users_found`,
`push_accepted`, `users_failed`, `source`, `dry_run`.
401 sem sessão, 403 não-admin, 400 envio sem confirmação, 404 usuário inexistente,
409 execução simultânea no processo e 503 erro do job.
Auditoria registra intenção antes do envio e resultado após conclusão. Falha após
um efeito externo não desfaz push já enviado; não repetir às cegas após timeout.

`POST /push/test` testa apenas os dispositivos do usuário autenticado, não mais
um broadcast. Serve para separar falha de entrega de falha da seleção de vencimentos.
Não substitui o teste do job.

## Roteiro em dispositivo real (pendente, executar com o usuário)

1. Identificar staging/API/PWA e usuário de teste; publicar a branch nesse ambiente.
   Confirmar par VAPID estável e scheduler continuamente ativo. Não usar reset.
2. Android: instalar PWA via Chrome e permitir notificações pelo botão da aplicação.
   iOS/iPadOS 16.4+: adicionar à Tela de Início via Safari, abrir pelo ícone instalado
   e permitir notificações após tocar no botão. Aba comum do Safari não equivale ao PWA.
3. Verificar a ativação (201 e estado ativo), sem registrar endpoint/chaves nos artefatos.
4. Criar uma venda sintética pendente com `due_date=hoje` no fuso configurado,
   vinculada ao usuário do aparelho. **É o vencimento da venda**, não do cadastro do
   cliente. A criação de vendas já possui outro envio imediato no código: não confundir
   essa notificação com a do scheduler. Identificar o evento pelo `run_id` do job.
5. Administrador, em outro dispositivo, executar prévia filtrada por `user_id`;
   conferir `sales_found`, `cutoff` e timezone. Em seguida confirmar envio real.
6. Repetir com app em primeiro plano, em background e fechado normalmente.
   Não confundir fechar janela com forçar parada do Chrome/PWA nas configurações do SO.
   Aguardar até 60 segundos inicialmente; registrar atraso/ausência, sem afirmar falha
   definitiva do provedor só pelo prazo. Confirmar título, corpo, ícone e clique em Cobranças.
7. Validar o **cron**, além do manual: manter a venda elegível e o serviço ativo no
   próximo horário configurado. Capturar `reminder_scheduler_started next_run`, depois
   `reminder_started source=scheduled`, `push_accepted` e confirmação visual correlacionada.
   Alteração temporária de horário só em staging; restaurar ao terminar.
8. Verificar controles negativos: venda paga e venda após cutoff não entram na prévia;
   outro usuário não recebe alerta do responsável testado. Remover apenas dados sintéticos.

Em caso de falha, anexar logs filtrados pelo `run_id` e horário com fuso, versão do SO,
navegador e estado da permissão. Não anexar JWT, subscription endpoint, p256dh, auth,
chave privada VAPID ou dados pessoais. Screenshot da notificação deve omitir dados reais.

| Plataforma | Primeiro plano | Background | Fechado | Cron no horário | Evidência |
|---|---|---|---|---|---|
| Android/Chrome instalado | Não executado | Não executado | Não executado | Não executado | Sem aparelho nesta sessão |
| iOS/Safari PWA instalado | Não executado | Não executado | Não executado | Não executado | Sem aparelho nesta sessão |

Classificar após observação: **funcionou** (todos os cenários e cron), **parcialmente**
(somente alguns), **não funcionou** (falha reproduzida). Por ora: **não validado em
aparelho**, não “funcionou” por causa dos testes simulados.
