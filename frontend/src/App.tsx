import { useEffect, useState, type ReactNode } from "react";
import { clearSession, getSessionUser } from "./lib/api.ts";
import { Layout } from "./components/Layout.tsx";
import { Login } from "./pages/Login.tsx";
import { Register } from "./pages/Register.tsx";
import { Dashboard } from "./pages/Dashboard.tsx";
import { Clients } from "./pages/Clients.tsx";
import { Sales } from "./pages/Sales.tsx";
import { NewSale } from "./pages/NewSale.tsx";
import { Reports } from "./pages/Reports.tsx";

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
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
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
    ["/reports", <Reports />],
  ]);

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