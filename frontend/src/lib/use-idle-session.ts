/**
 * Hook de timeout de sessão por inatividade.
 *
 * Enquanto `enabled` é `true` (usuário logado), qualquer atividade
 * (movimento do mouse, toque, tecla, rolagem, foco) renova o prazo de
 * `IDLE_TIMEOUT_MS` (2 minutos). Ao estourar, chama `onIdleLogout()` — que
 * limpa o token e devolve o usuário para a tela de login.
 *
 * Detalhe importante: o navegador **congela timers de abas em segundo plano**
 * (Chrome/Safari limitam `setTimeout` a ~1s ou pausam). Por isso, além do
 * `setInterval`, o hook reavalia a sessão em `visibilitychange`/`focus` e ao
 * voltar de uma aba suspensa — sem isso, quem saía do sistema por 30 min
 * voltaria "logado" até o próximo evento.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ACTIVITY_EVENTS,
  createIdleGuard,
  evaluateIdle,
  IDLE_TIMEOUT_MS,
  IDLE_WARNING_MS,
  type IdleState,
} from "../lib/session-idle.ts";

/** De quanto em quanto tempo o prazo é reavaliado (1s = contagem suave). */
const TICK_MS = 1000;

export interface IdleSession {
  /** Estado atual (usado para desenhar o aviso de contagem regressiva). */
  state: IdleState;
  /** Mantém a sessão aberta ao clicar em "Continuar logado". */
  keepAlive: () => void;
}

export function useIdleSession(
  enabled: boolean,
  onIdleLogout: () => void,
  timeoutMs: number = IDLE_TIMEOUT_MS
): IdleSession {
  const [state, setState] = useState<IdleState>(() =>
    evaluateIdle(Date.now(), Date.now(), timeoutMs, IDLE_WARNING_MS)
  );
  // Mantém o callback estável: evita religar os listeners a cada render.
  const onIdleLogoutRef = useRef(onIdleLogout);
  onIdleLogoutRef.current = onIdleLogout;
  // A guarda (e a regra de "aviso aberto ignora atividade") vem de
  // `lib/session-idle.ts`, coberta por testes com `node --test`.
  const guardRef = useRef<ReturnType<typeof createIdleGuard> | null>(null);
  if (guardRef.current === null) {
    guardRef.current = createIdleGuard({
      timeoutMs,
      warningMs: IDLE_WARNING_MS,
      onExpire: () => onIdleLogoutRef.current(),
      onChange: (next) => setState(next),
    });
  }

  const touch = useCallback(() => {
    guardRef.current!.reset();
    setState(guardRef.current!.peek());
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const guard = guardRef.current!;

    // Recomeça o prazo a cada login: uma sessão nova nunca herda a contagem.
    guard.reset();
    setState(guard.peek());

    const check = () => guard.check();
    const onActivity = () => guard.notifyActivity();
    const onVisible = () => {
      if (document.visibilityState === "visible") check();
    };

    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, onActivity, { passive: true });
    }
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("pageshow", check);
    const timer = window.setInterval(check, TICK_MS);

    return () => {
      window.clearInterval(timer);
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, onActivity);
      }
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("pageshow", check);
    };
  }, [enabled, timeoutMs]);

  return { state, keepAlive: touch };
}
