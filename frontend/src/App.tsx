import { useCallback, useEffect, useState, type ReactNode } from "react";
import { clearSession, getSessionUser } from "./lib/api.ts";
import { useIdleSession } from "./lib/use-idle-session.ts";
import { IDLE_LOGOUT_MESSAGE, secondsLeft } from "./lib/session-idle.ts";
import { Layout } from "./components/Layout.tsx";
import { Login } from "./pages/Login.tsx";
import { Register } from "./pages/Register.tsx";
import { Dashboard } from "./pages/Dashboard.tsx";
import { Clients } from "./pages/Clients.tsx";
import { Sales } from "./pages/Sales.tsx";
import { NewSale } from "./pages/NewSale.tsx";
import { Queue } from "./pages/Queue.tsx";
import { History } from "./pages/History.tsx";
import { Reports } from "./pages/Reports.tsx";
import { AdminData } from "./pages/AdminData.tsx";

function currentPath(): string {
  const raw = window.location.hash.replace(/^#/, "");
  return raw === "" ? "/" : raw;
}

/** Aviso de inatividade: o usuário pode continuar ou deixar a sessão encerrar. */
function IdleWarning({ seconds, onKeepAlive }: { seconds: number; onKeepAlive: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6">
      <div
        role="alertdialog"
        aria-live="assertive"
        aria-labelledby="idle-warning-title"
        className="w-full max-w-sm rounded-3xl bg-[#26215C] p-6 text-center shadow-2xl"
      >
        <h2 id="idle-warning-title" className="text-lg font-bold text-white">
          Sua sessão vai expirar
        </h2>
        <p className="mt-2 text-sm text-zinc-300">
          Por segurança, o sistema fecha após 2 minutos sem atividade. Ela será
          encerrada em <strong className="text-[#FAC775]">{seconds}s</strong>.
        </p>
        <button
          type="button"
          onClick={onKeepAlive}
          className="mt-5 w-full rounded-full bg-[#534AB7] py-2.5 text-sm font-semibold text-white hover:bg-[#6a60d4]"
        >
          Continuar logado
        </button>
      </div>
    </div>
  );
}

export function App(): ReactNode {
  const [path, setPath] = useState(currentPath());
  const [user, setUser] = useState(getSessionUser());
  const [idleNotice, setIdleNotice] = useState("");

  useEffect(() => {
    const onChange = () => {
      setPath(currentPath());
      setUser(getSessionUser());
    };
    // `crm_auth_changed` é disparado em login/logout; `crm_session_revoked`
    // quando a API responde 401 e a sessão é limpa. Sem ouvir esses eventos,
    // a UI continuava "logada" mesmo após o token ser removido do storage,
    // fazendo o registro de push falhar com "Token não informado".
    window.addEventListener("hashchange", onChange);
    window.addEventListener("crm_auth_changed", onChange);
    window.addEventListener("crm_session_revoked", onChange);
    return () => {
      window.removeEventListener("hashchange", onChange);
      window.removeEventListener("crm_auth_changed", onChange);
      window.removeEventListener("crm_session_revoked", onChange);
    };
  }, []);

  /** Encerra a sessão local e avisa o motivo (inatividade vs. logout manual). */
  const endSession = useCallback((message: string) => {
    clearSession();
    setUser(null);
    setIdleNotice(message);
    window.location.hash = "#/login";
  }, []);

  // Timeout de 2 minutos por inatividade: sem clicar em "Sair", o sistema se
  // fecha sozinho e o próximo acesso exige e-mail e senha novamente.
  const { state: idleState, keepAlive } = useIdleSession(
    Boolean(user),
    () => endSession(IDLE_LOGOUT_MESSAGE)
  );

  const route = path.split("?")[0];

  if (!user) {
    return route === "/register" ? <Register /> : <Login notice={idleNotice} />;
  }

  const content = new Map<string, ReactNode>([
    ["/", <Dashboard />],
    ["/clients", <Clients />],
    ["/sales", <Sales />],
    ["/sales/new", <NewSale />],
    ["/queue", <Queue />],
    ["/history", <History />],
    ["/reports", <Reports />],
  ]);

  // Área de gestão de dados: acessível apenas a administradores.
  if (user.role === "admin") {
    content.set("/admin/dados", <AdminData />);
  }

  const page = content.get(route) ?? content.get("/")!;

  return (
    <>
      <Layout
        user={user}
        onLogout={() => {
          setIdleNotice("");
          endSession("");
        }}
      >
        {page}
      </Layout>

      {idleState.warning && (
        <IdleWarning seconds={secondsLeft(idleState)} onKeepAlive={keepAlive} />
      )}
    </>
  );
}