import type { ReactNode } from "react";
import type { User } from "../types.ts";

const NAV = [
  { href: "#/", label: "Dashboard", icon: "\u{1F4CA}" },
  { href: "#/clients", label: "Clientes", icon: "\u{1F465}" },
  { href: "#/sales", label: "Ventas", icon: "\u{1F9FE}" },
  { href: "#/sales/new", label: "Nueva venta", icon: "\u2795" },
  { href: "#/reports", label: "Reportes", icon: "\u{1F4C8}" },
];

interface LayoutProps {
  user: User;
  onLogout: () => void;
  children: ReactNode;
}

export function Layout({ user, onLogout, children }: LayoutProps) {
  const current = window.location.hash.replace(/^#/, "") || "/";

  return (
    <div className="min-h-screen flex bg-slate-100">
      <aside className="w-64 bg-slate-900 text-white flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-slate-700/70">
          <div className="text-xl font-bold tracking-tight">CRM Vendas</div>
          <div className="text-xs text-slate-400 mt-1">PWA · ventas y cobranzas</div>
        </div>
        <nav className="flex-1 px-3 py-3 space-y-1">
          {NAV.map((n) => {
            const active = current.split("?")[0] === n.href.replace("#", "");
            return (
              <a
                key={n.href}
                href={n.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  active
                    ? "bg-slate-700 text-white font-medium"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <span aria-hidden>{n.icon}</span>
                {n.label}
              </a>
            );
          })}
        </nav>
        <div className="px-5 py-4 border-t border-slate-700/70">
          <div className="text-sm font-semibold text-white truncate">{user.name}</div>
          <div className="text-xs text-slate-400 truncate">
            {user.email} · {user.role}
          </div>
          <button
            onClick={onLogout}
            className="mt-3 text-xs text-red-300 hover:text-red-200 font-medium"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-6 md:p-8">{children}</main>
    </div>
  );
}