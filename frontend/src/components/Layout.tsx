import { type ReactNode, useEffect, useState } from "react";
import type { User } from "../types.ts";
import { getPushState, enablePush, disablePush } from "../lib/push.ts";
const NAV = [
  { href: "#/", label: "Painel", icon: "\u{1F4CA}" },
  { href: "#/clients", label: "Clientes", icon: "\u{1F465}" },
  { href: "#/sales", label: "Vendas", icon: "\u{1F9FE}" },
  { href: "#/sales/new", label: "Nova venda", icon: "\u2795" },
  { href: "#/queue", label: "Cobranças", icon: "\u{1F514}" },
  { href: "#/history", label: "Histórico", icon: "\u{1F4C5}" },
  { href: "#/reports", label: "Relatórios", icon: "\u{1F4C8}" },
];

// Bottom bar mobile: itens principais (doc 3.1 — Layout com bottom bar)
const BOTTOM_NAV = NAV.filter((n) => n.href !== "#/history");

// Item extra de administração (gestão de dados), visível só para admins.
const ADMIN_NAV = { href: "#/admin/dados", label: "Dados (admin)", icon: "\u{1F5C4}" };

interface LayoutProps {
  user: User;
  onLogout: () => void;
  children: ReactNode;
}

function PushToggle() {
  const [state, setState] = useState<"unsupported" | "denied" | "subscribed" | "unsubscribed" | "loading">("loading");
  const [feedback, setFeedback] = useState("");

  const refreshState = () => getPushState().then(setState).catch((err: unknown) => {
    setState("unsubscribed");
    setFeedback(err instanceof Error ? err.message : "Não foi possível verificar as notificações.");
  });

  useEffect(() => {
    void refreshState();
  }, []);

  if (state === "unsupported") return null;

  const toggle = async () => {
    setFeedback("");
    try {
      setState("loading");
      if (state === "subscribed") {
        await disablePush();
      } else {
        await enablePush();
      }
    } catch (err) {
      // Mensagem amigável: distingue permissão negada de sessão expirada.
      const message = err instanceof Error ? err.message : String(err);
      setFeedback(message);
      alert(message);
    } finally {
      await refreshState();
    }
  };

  const isSubscribed = state === "subscribed";
  const label =
    state === "denied"
      ? "🔕 Notificações bloqueadas"
      : isSubscribed
        ? "🔔 Notificações Ativas"
        : "🔕 Notificações Desativadas";

  return (
    <div className="flex flex-col items-start gap-1">
      <button
        onClick={toggle}
        disabled={state === "loading" || state === "denied"}
        className="flex items-center gap-2 rounded px-2 py-1 text-xs text-zinc-300 hover:text-white transition-colors disabled:opacity-50"
        title="Ativar/Desativar Notificações"
      >
        <span>{label}</span>
      </button>
      {state === "denied" && (
        <span className="px-2 text-[10px] text-[#FAC775]">
          Permita notificações nas configurações do navegador.
        </span>
      )}
      {feedback && state !== "denied" && (
        <span className="px-2 text-[10px] text-red-300">{feedback}</span>
      )}
    </div>
  );
}

export function Layout({ user, onLogout, children }: LayoutProps) {
  const current = window.location.hash.replace(/^#/, "") || "/";

  const isActive = (href: string) => current.split("?")[0] === href.replace("#", "");

  const navItems = user.role === "admin" ? [...NAV, ADMIN_NAV] : NAV;

  return (
    <div className="min-h-screen bg-[#1A1A1A] text-zinc-100">
      {/* Sidebar desktop */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col bg-[#26215C] lg:flex">
        <div className="border-b border-white/10 px-5 py-5">
          <div className="text-xl font-bold tracking-tight text-white">CRM Vendas</div>
          <div className="mt-1 text-xs text-zinc-400">PWA · vendas e cobranças</div>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-3">
          {navItems.map((n) => (
            <a
              key={n.href}
              href={n.href}
              className={`flex items-center gap-3 rounded-full px-3 py-2.5 text-sm transition-colors ${
                isActive(n.href)
                  ? "bg-[#534AB7] font-semibold text-white"
                  : "text-zinc-300 hover:bg-white/5 hover:text-white"
              }`}
            >
              <span aria-hidden>{n.icon}</span>
              {n.label}
            </a>
          ))}
        </nav>
        <div className="border-t border-white/10 px-5 py-4">
          <PushToggle />
          <div className="mt-2 truncate text-sm font-semibold text-white">{user.name}</div>
          <div className="truncate text-xs text-zinc-400">
            {user.email} · {user.role}
          </div>
          <button
            onClick={onLogout}
            className="mt-3 text-xs font-medium text-[#FAC775] hover:text-amber-300"
          >
            Sair
          </button>
        </div>
      </aside>

      {/* Bottom bar mobile */}
      <nav className="fixed inset-x-0 bottom-0 z-40 flex items-center justify-around overflow-x-auto border-t border-white/10 bg-[#26215C]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
        {BOTTOM_NAV.map((n) => (
          <a
            key={n.href}
            href={n.href}
            className={`flex flex-col items-center gap-0.5 px-2 py-2 text-[10px] ${
              isActive(n.href) ? "font-semibold text-[#FAC775]" : "text-zinc-300"
            }`}
          >
            <span className="text-lg" aria-hidden>
              {n.icon}
            </span>
            {n.label}
          </a>
        ))}
        {/* Sair (logout local) */}
        <button
          type="button"
          onClick={onLogout}
          className="flex flex-col items-center gap-0.5 px-2 py-2 text-[10px] text-zinc-300"
        >
          <span className="text-lg" aria-hidden>
            {"\u{1F6AA}"}
          </span>
          Sair
        </button>
      </nav>

      {/* Top bar mobile for Push Toggle */}
      <div className="lg:hidden flex flex-wrap items-center justify-between gap-2 bg-[#26215C] px-4 py-3 border-b border-white/10">
        <div className="text-lg font-bold text-white">CRM Vendas</div>
        {user.role === "admin" && (
          <a href={ADMIN_NAV.href} className="text-sm text-[#FAC775]">Dados (admin)</a>
        )}
        <PushToggle />
      </div>

      <main className="px-4 pb-24 pt-6 md:px-8 lg:ml-64 lg:pb-8 lg:pt-8">{children}</main>
    </div>
  );
}