import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api.ts";
import { Modal } from "../components/Modal.tsx";
import { fmtDate } from "../lib/format.ts";
import type { Client } from "../types.ts";

/** Ícone do WhatsApp (SVG oficial simplificado). */
export function WhatsappIcon({ className = "h-4.5 w-4.5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" />
    </svg>
  );
}

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
    <div>
      <h1 className="mb-6 text-2xl font-bold text-white">Clientes</h1>

      <form
        onSubmit={onCreate}
        className="mb-4 flex flex-col gap-2 rounded-3xl bg-[#26215C] p-4 shadow-lg shadow-black/30 sm:flex-row"
      >
        <input
          type="text"
          required
          minLength={3}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Nome do novo cliente…"
          className="flex-1 rounded-full border border-white/10 bg-[#1A1A1A] px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
        />
        <input
          type="text"
          value={newWhatsapp}
          onChange={(e) => setNewWhatsapp(e.target.value)}
          placeholder="WhatsApp (opcional): 5586999998888"
          inputMode="tel"
          className="w-full rounded-full border border-white/10 bg-[#1A1A1A] px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40 sm:w-64"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-full bg-[#534AB7] px-4 py-2 text-sm font-medium text-white hover:bg-[#6a60d4] disabled:opacity-50"
        >
          Adicionar
        </button>
      </form>

      <div className="mb-2 flex items-center gap-2">
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
          className="flex-1 rounded-full border border-white/10 bg-[#26215C] px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
        />
        <button
          type="button"
          onClick={() => onSearch(search.trim())}
          disabled={busy}
          className="rounded-full border border-white/10 px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-white/5"
        >
          Buscar
        </button>
        <button
          type="button"
          onClick={onClear}
          className="rounded-full border border-white/10 px-3 py-2 text-sm text-zinc-300 hover:bg-white/5"
        >
          Limpar
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {busy && clients.length === 0 ? (
        <p className="mt-6 text-sm text-zinc-400">Carregando…</p>
      ) : clients.length === 0 ? (
        <p className="mt-6 text-sm text-zinc-400">
          Nenhum cliente{search.trim() ? " que corresponda à busca" : ""}.
        </p>
      ) : (
        <table className="mt-3 w-full overflow-hidden rounded-3xl bg-[#26215C] text-sm shadow-lg shadow-black/30">
          <thead>
            <tr className="text-left text-xs text-zinc-400 uppercase border-b border-white/10">
              <th className="px-4 py-3">Nome</th>
              <th className="px-4 py-3">Normalizado</th>
              <th className="px-4 py-3">Cadastro</th>
              <th className="px-4 py-3 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((c) => (
              <tr key={c.id} className="border-t border-white/5 hover:bg-white/5">
                <td className="px-4 py-2.5 font-medium text-white">
                  <span className="inline-flex items-center gap-2">
                    {c.full_name}
                    {c.whatsapp && (
                      <a
                        href={`https://wa.me/${c.whatsapp}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={`Abrir WhatsApp: ${c.whatsapp}`}
                        aria-label={`Abrir WhatsApp de ${c.full_name}`}
                        className="inline-flex text-emerald-400 hover:text-emerald-300"
                      >
                        <WhatsappIcon />
                      </a>
                    )}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-zinc-400">{c.name_normalized}</td>
                <td className="px-4 py-2.5 text-zinc-400">{fmtDate(c.created_at)}</td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    type="button"
                    onClick={() => onEdit(c)}
                    className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-medium text-[#FAC775] hover:bg-white/5"
                  >
                    Editar
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(c)}
                    className="ml-2 rounded-full border border-red-500/40 px-3 py-1.5 text-xs font-medium text-red-300 hover:bg-red-500/10"
                  >
                    Excluir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && (
        <Modal title="Editar cliente" onClose={() => setEditing(null)}>
          <label className="mb-1 block text-sm font-medium text-zinc-300">Nome</label>
          <input
            type="text"
            required
            minLength={3}
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-[#1A1A1A] px-3 py-2 text-sm text-white focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
          />
          <label className="mb-1 mt-4 block text-sm font-medium text-zinc-300">
            WhatsApp <span className="text-zinc-500">(opcional)</span>
          </label>
          <input
            type="text"
            value={editWhatsapp}
            onChange={(e) => setEditWhatsapp(e.target.value)}
            placeholder="5586999998888"
            inputMode="tel"
            className="w-full rounded-xl border border-white/10 bg-[#1A1A1A] px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-[#534AB7] focus:outline-none focus:ring-2 focus:ring-[#534AB7]/40"
          />
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setEditing(null)}
              className="rounded-full border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={saveEdit}
              disabled={busy}
              className="rounded-full bg-[#534AB7] px-4 py-2 text-sm font-medium text-white hover:bg-[#6a60d4]"
            >
              Salvar
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}