import { type ReactNode, useEffect, useState } from "react";
import type { User } from "../types.ts";
import { getPushState, enablePush, disablePush } from "../lib/push.ts";
import { initialsOf, roleLabel } from "../lib/user-label.ts";
import { ThemeToggle } from "./ThemeToggle.tsx";
import {
  IconBell,
  IconDashboard,
  IconDatabase,
  IconLogout,
  IconPlus,
  IconReceipt,
  IconReports,
  IconUsers,
  IconCalendar,
} from "./icons.tsx";

const NAV = [
  { href: "#/", label: "Painel", Icon: IconDashboard },
  { href: "#/clients", label: "Clientes", Icon: IconUsers },
  { href: "#/sales", label: "Vendas", Icon: IconReceipt },
  { href: "#/sales/new", label: "Nova venda", Icon: IconPlus },
  { href: "#/queue", label: "Cobranças", Icon: IconBell },
  { href: "#/history", label: "Histórico", Icon: IconCalendar },
  { href: "#/reports", label: "Relatórios", Icon: IconReports },
];

// Bottom bar mobile: mantém todas as rotas principais (Histórico fica no menu
// lateral/desktop) para não remover nenhuma funcionalidade existente.
const BOTTOM_NAV = NAV.filter((n) => n.href !== "#/history");

const ADMIN_NAV = { href: "#/admin/dados", label: "Admin", Icon: IconDatabase };

interface LayoutProps {
  user: User;
  onLogout: () => void;
  children: ReactNode;
}

