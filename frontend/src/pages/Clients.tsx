import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api.ts";
import { Modal } from "../components/Modal.tsx";
import { fmtDate } from "../lib/format.ts";
import type { Client } from "../types.ts";

export function Clients() {
  const [clients, setClients] = useState<Client[]>([]);
  const [search, setSearch] = useState("");
  const [newName, setNewName] = useState("");
  const [editing, setEditing] = useState<Client | null>(null);
  const [editName, setEditName] = useState("");
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
      await api.post("/clients", { full_name: newName });
      setNewName("");
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
  }

  async function saveEdit() {
    if (!editing) return;
    setBusy(true);
    setError("");
    try {
      await api.put(`/clients/${editing.id}`, { full_name: editName });
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
      onCreate={create}
      error={error}
      clients={clients}
      onEdit={startEdit}
      onDelete={remove}
      saveEdit={saveEdit}
      editing={editing}
      editName={editName}
      setEditName={setEditName}
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
  onCreate: (e: FormEvent) => void;
  error: string;
  clients: Client[];
  onEdit: (c: Client) => void;
  onDelete: (c: Client) => void;
  saveEdit: () => void;
  editing: Client | null;
  editName: string;
  setEditName: (v: string) => void;
  setEditing: (c: Client | null) => void;
}) {
  const {
    busy, search, setSearch, onSearch, onClear, newName, setNewName,
    onCreate, error, clients, onEdit, onDelete, saveEdit,
    editing, editName, setEditName, setEditing,
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
                <td className="px-4 py-2.5 font-medium text-white">{c.full_name}</td>
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