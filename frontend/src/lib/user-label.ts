import type { User } from "../types.ts";

/** Rótulo do papel exibido na identificação do topo. */
export function roleLabel(role: User["role"]): string {
  return role === "admin" ? "Administrador" : "Usuário";
}

/** Iniciais do nome para o avatar (ex.: "Bruno de Sousa" -> "BS"). */
export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0][0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] ?? "" : "";
  return (first + last).toUpperCase();
}
