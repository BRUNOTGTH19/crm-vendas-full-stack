import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api.ts";
import { Modal } from "../components/Modal.tsx";
import { PageHeader } from "../components/PageHeader.tsx";
import { fmtDate } from "../lib/format.ts";
import type { Client } from "../types.ts";

/** Ícone do WhatsApp (SVG oficial simplificado). */
export function WhatsappIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" />
    </svg>
  );
}

const ERROR_BOX =
  "rounded-2xl border border-rose-700/20 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-300/20 dark:bg-rose-400/15 dark:text-rose-200";

export function Clients() {
  const [clients, setClients] = useState<Client[]>([]);
  const [search, setSearch] = useState("");
  const [newName, setNewName] = useState("");
  const [newWhatsapp, setNewWhatsapp] = useState("");
  const [editing, setEditing] = useState<Client | null>(null);
  const [editName, setEditName] = useState("");
  const [editWhatsapp, setEditWhatsapp] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(query = search.trim()) {
    setBusy(true);
    setError("");
    try {
      const qs = query ? `?search=${encodeURIComponent(query)}` : "";
      setClients(await api.get<Client[]>(`/clients${qs}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/clients", { full_name: newName, whatsapp: newWhatsapp.trim() || null });
      setNewName("");
      setNewWhatsapp("");
      await load(search.trim());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  function startEdit(c: Client) {
    setEditing(c);
    setEditName(c.full_name);
    setEditWhatsapp(c.whatsapp ?? "");
  }

  async function saveEdit() {
    if (!editing) return;
    setBusy(true);
    setError("");
    try {
      await api.put(`/clients/${editing.id}`, { full_name: editName, whatsapp: editWhatsapp.trim() || null });
      setEditing(null);
      await load(search.trim());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(c: Client) {
    if (!window.confirm(`Excluir o cliente "${c.full_name}"? Será bloqueado se tiver vendas.`)) return;
    setBusy(true);
    setError("");
    try {
      await api.del(`/clients/${c.id}`);
      await load(search.trim());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageBody
      busy={busy}
      search={search}
      setSearch={setSearch}
      onSearch={load}
      onClear={() => {
        setSearch("");
        load("");
      }}
      newName={newName}
      setNewName={setNewName}
      newWhatsapp={newWhatsapp}
      setNewWhatsapp={setNewWhatsapp}
      onCreate={create}
      error={error}
      clients={clients}
      onEdit={startEdit}
      onDelete={remove}
      saveEdit={saveEdit}
      editing={editing}
      editName={editName}
      setEditName={setEditName}
      editWhatsapp={editWhatsapp}
      setEditWhatsapp={setEditWhatsapp}
      setEditing={setEditing}
    />
  );
}

function PageBody(props: {
  busy: boolean;
  search: string;
  setSearch: (v: string) => void;
  onSearch: (q: string) => void;
  onClear: () => void;
  newName: string;
  setNewName: (v: string) => void;
  newWhatsapp: string;
  setNewWhatsapp: (v: string) => void;
  onCreate: (e: FormEvent) => void;
  error: string;
  clients: Client[];
  onEdit: (c: Client) => void;
  onDelete: (c: Client) => void;
  saveEdit: () => void;
  editing: Client | null;
  editName: string;
  setEditName: (v: string) => void;
  editWhatsapp: string;
  setEditWhatsapp: (v: string) => void;
  setEditing: (c: Client | null) => void;
}) {
  const {
    busy, search, setSearch, onSearch, onClear, newName, setNewName,
    newWhatsapp, setNewWhatsapp, onCreate, error, clients, onEdit, onDelete, saveEdit,
    editing, editName, setEditName, editWhatsapp, setEditWhatsapp, setEditing,
  } = props;

  return (
    <div className="animate-fade-up space-y-5">
      <PageHeader
        title="Clientes"
        eyebrow="Cadastro"
        subtitle="Cadastre, busque e edite os clientes usados nas vendas e cobranças."
      />

      <form onSubmit={onCreate} className="card card-pad flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          type="text"
          required
          minLength={3}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Nome do novo cliente…"
          className="field flex-1"
        />
        <input
          type="text"
          value={newWhatsapp}
          onChange={(e) => setNewWhatsapp(e.target.value)}
          placeholder="WhatsApp (opcional): 5586999998888"
          inputMode="tel"
          className="field sm:w-64"
        />
        <button type="submit" disabled={busy} className="btn btn-primary sm:px-6">
          Adicionar
        </button>
      </form>

      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onSearch(search.trim());
            }
          }}
          placeholder="Buscar por nome (sem acentos)…"
          className="field min-w-0 flex-1"
        />
        <button
          type="button"
          onClick={() => onSearch(search.trim())}
          disabled={busy}
          className="btn btn-ghost btn-sm"
        >
          Buscar
        </button>
        <button type="button" onClick={onClear} className="btn btn-ghost btn-sm">
          Limpar
        </button>
      </div>

      {error && (
        <div role="alert" className={ERROR_BOX}>
          {error}
        </div>
      )}

      {busy && clients.length === 0 ? (
        <p className="text-sm text-ink/70">Carregando…</p>
      ) : clients.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-sm text-ink/70">
            Nenhum cliente{search.trim() ? " que corresponda à busca" : ""}.
          </p>
        </div>
      ) : (
        // Rolagem horizontal: 4 colunas + botões não cabem em telas estreitas.
        <div className="card hidden overflow-x-auto sm:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ink/[0.06] text-left text-[11px] font-extrabold uppercase tracking-[0.12em] text-ink/70 dark:border-white/10">
                <th className="px-4 py-3">Nome</th>
                <th className="hidden px-4 py-3 xl:table-cell">Normalizado</th>
                <th className="px-4 py-3">Cadastro</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr
                  key={c.id}
                  className="border-t border-ink/[0.06] transition hover:bg-ink/[0.03] dark:border-white/10 dark:hover:bg-white/5"
                >
                  <td className="px-4 py-3 font-bold text-ink">
                    <span className="inline-flex items-center gap-2">
                      {c.full_name}
                      {c.whatsapp && (
                        <a
                          href={`https://wa.me/${c.whatsapp}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={`Abrir WhatsApp: ${c.whatsapp}`}
                          aria-label={`Abrir WhatsApp de ${c.full_name}`}
                          className="relative inline-flex text-brand-600 after:absolute after:-inset-3.5 after:content-[''] hover:text-brand-700 dark:text-brand-300 dark:hover:text-brand-200"
                        >
                          <WhatsappIcon />
                        </a>
                      )}
                    </span>
                  </td>
                  <td className="hidden px-4 py-3 text-ink/70 xl:table-cell">{c.name_normalized}</td>
                  <td className="px-4 py-3 text-ink/70">{fmtDate(c.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <button type="button" onClick={() => onEdit(c)} className="btn btn-ghost btn-sm">
                      Editar
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(c)}
                      className="btn btn-danger btn-sm ml-2"
                    >
                      Excluir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Mobile: cartões — a tabela de 4 colunas + botões não caberia em 360px. */}
      {!busy && clients.length > 0 && (
        <ul className="space-y-2 sm:hidden">
          {clients.map((c) => (
            <li key={c.id} className="card p-4">
              <div className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-sm font-bold text-ink">
                  {c.full_name}
                </span>
                {c.whatsapp && (
                  <a
                    href={`https://wa.me/${c.whatsapp}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={`Abrir WhatsApp: ${c.whatsapp}`}
                    aria-label={`Abrir WhatsApp de ${c.full_name}`}
                    className="relative inline-flex shrink-0 text-brand-600 after:absolute after:-inset-3.5 after:content-[''] hover:text-brand-700 dark:text-brand-300"
                  >
                    <WhatsappIcon />
                  </a>
                )}
              </div>
              <div className="truncate text-xs text-ink/70">{c.name_normalized}</div>
              <div className="text-xs text-ink/70">Cadastro: {fmtDate(c.created_at)}</div>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => onEdit(c)}
                  className="btn btn-ghost btn-sm flex-1"
                >
                  Editar
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(c)}
                  className="btn btn-danger btn-sm flex-1"
                >
                  Excluir
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <Modal title="Editar cliente" onClose={() => setEditing(null)}>
          <label className="label" htmlFor="edit-client-name">
            Nome
          </label>
          <input
            id="edit-client-name"
            type="text"
            required
            minLength={3}
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            className="field"
          />
          <label className="label mt-4" htmlFor="edit-client-whatsapp">
            WhatsApp
          </label>
          <input
            id="edit-client-whatsapp"
            type="text"
            value={editWhatsapp}
            onChange={(e) => setEditWhatsapp(e.target.value)}
            placeholder="5586999998888"
            inputMode="tel"
            className="field"
          />
          <p className="hint mt-1.5">Opcional. Use o formato internacional, só números.</p>
          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={() => setEditing(null)} className="btn btn-ghost">
              Cancelar
            </button>
            <button type="button" onClick={saveEdit} disabled={busy} className="btn btn-primary">
              Salvar
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
