/**
 * Timeout de sessão por inatividade (2 minutos).
 *
 * Objetivo: se o usuário abrir o sistema e simplesmente sair (fecha a aba, sai
 * do navegador, deixa o celular sobre a mesa) **sem clicar em "Sair"**, ao
 * voltar depois de 2 minutos ele precisa entrar novamente com e-mail e senha.
 * O token JWT do backend vive 8 horas, então sozinho ele continuaria válido —
 * por isso a expiração é controlada aqui, no cliente.
 *
 * A lógica fica separada do React (mesmo padrão de `lib/user-label.ts` e
 * `lib/report-export.ts`) para poder ser testada com `node --test`, sem DOM.
 */

/** Tempo de inatividade até encerrar a sessão: 2 minutos (regra pedida). */
export const IDLE_TIMEOUT_MS = 2 * 60 * 1000;

/** Aviso exibido antes de encerrar, para o usuário poder continuar logado. */
export const IDLE_WARNING_MS = 30 * 1000;

/** Eventos que contam como atividade do usuário. */
export const ACTIVITY_EVENTS = [
  "pointerdown",
  "pointermove",
  "keydown",
  "wheel",
  "touchstart",
  "focus",
] as const;

/** Mensagem exibida na tela de login quando a sessão expirou por inatividade. */
export const IDLE_LOGOUT_MESSAGE =
  "Sua sessão foi encerrada por falta de atividade. Faça login novamente.";

export interface IdleState {
  /** Milissegundos restantes antes do encerramento (0 quando expirado). */
  remainingMs: number;
  /** `true` dentro da janela de aviso (permite manter a sessão aberta). */
  warning: boolean;
  /** `true` quando o tempo de inatividade já estourou. */
  expired: boolean;
}

/**
 * Calcula o estado da sessão a partir do último instante de atividade.
 * Função pura: não usa relógio, DOM nem storage — o `now` é injetado.
 */
export function evaluateIdle(
  lastActivityAt: number,
  now: number,
  timeoutMs: number = IDLE_TIMEOUT_MS,
  warningMs: number = IDLE_WARNING_MS
): IdleState {
  const idleFor = Math.max(0, now - lastActivityAt);
  const remainingMs = Math.max(0, timeoutMs - idleFor);
  return {
    remainingMs,
    warning: remainingMs > 0 && remainingMs <= warningMs,
    expired: remainingMs === 0,
  };
}

/** `true` quando a sessão já pode ser encerrada. */
export function isExpired(
  lastActivityAt: number,
  now: number,
  timeoutMs: number = IDLE_TIMEOUT_MS
): boolean {
  return evaluateIdle(lastActivityAt, now, timeoutMs).expired;
}

/** Segundos restantes, arredondados para cima (contagem regressiva do aviso). */
export function secondsLeft(state: IdleState): number {
  return Math.ceil(state.remainingMs / 1000);
}

export interface IdleGuardOptions {
  onExpire: () => void;
  onChange?: (state: IdleState) => void;
  timeoutMs?: number;
  warningMs?: number;
}

export interface IdleGuard {
  /** Registra interação do usuário. Ignora durante o aviso de expiração. */
  notifyActivity: (at?: number) => void;
  /** Reavalia o prazo; dispara `onExpire` uma única vez ao estourar. */
  check: (now?: number) => IdleState;
  /** Estado atual (sem efeitos colaterais). */
  peek: (now?: number) => IdleState;
  /** Zera o histórico: usado ao (re)iniciar a sessão. */
  reset: (at?: number) => void;
}

/**
 * Guarda de inatividade sem DOM nem React — o "cérebro" do timeout de sessão.
 *
 * Fica separado do hook para poder ser testado de ponta a ponta com
 * `node --test` (inclusive a regra "com o aviso aberto, a atividade não
 * renova a sessão"). O `now` é injetado: o teste controla o relógio.
 */
export function createIdleGuard(options: IdleGuardOptions): IdleGuard {
  const timeoutMs = options.timeoutMs ?? IDLE_TIMEOUT_MS;
  const warningMs = options.warningMs ?? IDLE_WARNING_MS;
  let lastActivityAt = 0;
  let expired = false;
  let warning = false;

  const peek = (now: number = Date.now()): IdleState => {
    const state = evaluateIdle(lastActivityAt, now, timeoutMs, warningMs);
    return { ...state, warning: warning && state.warning };
  };

  const guard: IdleGuard = {
    notifyActivity(at = Date.now()) {
      // Durante o aviso só o botão "Continuar logado" renova a sessão —
      // senão mover o mouse reinicia a contagem e o aviso nunca expira.
      if (warning) return;
      lastActivityAt = at;
      options.onChange?.(peek(at));
    },
    check(now = Date.now()) {
      const state = evaluateIdle(lastActivityAt, now, timeoutMs, warningMs);
      warning = state.warning;
      if (state.expired && !expired) {
        // Uma única vez: o logout limpa a sessão e o hook é desabilitado.
        expired = true;
        options.onExpire();
      }
      options.onChange?.(peek(now));
      return peek(now);
    },
    peek,
    reset(at = Date.now()) {
      lastActivityAt = at;
      expired = false;
      warning = false;
    },
  };

  guard.reset();
  return guard;
}
