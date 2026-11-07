"""add indexes for scope and filter columns

Antes desta revisão NENHUMA coluna de filtro era indexada (só as chaves
primárias e alguns únicos). Toda consulta escopada por dono — o padrão do CRM —
fazia varredura completa da tabela, e o custo crescia linearmente com o volume
de dados de TODOS os usuários, não só do escopo consultado.

Índices criados, na ordem em que as consultas acontecem:

- ``sales``: escopo por dono + status (pendentes), vencimento (cobranças e
  agendador), período (relatórios) e histórico por cliente;
- ``sale_items`` e ``payments``: itens/recebimentos de uma venda;
- ``clients``: escopo por dono;
- ``push_subscriptions`` e ``audit_logs``: filtro por usuário.

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-09-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_sales_client_id", "sales", ["client_id"]),
    ("ix_sales_due_date", "sales", ["due_date"]),
    ("ix_sales_user_status", "sales", ["user_id", "status"]),
    ("ix_sales_user_due_date", "sales", ["user_id", "due_date"]),
    ("ix_sales_user_sale_date", "sales", ["user_id", "sale_date"]),
    ("ix_sale_items_sale_id", "sale_items", ["sale_id"]),
    ("ix_payments_sale_id", "payments", ["sale_id"]),
    ("ix_clients_created_by_id", "clients", ["created_by_id"]),
    ("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"]),
    ("ix_audit_logs_user_id", "audit_logs", ["user_id"]),
]


def upgrade() -> None:
    """Upgrade schema."""
    for name, table, columns in INDEXES:
        op.create_index(op.f(name), table, columns, unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    for name, table, _ in reversed(INDEXES):
        op.drop_index(op.f(name), table_name=table)
