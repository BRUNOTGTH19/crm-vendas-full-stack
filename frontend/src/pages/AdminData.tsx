import { useRef, useState } from "react";
import { Modal } from "../components/Modal.tsx";
import {
  ApiError,
  adminExportDatabase,
  adminImportDatabase,
  adminResetDatabase,
  type AdminImportResult,
  type AdminResetResult,
} from "../lib/api.ts";

/**
 * Área restrita a administradores: zerar, exportar e importar dados.
 * Rota: #/admin/dados (só renderizada quando o usuário tem role "admin").
 */
export function AdminData() {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [resetResult, setResetResult] = useState<AdminResetResult | null>(null);
  const [importResult, setImportResult] = useState<AdminImportResult | null>(null);
  const [importMode, setImportMode] = useState<"skip" | "overwrite">("skip");
  const fileRef = useRef<HTMLInputElement>(null);

  async function doReset() {
    setBusy(true);
    setError("");
    setOk("");
    try {
      const res = await adminResetDatabase();
      setResetResult(res);
      setOk("Dados zerados com sucesso.");
      setConfirmOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function doExport() {
    setBusy(true);
    setError("");
    setOk("");
    try {
      await adminExportDatabase();
      setOk("Exportação baixada (crm_vendas_export.json).");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function doImport() {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Selecione um arquivo JSON exportado.");
      return;
    }
    setBusy(true);
    setError("");
    setOk("");
    try {
      const res = await adminImportDatabase(file, importMode);
      setImportResult(res);
      setOk("Importação concluída.");
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-white">Gestão de dados</h1>
      <p className="mb-6 text-sm text-zinc-400">
        Área restrita a administradores. O reset apaga as tabelas de dados
        (clientes, vendas, itens, pagamentos e inscrições de push) e{" "}
        <span className="font-semibold text-[#FAC775]">preserva os usuários</span>.
      </p>

      {error && (
        <div className="mb-4 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
      {ok && (
        <div className="mb-4 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          {ok}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {/* Reset */}
        <section className="rounded-3xl bg-[#26215C] p-5 shadow-lg shadow-black/30">
          <h2 className="text-lg font-semibold text-white">Zerar dados</h2>
          <p className="mt-1 text-xs text-zinc-400">
            Apaga todos os registros de dados do ambiente de teste. Ação
            irreversível — exporte antes se quiser guardar.
          </p>
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            disabled={busy}
            className="mt-4 w-full rounded-full bg-red-500/90 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50"
          >
            Zerar dados
          </button>
        </section>

        {/* Export */}
        <section className="rounded-3xl bg-[#26215C] p-5 shadow-lg shadow-black/30">
          <h2 className="text-lg font-semibold text-white">Exportar</h2>
          <p className="mt-1 text-xs text-zinc-400">
            Baixa um arquivo JSON com todos os registros das tabelas de dados.
          </p>
          <button
            type="button"
            onClick={doExport}
            disabled={busy}
            className="mt-4 w-full rounded-full bg-[#534AB7] px-4 py-2 text-sm font-semibold text-white hover:bg-[#6a60d4] disabled:opacity-50"
          >
            Exportar dados
          </button>
        </section>

        {/* Import */}
        <section className="rounded-3xl bg-[#26215C] p-5 shadow-lg shadow-black/30">
          <h2 className="text-lg font-semibold text-white">Importar</h2>
          <p className="mt-1 text-xs text-zinc-400">
            Reinsere os dados de um arquivo exportado anteriormente.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="mt-3 w-full rounded-xl border border-white/10 bg-[#1A1A1A] px-3 py-2 text-xs text-zinc-300 file:mr-3 file:rounded-full file:border-0 file:bg-[#534AB7] file:px-3 file:py-1.5 file:text-xs file:text-white"
          />
          <label className="mt-3 flex items-center gap-2 text-xs text-zinc-300">
            <span>Conflitos de ID:</span>
            <select
              value={importMode}
              onChange={(e) => setImportMode(e.target.value as "skip" | "overwrite")}
              className="rounded-lg border border-white/10 bg-[#1A1A1A] px-2 py-1 text-xs text-white focus:border-[#534AB7] focus:outline-none"
            >
              <option value="skip">Pular existentes (skip)</option>
              <option value="overwrite">Sobrescrever (overwrite)</option>
            </select>
          </label>
          <button
            type="button"
            onClick={doImport}
            disabled={busy}
            className="mt-3 w-full rounded-full bg-emerald-500/90 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            Importar dados
          </button>
        </section>
      </div>

      {resetResult && (
        <div className="mt-6 rounded-2xl border border-white/10 bg-[#26215C] p-4 text-sm">
          <div className="mb-1 font-semibold text-white">Último reset</div>
          <ul className="space-y-0.5 text-zinc-300">
            {Object.entries(resetResult.cleared).map(([table, count]) => (
              <li key={table}>
                {table}: {count} registro(s) removido(s)
              </li>
            ))}
          </ul>
          <div className="mt-1 text-xs text-zinc-400">
            Preservadas: {resetResult.preserved.join(", ")}
          </div>
        </div>
      )}

      {importResult && (
        <div className="mt-6 rounded-2xl border border-white/10 bg-[#26215C] p-4 text-sm">
          <div className="mb-1 font-semibold text-white">
            Última importação (modo: {importResult.mode})
          </div>
          <ul className="space-y-0.5 text-zinc-300">
            {Object.keys(importResult.inserted).map((table) => (
              <li key={table}>
                {table}: {importResult.inserted[table]} inserido(s),{" "}
                {importResult.skipped[table]} pulado(s),{" "}
                {importResult.updated[table]} atualizado(s)
              </li>
            ))}
          </ul>
        </div>
      )}

      {confirmOpen && (
        <Modal title="Confirmar reset de dados" onClose={() => setConfirmOpen(false)}>
          <p className="text-sm text-zinc-300">
            Tem certeza que deseja <span className="font-semibold text-red-300">zerar todos os dados</span>?
            Clientes, vendas, itens, pagamentos e inscrições de push serão apagados.
            Os usuários <span className="font-semibold text-white">não</span> serão removidos.
          </p>
          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirmOpen(false)}
              disabled={busy}
              className="rounded-full border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={doReset}
              disabled={busy}
              className="rounded-full bg-red-500/90 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50"
            >
              {busy ? "Zerando…" : "Confirmar e zerar"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}