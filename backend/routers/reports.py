from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import resolve_data_owner
from models.client import Client
from models.sale import Sale, SaleStatus
from models.sale_item import SaleItem
from services.pdf_service import build_report_pdf
from services.scope import scoped

router = APIRouter(prefix="/reports", tags=["Reports"])

# Limites do ano aceito em `?month=YYYY-MM` — evita datas absurdas (ex.: 0000-01).
MIN_REPORT_YEAR = 1900
MAX_REPORT_YEAR = 2999


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    """Entrega o PDF como download.

    ``attachment`` (e não ``inline``) porque o usuário está *emitindo* um
    relatório — o navegador deve salvar/abrir o arquivo, nunca renderizá-lo
    como página. ``no-store`` impede que proxy, service worker ou cache do
    navegador sirvam um PDF antigo depois de mudanças nos dados.
    """
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def _validate_period(start: date, end: date) -> None:
    """Período invertido devolveria relatório vazio sem explicação — 400 é mais claro."""
    if start > end:
        raise HTTPException(
            status_code=400,
            detail="Período inválido: a data inicial não pode ser maior que a data final.",
        )


def _client_name(sale: Sale) -> str:
    """Nome do cliente do relatório (defensivo: nunca quebra a emissão)."""
    return sale.client.full_name if sale.client else f"Cliente {sale.client_id}"


def parse_month(month: str) -> tuple[int, int]:
    """Valida ``YYYY-MM`` e devolve ``(ano, mês)``.

    Levanta 400 em formato inválido **e** em mês/ano fora de faixa: antes,
    ``?month=2026-13`` passava pela conversão de inteiros e estourava
    ``date(2026, 13, 1)`` com 500 Internal Server Error.
    """
    try:
        year_str, month_str = month.split("-")
        year, mon = int(year_str), int(month_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de mês inválido. Use YYYY-MM (ex.: 2026-09).",
        ) from None

    if not 1 <= mon <= 12:
        raise HTTPException(
            status_code=400,
            detail="Mês inválido: use um valor entre 01 e 12.",
        )
    if not MIN_REPORT_YEAR <= year <= MAX_REPORT_YEAR:
        raise HTTPException(
            status_code=400,
            detail=f"Ano inválido: use um valor entre {MIN_REPORT_YEAR} e {MAX_REPORT_YEAR}.",
        )
    return year, mon


