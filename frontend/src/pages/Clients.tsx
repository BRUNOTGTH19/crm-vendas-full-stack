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
    if (!window.confirm(`¿Eliminar al cliente "${c.full_name}"? Se bloqueará si tiene ventas.`)) return;
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
      <h1 className="text-2xl font-bold text-slate-800 mb-6">Clientes</h1>

      <form
        onSubmit={onCreate}
        className="mb-4 flex flex-col sm:flex-row gap-2 rounded-2xl bg-white p-4 shadow-sm border border-slate-200"
      >
        <input
          type="text"
          required
          minLength={3}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Nombre del nuevo cliente…"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          Agregar
        </button>
      </form>

      <div className="flex items-center gap-2 mb-2">
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
          placeholder="Buscar por nombre (sin acentos)…"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200"
        />
        <button
          type="button"
          onClick={() => onSearch(search.trim())}
          disabled={busy}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
        >
          Buscar
        </button>
        <button
          type="button"
          onClick={onClear}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-500 hover:bg-slate-200"
        >
          Limpiar
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {busy && clients.length === 0 ? (
        <p className="mt-6 text-slate-500 text-sm">Cargando…</p>
      ) : clients.length === 0 ? (
        <p className="mt-6 text-slate-500 text-sm">
          No hay clientes{search.trim() ? " que coincidan con la búsqueda" : ""}.
        </p>
      ) : (
        <table className="mt-3 w-full text-sm bg-white rounded-2xl border border-slate-200 shadow-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400 uppercase border-b border-slate-200">
              <th className="px-4 py-3">Nombre</th>
              <th className="px-4 py-3">Normalizado</th>
              <th className="px-4 py-3">Alta</th>
              <th className="px-4 py-3 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((c) => (
              <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2.5 font-medium text-slate-800">{c.full_name}</td>
                <td className="px-4 py-2.5 text-slate-500">{c.name_normalized}</td>
                <td className="px-4 py-2.5 text-slate-500">{fmtDate(c.created_at)}</td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    type="button"
                    onClick={() => onEdit(c)}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-200"
                  >
                    Editar
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(c)}
                    className="ml-2 rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
                  >
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && (
        <Modal title="Editar cliente" onClose={() => setEditing(null)}>
          <label className="block text-sm font-medium text-slate-700 mb-1">Nombre</label>
          <input
            type="text"
            required
            minLength={3}
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-200"
          />
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setEditing(null)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-200"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={saveEdit}
              disabled={busy}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
            >
              Guardar
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}