function PushToggle({ compact = false }: { compact?: boolean }) {
  const [state, setState] = useState<"unsupported" | "denied" | "subscribed" | "unsubscribed" | "loading">("loading");
  const [feedback, setFeedback] = useState("");

  const refreshState = () =>
    getPushState().then(setState).catch((err: unknown) => {
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
      ? "Notificações bloqueadas"
      : isSubscribed
        ? "Notificações ativas"
        : "Notificações desativadas";

  return (
    <div className="flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={toggle}
        disabled={state === "loading" || state === "denied"}
        className="inline-flex min-h-11 items-center gap-2 rounded-full px-2.5 py-1.5 text-xs font-bold text-ink/70 transition hover:bg-ink/5 hover:text-ink disabled:opacity-50 dark:hover:bg-white/5"
        title="Ativar/Desativar Notificações"
        aria-label={label}
      >
        <IconBell className="h-4 w-4" />
        <span className={compact ? "hidden sm:inline" : ""}>{label}</span>
      </button>
      {state === "denied" && (
        <span className="px-2.5 text-[11px] font-semibold text-amber-700 dark:text-amber-300">
          Permita notificações nas configurações do navegador.
        </span>
      )}
      {feedback && state !== "denied" && (
        <span className="px-2.5 text-[11px] font-semibold text-rose-600 dark:text-rose-300">{feedback}</span>
      )}
    </div>
  );
}

export function Layout({ user, onLogout, children }: LayoutProps) {
  const current = window.location.hash.replace(/^#/, "") || "/";

  const isActive = (href: string) => current.split("?")[0] === href.replace("#", "");

  const bottomItems = user.role === "admin" ? [...BOTTOM_NAV, ADMIN_NAV] : BOTTOM_NAV;

  return (
    <div className="min-h-screen text-ink">
      {/* Sidebar desktop */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[17.5rem] flex-col border-r border-ink/[0.06] bg-cream/70 backdrop-blur dark:border-white/10 dark:bg-paper/50 lg:flex">
        <a href="#/" className="flex items-center gap-3 px-5 py-6">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-950 text-lime shadow-sm dark:bg-lime dark:text-brand-950">
            <IconReports className="h-6 w-6" />
          </span>
          <div className="min-w-0">
            <div className="text-[17px] font-extrabold tracking-[-0.02em] text-ink">CRM Vendas</div>
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-ink/70">
              Vendas e cobranças
            </div>
          </div>
        </a>

        <nav className="flex-1 space-y-1.5 overflow-y-auto px-3 py-2">
          {NAV.map(({ href, label, Icon }) => {
            const active = isActive(href);
            return (
              <a
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-11 items-center gap-3 rounded-2xl px-3.5 py-3 text-sm font-bold transition ${
                  active
                    ? "bg-brand-950 text-white shadow-card dark:bg-lime dark:text-brand-950"
                    : "text-ink/70 hover:bg-ink/5 hover:text-ink dark:hover:bg-white/5"
                }`}
              >
                <Icon className={`h-5 w-5 shrink-0 ${active ? "text-lime dark:text-brand-950" : "text-ink/70"}`} />
                <span className="truncate">{label}</span>
              </a>
            );
          })}

          {user.role === "admin" && (
            <div className="mt-4 border-t border-ink/[0.06] pt-3 dark:border-white/10">
              <p className="px-3.5 pb-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-ink/70">
                Administração
              </p>
              <a
                href={ADMIN_NAV.href}
                aria-current={isActive(ADMIN_NAV.href) ? "page" : undefined}
                className={`flex min-h-11 items-center gap-3 rounded-2xl px-3.5 py-3 text-sm font-bold transition ${
                  isActive(ADMIN_NAV.href)
                    ? "bg-brand-950 text-white shadow-card dark:bg-lime dark:text-brand-950"
                    : "text-ink/70 hover:bg-ink/5 hover:text-ink dark:hover:bg-white/5"
                }`}
              >
                <IconDatabase
                  className={`h-5 w-5 shrink-0 ${
                    isActive(ADMIN_NAV.href) ? "text-lime dark:text-brand-950" : "text-ink/70"
                  }`}
                />
                <span className="truncate">Dados e usuários</span>
              </a>
            </div>
          )}
        </nav>

        <div className="space-y-3 border-t border-ink/[0.06] px-4 py-4 dark:border-white/10">
          <PushToggle />
          <ThemeToggle variant="full" />

          <div className="flex items-center gap-2 rounded-2xl border border-ink/[0.06] bg-white/60 p-2.5 dark:border-white/10 dark:bg-white/5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-extrabold text-brand-900 dark:bg-brand-900 dark:text-lime">
              {initialsOf(user.name)}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-bold text-ink">{user.name}</div>
              <div className="truncate text-[11px] text-ink/70">{roleLabel(user.role)}</div>
            </div>
            <button
              type="button"
              onClick={onLogout}
              className="icon-btn"
              aria-label="Sair"
              title="Sair"
            >
              <IconLogout className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Header fixo (todas as rotas) */}
      <header className="sticky top-0 z-30 border-b border-ink/[0.05] bg-cream/85 pt-[env(safe-area-inset-top)] backdrop-blur-md dark:border-white/10 lg:ml-[17.5rem]">
        <div className="flex items-center justify-between gap-2 px-4 py-2.5 sm:px-6 lg:px-8">
          <a href="#/" className="flex min-w-0 items-center gap-2.5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-950 text-lime dark:bg-lime dark:text-brand-950">
              <IconReports className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <div className="truncate text-sm font-extrabold tracking-tight text-ink">CRM Vendas</div>
              <div className="hidden text-[10px] font-bold uppercase tracking-[0.16em] text-ink/70 sm:block">
                Vendas e cobranças
              </div>
            </div>
          </a>

          <div className="flex items-center gap-1.5">
            {user.role === "admin" && (
              <a
                href={ADMIN_NAV.href}
                className="icon-btn"
                aria-label="Dados (admin)"
                title="Dados (admin)"
              >
                <IconDatabase className="h-4 w-4" />
              </a>
            )}
            <PushToggle compact />
            <ThemeToggle />
            <div
              className="ml-1 hidden items-center gap-2 sm:flex"
              title={`${user.name} · ${roleLabel(user.role)}`}
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-extrabold text-brand-900 dark:bg-brand-900 dark:text-lime">
                {initialsOf(user.name)}
              </span>
              <div className="hidden md:block">
                <div className="max-w-[10rem] truncate text-sm font-bold text-ink">{user.name}</div>
                <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-ink/70">
                  {roleLabel(user.role)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Bottom bar mobile — todas as rotas principais + sair. */}
      <nav className="safe-bottom fixed inset-x-0 bottom-0 z-40 flex items-stretch border-t border-ink/[0.08] bg-paper/95 backdrop-blur-md dark:border-white/10 lg:hidden">
        {bottomItems.map(({ href, label, Icon }) => {
          const active = isActive(href);
          return (
            <a
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-11 min-w-0 flex-1 flex-col items-center justify-center gap-0.5 px-0.5 py-1.5 text-[9px] font-bold min-[360px]:text-[10px] ${
                active ? "text-brand-950 dark:text-lime" : "text-ink/70"
              }`}
            >
              <span
                className={`flex h-6 w-9 items-center justify-center rounded-full transition ${
                  active ? "bg-lime text-brand-950" : "text-ink/70"
                }`}
              >
                <Icon className="h-4 w-4" />
              </span>
              <span className="w-full truncate text-center leading-tight">{label}</span>
            </a>
          );
        })}
        <button
          type="button"
          onClick={onLogout}
          className="flex min-h-11 min-w-0 flex-1 flex-col items-center justify-center gap-0.5 px-0.5 py-1.5 text-[9px] font-bold text-ink/70 min-[360px]:text-[10px]"
        >
          <span className="flex h-6 w-9 items-center justify-center rounded-full">
            <IconLogout className="h-4 w-4" />
          </span>
          <span className="w-full truncate text-center leading-tight">Sair</span>
        </button>
      </nav>

      <main className="lg:ml-[17.5rem]">
        <div className="mx-auto w-full max-w-6xl px-4 pb-[calc(6.5rem+env(safe-area-inset-bottom))] pt-6 sm:px-6 lg:px-8 lg:pb-16 lg:pt-8">
          {children}
        </div>
      </main>
    </div>
  );
}
