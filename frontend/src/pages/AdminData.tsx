import { useEffect, useRef, useState } from "react";
import { Modal } from "../components/Modal.tsx";
import { PageHeader } from "../components/PageHeader.tsx";
import {
  IconAlert,
  IconCheck,
  IconDatabase,
  IconDownload,
  IconTrash,
  IconUpload,
} from "../components/icons.tsx";
import {
  ApiError,
  adminCreateResetToken,
  adminDeleteUser,
  adminExportDatabase,
  adminImportDatabase,
  adminListUsers,
  adminResetDatabase,
  copyToClipboard,
  getSessionUser,
  type AdminImportResult,
  type AdminResetResult,
  type AdminResetTokenResult,
  type AdminUser,
} from "../lib/api.ts";

/**
 * Área restrita a administradores: zerar, exportar, importar dados e
 * gerenciar usuários. Rota: #/admin/dados (só renderizada quando o
 * usuário tem role "admin").
 */
export function AdminData() {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [resetResult, setResetResult] = useState<AdminResetResult | null>(null);
  const [importResult, setImportResult] = useState<AdminImportResult | null>(null);
  const [importMode, setImportMode] = useState<"skip" | "overwrite">("skip");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersBusy, setUsersBusy] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);
  const [tokenUser, setTokenUser] = useState<AdminUser | null>(null);
  const [resetToken, setResetToken] = useState<AdminResetTokenResult | null>(null);
  const [tokenBusy, setTokenBusy] = useState(false);
  const [tokenCopied, setTokenCopied] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const me = getSessionUser();

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

  async function loadUsers() {
    setUsersBusy(true);
    setError("");
    try {
      setUsers(await adminListUsers());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setUsersBusy(false);
    }
  }

  useEffect(() => {
    void loadUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function closeTokenModal() {
    if (tokenBusy) return;
    setTokenUser(null);
    setResetToken(null);
    setTokenCopied(false);
  }

  async function doGenerateResetToken(user: AdminUser) {
    setTokenUser(user);
    setResetToken(null);
    setTokenCopied(false);
    setTokenBusy(true);
    setError("");
    setOk("");
    try {
      setResetToken(await adminCreateResetToken(user.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
      setTokenUser(null);
    } finally {
      setTokenBusy(false);
    }
  }

  async function copyResetToken() {
    if (!resetToken) return;
    await copyToClipboard(resetToken.token);
    setTokenCopied(true);
    window.setTimeout(() => setTokenCopied(false), 2000);
  }

  async function doDeleteUser() {
    if (!deleteTarget) return;
    setBusy(true);
    setError("");
    setOk("");
    try {
      await adminDeleteUser(deleteTarget.id);
      setOk(`Usuário ${deleteTarget.email} excluído com seus dados.`);
      setDeleteTarget(null);
      await loadUsers();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="animate-fade-up space-y-4 sm:space-y-6">
      <PageHeader
        title="Gestão de dados"
        eyebrow="Administração"
        subtitle="Área restrita a administradores. O reset apaga as tabelas de dados (clientes, vendas, itens, pagamentos e inscrições de push) e preserva os usuários."
      />

      {error && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-700/20 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-300/20 dark:bg-rose-400/15 dark:text-rose-200"
        >
          {error}
        </div>
      )}
      {ok && (
        <div
          role="status"
          className="rounded-2xl border border-brand-700/20 bg-brand-50 px-4 py-3 text-sm font-semibold text-brand-700 dark:border-brand-300/20 dark:bg-brand-400/15 dark:text-brand-200"
        >
          {ok}
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {/* Reset */}
        <section className="card card-pad flex min-w-0 flex-col">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-700 dark:bg-rose-400/15 dark:text-rose-200">
            <IconTrash className="h-5 w-5" />
          </span>
          <h2 className="section-title mt-3">Zerar dados</h2>
          <p className="hint mt-1 flex-1">
            Apaga todos os registros de dados do ambiente de teste. Ação
            irreversível — exporte antes se quiser guardar.
          </p>
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            disabled={busy}
            className="btn btn-danger mt-4 w-full"
          >
            Zerar dados
          </button>
        </section>

        {/* Export */}
        <section className="card card-pad flex min-w-0 flex-col">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-700 dark:bg-brand-400/15 dark:text-brand-200">
            <IconDownload className="h-5 w-5" />
          </span>
          <h2 className="section-title mt-3">Exportar</h2>
          <p className="hint mt-1 flex-1">
            Baixa um arquivo JSON com todos os registros das tabelas de dados.
          </p>
          <button
            type="button"
            onClick={doExport}
            disabled={busy}
            className="btn btn-primary mt-4 w-full"
          >
            Exportar dados
          </button>
        </section>

        {/* Import */}
        <section className="card card-pad flex min-w-0 flex-col">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-700 dark:bg-amber-400/15 dark:text-amber-200">
            <IconUpload className="h-5 w-5" />
          </span>
          <h2 className="section-title mt-3">Importar</h2>
          <p className="hint mt-1 flex-1">
            Reinsere os dados de um arquivo exportado anteriormente.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="field mt-3 text-xs file:mr-3 file:rounded-full file:border-0 file:bg-brand-950 file:px-3 file:py-1.5 file:text-xs file:font-bold file:text-white dark:file:bg-lime dark:file:text-brand-950"
          />
          <label className="mt-3 flex flex-wrap items-center gap-2 text-xs font-semibold text-ink/70">
            <span>Conflitos de ID:</span>
            <select
              value={importMode}
              onChange={(e) => setImportMode(e.target.value as "skip" | "overwrite")}
              className="field min-w-0 flex-1 py-1.5 text-xs sm:flex-none"
            >
              <option value="skip">Pular existentes (skip)</option>
              <option value="overwrite">Sobrescrever (overwrite)</option>
            </select>
          </label>
          <button
            type="button"
            onClick={doImport}
            disabled={busy}
            className="btn btn-lime mt-3 w-full"
          >
            Importar dados
          </button>
        </section>
      </div>

      {/* Usuários */}
      <section className="card card-pad">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="section-title">Usuários</h2>
            <p className="hint mt-1 max-w-2xl">
              Excluir um usuário comum remove também os clientes, vendas,
              pagamentos e inscrições de push dele. Administradores são
              protegidos e não podem ser excluídos.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadUsers()}
            disabled={usersBusy}
            className="btn btn-ghost btn-sm"
          >
            {usersBusy ? "Carregando…" : "Atualizar lista"}
          </button>
        </div>
        <ul className="mt-4 space-y-2">
          {users.map((u) => (
            <li
              key={u.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-ink/[0.06] bg-white/60 px-4 py-3 dark:border-white/10 dark:bg-white/5"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 text-sm font-bold text-ink">
                  <span className="truncate">{u.name}</span>
                  <span
                    className={`chip uppercase ${
                      u.role === "admin"
                        ? "bg-amber-50 text-amber-700 dark:bg-amber-400/15 dark:text-amber-200"
                        : "bg-brand-50 text-brand-700 dark:bg-brand-400/15 dark:text-brand-200"
                    }`}
                  >
                    {u.role}
                  </span>
                </div>
                <div className="truncate text-xs text-ink/70">{u.email}</div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {u.id !== me?.id ? (
                  <button
                    type="button"
                    onClick={() => void doGenerateResetToken(u)}
                    disabled={tokenBusy}
                    className="btn btn-primary btn-sm"
                  >
                    {tokenBusy && tokenUser?.id === u.id
                      ? "Gerando…"
                      : "Gerar token de redefinição"}
                  </button>
                ) : (
                  <span className="text-xs font-semibold text-ink/70">você</span>
                )}
                {u.role === "user" && (
                  <button
                    type="button"
                    onClick={() => setDeleteTarget(u)}
                    disabled={busy}
                    className="btn btn-danger btn-sm"
                  >
                    Excluir
                  </button>
                )}
              </div>
            </li>
          ))}
          {!usersBusy && users.length === 0 && (
            <li className="rounded-2xl border border-ink/[0.06] bg-white/60 px-4 py-3 text-xs text-ink/70 dark:border-white/10 dark:bg-white/5">
              Nenhum usuário encontrado.
            </li>
          )}
        </ul>
      </section>

      {resetResult && (
        <div className="card p-4 text-sm">
          <div className="mb-1 flex items-center gap-2 font-bold text-ink">
            <IconDatabase className="h-4 w-4" />
            Último reset
          </div>
          <ul className="space-y-0.5 text-ink/70">
            {Object.entries(resetResult.cleared).map(([table, count]) => (
              <li key={table}>
                {table}: {count} registro(s) removido(s)
              </li>
            ))}
          </ul>
          <div className="mt-1 text-xs text-ink/70">
            Preservadas: {resetResult.preserved.join(", ")}
          </div>
        </div>
      )}

      {importResult && (
        <div className="card p-4 text-sm">
          <div className="mb-1 flex items-center gap-2 font-bold text-ink">
            <IconCheck className="h-4 w-4" />
            Última importação (modo: {importResult.mode})
          </div>
          <ul className="space-y-0.5 text-ink/70">
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
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-rose-50 text-rose-700 dark:bg-rose-400/15 dark:text-rose-200">
              <IconAlert className="h-5 w-5" />
            </span>
            <p className="text-sm leading-relaxed text-ink/70">
              Tem certeza que deseja{" "}
              <span className="font-bold text-rose-600 dark:text-rose-300">
                zerar todos os dados
              </span>
              ? Clientes, vendas, itens, pagamentos e inscrições de push serão
              apagados. Os usuários <span className="font-bold text-ink">não</span> serão
              removidos.
            </p>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirmOpen(false)}
              disabled={busy}
              className="btn btn-ghost"
            >
              Cancelar
            </button>
            <button type="button" onClick={doReset} disabled={busy} className="btn btn-danger">
              {busy ? "Zerando…" : "Confirmar e zerar"}
            </button>
          </div>
        </Modal>
      )}

      {tokenUser && (
        <Modal title="Token de redefinição de senha" onClose={closeTokenModal}>
          <p className="text-sm text-ink/70">
            Token para{" "}
            <span className="font-bold text-ink">{tokenUser.name}</span> ({tokenUser.email}).
            Entregue o token pessoalmente ao usuário.
          </p>

          {tokenBusy && (
            <p className="mt-4 rounded-2xl bg-ink/[0.04] px-4 py-3 text-sm text-ink/70 dark:bg-white/5">
              Gerando token…
            </p>
          )}

          {resetToken && (
            <>
              <div className="mt-4 break-all rounded-2xl border border-brand-700/20 bg-brand-50 px-4 py-3 font-mono text-xs leading-relaxed text-brand-700 dark:border-brand-300/20 dark:bg-brand-400/15 dark:text-brand-200">
                {resetToken.token}
              </div>
              <p className="mt-2 text-xs font-semibold text-amber-700 dark:text-amber-300">
                Expira em 15 minutos e não será exibido novamente. Copie agora.
              </p>
              <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <button type="button" onClick={closeTokenModal} className="btn btn-ghost">
                  Fechar
                </button>
                <button
                  type="button"
                  onClick={() => void copyResetToken()}
                  className="btn btn-primary"
                >
                  {tokenCopied ? "Copiado ✓" : "Copiar token"}
                </button>
              </div>
            </>
          )}
        </Modal>
      )}

      {deleteTarget && (
        <Modal
          title="Confirmar exclusão de usuário"
          onClose={() => {
            if (!busy) setDeleteTarget(null);
          }}
        >
          <p className="text-sm leading-relaxed text-ink/70">
            Excluir <span className="font-bold text-ink">{deleteTarget.name}</span> (
            {deleteTarget.email})? Todos os dados dele serão apagados: clientes,
            vendas, itens, pagamentos e inscrições de push.{" "}
            <span className="font-bold text-rose-600 dark:text-rose-300">
              Esta ação não tem volta.
            </span>
          </p>
          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setDeleteTarget(null)}
              disabled={busy}
              className="btn btn-ghost"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={doDeleteUser}
              disabled={busy}
              className="btn btn-danger"
            >
              {busy ? "Excluindo…" : "Confirmar exclusão"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