@router.get("/paid")
def paid_report_pdf(
    start: date = Query(..., description="Data inicial (YYYY-MM-DD)"),
    end: date = Query(..., description="Data final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Relatório PDF de vendas pagas no período (doc 2.5), no escopo resolvido."""
    _validate_period(start, end)
    sales = (
        scoped(db.query(Sale), Sale.user_id, owner_id)
        .filter(
            Sale.status == SaleStatus.paid,
            Sale.sale_date >= start,
            Sale.sale_date <= end,
        )
        .order_by(Sale.sale_date, Sale.id)
        .all()
    )
    rows = [
        [
            f"#{s.id}",
            _client_name(s),
            s.sale_date.strftime("%d/%m/%Y"),
            f"R$ {float(s.total):.2f}",
        ]
        for s in sales
    ]
    total = sum(float(s.total) for s in sales)
    pdf = build_report_pdf(
        "Relatório de Vendas Pagas",
        f"Período: {start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}",
        ["Venda", "Cliente", "Data", "Total"],
        rows,
        [f"TOTAL: R$ {total:.2f}"],
    )
    return _pdf_response(pdf, "relatorio_vendas_pagas.pdf")


@router.get("/pending")
def pending_report_pdf(
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Relatório PDF de vendas pendentes (doc 2.5), no escopo resolvido."""
    sales = (
        scoped(db.query(Sale), Sale.user_id, owner_id)
        .filter(Sale.status == SaleStatus.pending)
        .order_by(Sale.due_date, Sale.id)
        .all()
    )
    rows = [
        [
            f"#{s.id}",
            _client_name(s),
            s.sale_date.strftime("%d/%m/%Y"),
            s.due_date.strftime("%d/%m/%Y") if s.due_date else "—",
            f"R$ {float(s.total):.2f}",
        ]
        for s in sales
    ]
    total = sum(float(s.total) for s in sales)
    pdf = build_report_pdf(
        "Relatório de Vendas Pendentes",
        f"Emitido em {date.today().strftime('%d/%m/%Y')}",
        ["Venda", "Cliente", "Data da venda", "Vencimento", "Total"],
        rows,
        [f"TOTAL PENDENTE: R$ {total:.2f}"],
    )
    return _pdf_response(pdf, "relatorio_vendas_pendentes.pdf")


@router.get("/charges")
def charges_report_pdf(
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Relatório PDF de cobranças (doc 2.5), no escopo resolvido."""
    today = date.today()
    sales = (
        scoped(db.query(Sale), Sale.user_id, owner_id)
        .filter(
            Sale.status == SaleStatus.pending,
            Sale.due_date.isnot(None),
        )
        .order_by(Sale.due_date, Sale.id)
        .all()
    )
    rows = []
    total = 0.0
    for s in sales:
        if s.due_date < today:
            situacao = "VENCIDA"
        elif s.due_date == today:
            situacao = "Vence hoje"
        else:
            situacao = "A vencer"
        rows.append(
            [
                f"#{s.id}",
                _client_name(s),
                s.due_date.strftime("%d/%m/%Y"),
                situacao,
                f"R$ {float(s.total):.2f}",
            ]
        )
        total += float(s.total)
    pdf = build_report_pdf(
        "Relatório de Cobranças",
        f"Cobranças pendentes — emitido em {today.strftime('%d/%m/%Y')}",
        ["Venda", "Cliente", "Vencimento", "Situação", "Valor"],
        rows,
        [f"TOTAL A COBRAR: R$ {total:.2f}"],
    )
    return _pdf_response(pdf, "relatorio_cobrancas.pdf")


@router.get("/cashflow")
def cashflow_report_pdf(
    month: str = Query(
        None,
        description="Mês de referência no formato YYYY-MM (padrão: mês atual)",
    ),
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Fechamento de caixa do mês em PDF (doc 2.5), no escopo resolvido."""
    today = date.today()
    if month:
        year, mon = parse_month(month)
    else:
        year, mon = today.year, today.month

    first_day = date(year, mon, 1)
    next_month = date(year + (1 if mon == 12 else 0), 1 if mon == 12 else mon + 1, 1)
    last_day = next_month - timedelta(days=1)

    sales = (
        scoped(db.query(Sale), Sale.user_id, owner_id)
        .filter(
            Sale.sale_date >= first_day,
            Sale.sale_date <= last_day,
        )
        .order_by(Sale.sale_date, Sale.id)
        .all()
    )
    paid_total = sum(float(s.total) for s in sales if s.status == SaleStatus.paid)
    pending_total = sum(float(s.remaining) for s in sales if s.status == SaleStatus.pending)
    rows = [
        [
            f"#{s.id}",
            _client_name(s),
            s.sale_date.strftime("%d/%m/%Y"),
            "Paga" if s.status == SaleStatus.paid else "Pendente",
            f"R$ {float(s.total):.2f}",
        ]
        for s in sales
    ]
    pdf = build_report_pdf(
        "Fechamento de Caixa",
        f"Período: {first_day.strftime('%d/%m/%Y')} a {last_day.strftime('%d/%m/%Y')}",
        ["Venda", "Cliente", "Data", "Status", "Valor"],
        rows,
        [
            f"TOTAL RECEBIDO: R$ {paid_total:.2f}",
            f"TOTAL PENDENTE: R$ {pending_total:.2f}",
            f"MOVIMENTAÇÃO TOTAL: R$ {paid_total + pending_total:.2f}",
        ],
    )
    return _pdf_response(pdf, f"fechamento_caixa_{year}-{mon:02d}.pdf")


@router.get("/period")
def period_report_pdf(
    start: date = Query(..., description="Data inicial (YYYY-MM-DD)"),
    end: date = Query(..., description="Data final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Relatório PDF de **todas** as vendas do período (pagas e pendentes).

    É o PDF correspondente ao cartão "Vendas por período" da tela: o botão
    "Gerar" filtrava a tabela, mas não existia arquivo para baixar — por isso a
    emissão por período parecia quebrada mesmo com as datas selecionadas.
    Traz status e totalizadores de pago/pendente para o período.
    """
    _validate_period(start, end)
    sales = (
        scoped(db.query(Sale), Sale.user_id, owner_id)
        .filter(
            Sale.sale_date >= start,
            Sale.sale_date <= end,
        )
        .order_by(Sale.sale_date, Sale.id)
        .all()
    )
    rows = [
        [
            f"#{s.id}",
            _client_name(s),
            s.sale_date.strftime("%d/%m/%Y"),
            "Paga" if s.status == SaleStatus.paid else "Pendente",
            f"R$ {float(s.total):.2f}",
        ]
        for s in sales
    ]
    paid_total = sum(float(s.total) for s in sales if s.status == SaleStatus.paid)
    pending_total = sum(float(s.remaining) for s in sales if s.status == SaleStatus.pending)
    total = sum(float(s.total) for s in sales)
    pdf = build_report_pdf(
        "Relatório de Vendas por Período",
        f"Período: {start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}",
        ["Venda", "Cliente", "Data", "Status", "Valor"],
        rows,
        [
            f"VENDAS NO PERÍODO: {len(sales)}",
            f"TOTAL RECEBIDO: R$ {paid_total:.2f}",
            f"TOTAL PENDENTE: R$ {pending_total:.2f}",
            f"TOTAL GERAL: R$ {total:.2f}",
        ],
    )
    return _pdf_response(pdf, f"relatorio_vendas_{start.isoformat()}_a_{end.isoformat()}.pdf")


@router.get("/sales")
def sales_report(
    start: date = Query(..., description="Data inicial (YYYY-MM-DD)"),
    end: date = Query(..., description="Data final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Resumo de vendas no período, no escopo resolvido."""
    _validate_period(start, end)
    sales = (
        scoped(db.query(Sale), Sale.user_id, owner_id)
        .filter(
            Sale.sale_date >= start,
            Sale.sale_date <= end,
        )
        .order_by(Sale.sale_date, Sale.id)
        .all()
    )
    total = sum(s.total for s in sales)
    paid_total = sum(s.total for s in sales if s.status == SaleStatus.paid)
    pending_total = sum(s.remaining for s in sales if s.status == SaleStatus.pending)
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "sales_count": len(sales),
        "total": float(total),
        "paid_total": float(paid_total),
        "pending_total": float(pending_total),
        "sales": [
            {
                "id": s.id,
                "client_id": s.client_id,
                "client_name": _client_name(s),
                "sale_date": s.sale_date.isoformat(),
                "status": s.status.value,
                "total": float(s.total),
            }
            for s in sales
        ],
    }


@router.get("/clients")
def clients_report(
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Total de vendas e faturamento por cliente, no escopo resolvido."""
    rows = (
        scoped(
            db.query(
                Client.id,
                Client.full_name,
                func.count(Sale.id).label("sales_count"),
                func.coalesce(func.sum(Sale.total), 0).label("total_revenue"),
            ).outerjoin(Sale, Sale.client_id == Client.id),
            Client.created_by_id,
            owner_id,
        )
        .group_by(Client.id, Client.full_name)
        .order_by(func.sum(Sale.total).desc())
        .all()
    )
    return [
        {
            "client_id": r.id,
            "client_name": r.full_name,
            "sales_count": r.sales_count,
            "total_revenue": float(r.total_revenue),
        }
        for r in rows
    ]


@router.get("/products")
def products_report(
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Produtos mais vendidos, no escopo resolvido."""
    rows = (
        scoped(
            db.query(
                SaleItem.product_name,
                func.sum(SaleItem.quantity).label("total_quantity"),
                func.sum(SaleItem.subtotal).label("total_revenue"),
            ).join(Sale, Sale.id == SaleItem.sale_id),
            Sale.user_id,
            owner_id,
        )
        .group_by(SaleItem.product_name)
        .order_by(func.sum(SaleItem.quantity).desc())
        .all()
    )
    return [
        {
            "product_name": r.product_name,
            "total_quantity": int(r.total_quantity),
            "total_revenue": float(r.total_revenue),
        }
        for r in rows
    ]