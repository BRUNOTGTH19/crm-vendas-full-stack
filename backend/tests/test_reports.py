"""Testes dos relatórios PDF (doc 2.5): emissão, filtros e validação de parâmetros.

Regressões cobertas nesta suíte:

- ``GET /reports/cashflow?month=2026-13`` (e ``2026-00`` / ``0000-01``)
  respondia **500 Internal Server Error**: a conversão de ``YYYY-MM`` tratava
  apenas o ``ValueError`` do ``split``, mas ``date(2026, 13, 1)`` estourava
  dentro do handler. Agora a faixa do mês/ano é validada com 400.
- As tabelas assumiam a largura natural do conteúdo e ultrapassavam a área útil
  do A4 (538pt para 451pt disponíveis), cortando as últimas colunas na margem
  direita. ``_column_widths`` agora soma exatamente a largura do frame.
- Período invertido (``start > end``) devolvia um relatório vazio sem
  explicação; agora responde 400.

Usa SQLite em memória com foreign keys e serviços externos simulados
(conftest.py). Nenhuma conexão com o banco configurado é realizada.
"""
import re
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

import routers.reports as reports_router
from database import SessionLocal
from main import app
from models.audit_log import AuditLog
from models.client import Client
from models.payment import Payment
from models.push_subscription import PushSubscription
from models.sale import Sale
from models.sale_item import SaleItem
from models.user import User
from services.pdf_service import _column_widths, build_report_pdf

client = TestClient(app)

PDF_ROUTES = [
    "/reports/paid?start=2026-01-01&end=2026-12-31",
    "/reports/pending",
    "/reports/charges",
    "/reports/cashflow?month=2026-09",
]

JSON_ROUTES = [
    "/reports/sales?start=2026-01-01&end=2026-12-31",
    "/reports/clients",
    "/reports/products",
]


# ---------------------------------------------------------------------------
# Infra dos testes (usuários isolados por teste)
# ---------------------------------------------------------------------------
def _register(email: str) -> None:
    r = client.post(
        "/auth/register",
        json={"name": "Relatorios Teste", "email": email, "password": "123456"},
    )
    assert r.status_code == 201, r.text


