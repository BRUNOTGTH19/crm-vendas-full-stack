import { useEffect, useState, type ReactNode } from "react";
import { clearSession, getSessionUser } from "./lib/api.ts";
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

export function App(): ReactNode {
  const [path, setPath] = useState(currentPath());
  const [user, setUser] = useState(getSessionUser());

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

  const route = path.split("?")[0];

  if (!user) {
    return route === "/register" ? <Register /> : <Login />;
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
    <Layout
      user={user}
      onLogout={() => {
        clearSession();
        setUser(null);
        window.location.hash = "#/login";
      }}
    >
      {page}
    </Layout>
  );
}