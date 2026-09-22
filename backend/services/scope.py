"""Isolamento de dados por dono (escopo multiusuário).

``owner_id=None`` significa escopo GLOBAL (sem filtro de dono) — usado apenas
para administradores que não selecionaram um usuário específico.
Qualquer outro valor restringe a consulta às linhas daquele dono.
"""


def scoped(query, column, owner_id: int | None):
    """Aplica o filtro de dono à consulta quando há escopo definido."""
    if owner_id is not None:
        query = query.filter(column == owner_id)
    return query