def _login(email: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": "123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _unique_email(prefix: str) -> str:
    return f"{prefix}_{datetime.now().strftime('%H%M%S%f')}@crm.com"


def _cleanup_user(email: str) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return
        db.query(AuditLog).filter(AuditLog.user_id == user.id).delete(
            synchronize_session=False
        )
        db.query(PushSubscription).filter(PushSubscription.user_id == user.id).delete(
            synchronize_session=False
        )
        client_ids = [
            c.id for c in db.query(Client).filter(Client.created_by_id == user.id)
        ]
        if client_ids:
            sale_ids = [
                s.id for s in db.query(Sale).filter(Sale.client_id.in_(client_ids))
            ]
            if sale_ids:
                db.query(Payment).filter(Payment.sale_id.in_(sale_ids)).delete(
                    synchronize_session=False
                )
                db.query(SaleItem).filter(SaleItem.sale_id.in_(sale_ids)).delete(
                    synchronize_session=False
                )
                db.query(Sale).filter(Sale.id.in_(sale_ids)).delete(
                    synchronize_session=False
                )
            db.query(Client).filter(Client.id.in_(client_ids)).delete(
                synchronize_session=False
            )
        db.delete(user)
        db.commit()


@pytest.fixture
def owner():
    """Usuário comum novo por teste — relatórios nunca misturam períodos."""
    email = _unique_email("relatorios")
    _register(email)
    yield {"email": email, "headers": _login(email)}
    _cleanup_user(email)


@pytest.fixture
def other_user():
    email = _unique_email("relatorios_outro")
    _register(email)
    yield {"email": email, "headers": _login(email)}
    _cleanup_user(email)


@pytest.fixture
def pdf_spy(monkeypatch):
    """Captura o conteúdo enviado ao gerador de PDF (sem abrir o binário).

    Os streams do ReportLab saem comprimidos (FlateDecode), então ler o texto
    dentro do PDF não é confiável — inspecionar as linhas recebidas por
    ``build_report_pdf`` prova o filtro de período/status/escopo de verdade.
    """
    calls: list[dict] = []

    def fake_build(title, subtitle, headers, rows, footers=None):
        calls.append(
            {
                "title": title,
                "subtitle": subtitle,
                "headers": headers,
                "rows": rows,
                "footers": footers,
            }
        )
        return b"%PDF-1.4\n% spy\n%%EOF"

    monkeypatch.setattr(reports_router, "build_report_pdf", fake_build)
    return calls


def _create_client(headers: dict, name: str) -> int:
    r = client.post("/clients", json={"full_name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_sale(
    headers: dict,
    client_id: int,
    *,
    sale_date: str,
    status: str = "pending",
    due_date: str | None = None,
    unit_price: str = "100.00",
    quantity: int = 1,
) -> int:
    payload = {
        "client_id": client_id,
        "sale_date": sale_date,
        "status": status,
        "items": [
            {
                "product_name": "Produto Relatorio",
                "quantity": quantity,
                "unit_price": unit_price,
            }
        ],
    }
    if status == "pending":
        payload["due_date"] = due_date or sale_date
    r = client.post("/sales", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Autenticação e cabeçalhos de download
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path", PDF_ROUTES + JSON_ROUTES)
def test_reports_require_authentication(path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    ("path", "filename"),
    [
        ("/reports/paid?start=2026-01-01&end=2026-12-31", "relatorio_vendas_pagas.pdf"),
        ("/reports/pending", "relatorio_vendas_pendentes.pdf"),
        ("/reports/charges", "relatorio_cobrancas.pdf"),
        ("/reports/cashflow?month=2026-09", "fechamento_caixa_2026-09.pdf"),
    ],
)
def test_pdf_reports_download_as_attachment(owner, path, filename):
    """O relatório é um download (``attachment``) e nunca um PDF cacheado."""
    r = client.get(path, headers=owner["headers"])
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF-")
    assert r.content.rstrip().endswith(b"%%EOF")
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"] == f'attachment; filename="{filename}"'
    assert "no-store" in r.headers["cache-control"]



# ---------------------------------------------------------------------------
# Filtros dos relatórios
# ---------------------------------------------------------------------------
def test_paid_report_filters_by_period_and_status(owner, pdf_spy):
    cid = _create_client(owner["headers"], "Cliente Vendas Pagas")
    dentro = _create_sale(owner["headers"], cid, sale_date="2026-03-10", status="paid")
    _create_sale(owner["headers"], cid, sale_date="2026-04-10", status="paid")
    _create_sale(
        owner["headers"],
        cid,
        sale_date="2026-03-11",
        status="pending",
        due_date="2026-03-20",
    )

    r = client.get(
        "/reports/paid?start=2026-03-01&end=2026-03-31", headers=owner["headers"]
    )
    assert r.status_code == 200, r.text
    assert len(pdf_spy) == 1
    call = pdf_spy[0]
    assert call["headers"] == ["Venda", "Cliente", "Data", "Total"]
    assert [row[0] for row in call["rows"]] == [f"#{dentro}"]
    assert call["rows"][0][1] == "Cliente Vendas Pagas"
    assert call["footers"] == ["TOTAL: R$ 100.00"]


def test_pending_and_charges_reports_exclude_paid_sales(owner, pdf_spy):
    cid = _create_client(owner["headers"], "Cliente Pendentes")
    # Datas relativas a hoje: o relatório de cobranças classifica "A vencer"
    # comparando com a data corrente, então datas fixas no passado quebrariam.
    vencimento = date.today() + timedelta(days=30)
    hoje = date.today().isoformat()
    pendente = _create_sale(
        owner["headers"],
        cid,
        sale_date=hoje,
        status="pending",
        due_date=vencimento.isoformat(),
        unit_price="25.50",
    )
    _create_sale(owner["headers"], cid, sale_date=hoje, status="paid")

    assert client.get("/reports/pending", headers=owner["headers"]).status_code == 200
    assert client.get("/reports/charges", headers=owner["headers"]).status_code == 200
    assert len(pdf_spy) == 2

    pendentes, cobrancas = pdf_spy
    assert [row[0] for row in pendentes["rows"]] == [f"#{pendente}"]
    assert pendentes["rows"][0][3] == vencimento.strftime("%d/%m/%Y")
    assert pendentes["footers"] == ["TOTAL PENDENTE: R$ 25.50"]

    assert [row[0] for row in cobrancas["rows"]] == [f"#{pendente}"]
    assert cobrancas["headers"] == [
        "Venda",
        "Cliente",
        "Vencimento",
        "Situação",
        "Valor",
    ]
    assert cobrancas["rows"][0][3] == "A vencer"


def test_charges_report_marks_overdue_sales(owner, pdf_spy):
    cid = _create_client(owner["headers"], "Cliente Vencido")
    ontem = (date.today() - timedelta(days=1)).isoformat()
    hoje = date.today().isoformat()
    vencida = _create_sale(
        owner["headers"], cid, sale_date=ontem, status="pending", due_date=ontem
    )
    vence_hoje = _create_sale(
        owner["headers"], cid, sale_date=hoje, status="pending", due_date=hoje
    )

    assert client.get("/reports/charges", headers=owner["headers"]).status_code == 200
    situacoes = {row[0]: row[3] for row in pdf_spy[0]["rows"]}
    assert situacoes[f"#{vencida}"] == "VENCIDA"
    assert situacoes[f"#{vence_hoje}"] == "Vence hoje"


def test_cashflow_report_totals_stay_inside_the_month(owner, pdf_spy):
    cid = _create_client(owner["headers"], "Cliente Fechamento")
    _create_sale(
        owner["headers"], cid, sale_date="2026-05-05", status="paid", unit_price="150.00"
    )
    _create_sale(
        owner["headers"],
        cid,
        sale_date="2026-05-06",
        status="pending",
        due_date="2026-06-06",
        unit_price="50.00",
    )
    _create_sale(
        owner["headers"], cid, sale_date="2026-06-01", status="paid", unit_price="999.00"
    )

    r = client.get("/reports/cashflow?month=2026-05", headers=owner["headers"])
    assert r.status_code == 200, r.text
    call = pdf_spy[0]
    assert len(call["rows"]) == 2
    assert call["footers"] == [
        "TOTAL RECEBIDO: R$ 150.00",
        "TOTAL PENDENTE: R$ 50.00",
        "MOVIMENTAÇÃO TOTAL: R$ 200.00",
    ]


def test_cashflow_without_month_uses_current_month(owner, pdf_spy):
    r = client.get("/reports/cashflow", headers=owner["headers"])
    assert r.status_code == 200, r.text
    hoje = date.today()
    primeiro_dia = hoje.replace(day=1)
    ultimo_dia = date(
        hoje.year + (1 if hoje.month == 12 else 0),
        1 if hoje.month == 12 else hoje.month + 1,
        1,
    ) - timedelta(days=1)

    assert pdf_spy[0]["title"] == "Fechamento de Caixa"
    assert pdf_spy[0]["subtitle"] == (
        f"Período: {primeiro_dia.strftime('%d/%m/%Y')} a {ultimo_dia.strftime('%d/%m/%Y')}"
    )


# ---------------------------------------------------------------------------
# Validação de parâmetros (regressão dos 500)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "month",
    ["2026-13", "2026-00", "0000-01", "1899-12", "3000-01", "abc", "2026", "2026-9-1"],
)
def test_invalid_month_returns_400_instead_of_500(owner, month):
    r = client.get(f"/reports/cashflow?month={month}", headers=owner["headers"])
    assert r.status_code == 400, f"{month} -> {r.status_code}: {r.text}"
    assert "detail" in r.json()


@pytest.mark.parametrize(
    "path",
    [
        "/reports/paid?start=2026-09-30&end=2026-09-01",
        "/reports/sales?start=2026-09-30&end=2026-09-01",
    ],
)
def test_inverted_period_returns_400(owner, path):
    r = client.get(path, headers=owner["headers"])
    assert r.status_code == 400, r.text
    assert "Período inválido" in r.json()["detail"]


@pytest.mark.parametrize(
    "path",
    ["/reports/paid", "/reports/paid?start=2026-09-01", "/reports/sales?end=2026-09-30"],
)
def test_missing_period_parameters_return_422(owner, path):
    assert client.get(path, headers=owner["headers"]).status_code == 422


# ---------------------------------------------------------------------------
# Escopo por dono
# ---------------------------------------------------------------------------
def test_pdf_reports_are_scoped_to_the_owner(owner, other_user, pdf_spy):
    meu_cliente = _create_client(owner["headers"], "Cliente Do Dono")
    _create_sale(
        owner["headers"],
        meu_cliente,
        sale_date="2026-07-01",
        status="pending",
        due_date="2026-07-31",
    )

    cliente_alheio = _create_client(other_user["headers"], "Cliente De Outro")
    _create_sale(
        other_user["headers"],
        cliente_alheio,
        sale_date="2026-07-02",
        status="pending",
        due_date="2026-07-31",
    )

    assert client.get("/reports/pending", headers=owner["headers"]).status_code == 200
    nomes = {row[1] for row in pdf_spy[0]["rows"]}
    assert nomes == {"Cliente Do Dono"}


def test_aggregate_reports_are_scoped_to_the_owner(owner, other_user):
    _create_client(owner["headers"], "Cliente Ranking Proprio")
    _create_client(other_user["headers"], "Cliente Ranking Alheio")

    r = client.get("/reports/clients", headers=owner["headers"])
    assert r.status_code == 200
    nomes = {row["client_name"] for row in r.json()}
    assert "Cliente Ranking Proprio" in nomes
    assert "Cliente Ranking Alheio" not in nomes


def test_sales_report_summarizes_the_period(owner):
    cid = _create_client(owner["headers"], "Cliente Resumo Periodo")
    _create_sale(
        owner["headers"], cid, sale_date="2026-08-10", status="paid", unit_price="10.00"
    )
    _create_sale(
        owner["headers"],
        cid,
        sale_date="2026-08-11",
        status="pending",
        due_date="2026-09-11",
        unit_price="30.00",
    )

    r = client.get(
        "/reports/sales?start=2026-08-01&end=2026-08-31", headers=owner["headers"]
    )
    assert r.status_code == 200
    body = r.json()
    assert body["sales_count"] == 2
    assert body["paid_total"] == 10.0
    assert body["pending_total"] == 30.0
    assert body["total"] == 40.0



# ---------------------------------------------------------------------------
# Robustez do gerador de PDF
# ---------------------------------------------------------------------------
def test_report_with_special_characters_in_client_name(owner):
    """Nomes com <, & e aspas não podem quebrar o XML interno do ReportLab."""
    cid = _create_client(owner["headers"], 'Loja <A&B> "XPTO" & Cia')
    _create_sale(
        owner["headers"],
        cid,
        sale_date="2026-09-01",
        status="pending",
        due_date="2026-09-20",
    )

    r = client.get("/reports/charges", headers=owner["headers"])
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF-")


def test_report_without_rows_still_builds_a_valid_pdf(owner):
    r = client.get("/reports/pending", headers=owner["headers"])
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF-")
    assert r.content.rstrip().endswith(b"%%EOF")


def test_column_widths_never_exceed_the_page_frame():
    """Regressão: a tabela somava 538pt em um frame de 451pt e era cortada."""
    headers = ["Venda", "Cliente", "Data da venda", "Vencimento", "Total"]
    rows = [
        [
            "#1234",
            "Maria Auxiliadora dos Santos Albuquerque Nascimento Pereira",
            "01/09/2026",
            "30/09/2026",
            "R$ 12345,67",
        ]
    ]
    disponivel = A4[0] - 30 * mm

    larguras = _column_widths(headers, rows, disponivel)
    assert len(larguras) == len(headers)
    assert all(largura > 0 for largura in larguras)
    assert sum(larguras) == pytest.approx(disponivel, abs=0.01)
    # A coluna do nome fica com a maior fatia (o texto longo quebra em linhas).
    assert max(larguras) == pytest.approx(larguras[1])


def test_build_report_pdf_paginates_long_reports():
    headers = ["Venda", "Cliente", "Data", "Vencimento", "Total"]
    rows = [
        [f"#{i}", f"Cliente {i}", "01/09/2026", "30/09/2026", "R$ 10,00"]
        for i in range(200)
    ]

    pdf = build_report_pdf(
        "Relatório Grande", "Período", headers, rows, ["TOTAL: R$ 2000,00"]
    )
    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    pagina_count = re.search(rb"/Count (\d+)", pdf)
    assert pagina_count is not None
    assert int(pagina_count.group(1)) > 1


def test_build_report_pdf_without_rows_or_footers():
    pdf = build_report_pdf("Sem registros", "Período", ["Venda", "Cliente"], [])
    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
