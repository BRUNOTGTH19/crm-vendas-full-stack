from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from models.client import Client
from models.sale import Sale, SaleStatus
from models.user import User
from models.sale_item import SaleItem
from services.pdf_service import build_report_pdf

router = APIRouter(prefix="/reports", tags=["Reports"])


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/paid")
def paid_report_pdf(
    start: date = Query(..., description="Data inicial (YYYY-MM-DD)"),
    end: date = Query(..., description="Data final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Relatório PDF de vendas pagas no período (doc 2.5)."""
    sales = (
        db.query(Sale)
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
            s.client.full_name,
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
    current_user: User = Depends(get_current_user_dependency),
):
    """Relatório PDF de vendas pendentes (doc 2.5)."""
    sales = (
        db.query(Sale)
        .filter(Sale.status == SaleStatus.pending)
        .order_by(Sale.due_date, Sale.id)
        .all()
    )
    rows = [
        [
            f"#{s.id}",
            s.client.full_name,
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
    current_user: User = Depends(get_current_user_dependency),
):
    """Relatório PDF de cobranças com dados do cliente e da compra (doc 2.5)."""
    today = date.today()
    sales = (
        db.query(Sale)
        .filter(Sale.status == SaleStatus.pending, Sale.due_date.isnot(None))
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
                s.client.full_name,
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
    current_user: User = Depends(get_current_user_dependency),
):
    """Fechamento de caixa do mês em PDF (doc 2.5)."""
    today = date.today()
    if month:
        try:
            year, mon = (int(part) for part in month.split("-"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Formato de mês inválido. Use YYYY-MM.",
            )
    else:
        year, mon = today.year, today.month

    first_day = date(year, mon, 1)
    next_month = date(year + (1 if mon == 12 else 0), 1 if mon == 12 else mon + 1, 1)
    last_day = next_month - timedelta(days=1)

    sales = (
        db.query(Sale)
        .filter(Sale.sale_date >= first_day, Sale.sale_date <= last_day)
        .order_by(Sale.sale_date, Sale.id)
        .all()
    )
    paid_total = sum(float(s.total) for s in sales if s.status == SaleStatus.paid)
    pending_total = sum(float(s.total) for s in sales if s.status == SaleStatus.pending)
    rows = [
        [
            f"#{s.id}",
            s.client.full_name,
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


@router.get("/sales")
def sales_report(
    start: date = Query(..., description="Data inicial (YYYY-MM-DD)"),
    end: date = Query(..., description="Data final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Resumo de vendas no período."""
    sales = (
        db.query(Sale)
        .filter(Sale.sale_date >= start, Sale.sale_date <= end)
        .order_by(Sale.sale_date, Sale.id)
        .all()
    )
    total = sum(s.total for s in sales)
    paid_total = sum(s.total for s in sales if s.status == SaleStatus.paid)
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "sales_count": len(sales),
        "total": float(total),
        "paid_total": float(paid_total),
        "pending_total": float(total - paid_total),
        "sales": [
            {
                "id": s.id,
                "client_id": s.client_id,
                "client_name": s.client.full_name,
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
    current_user: User = Depends(get_current_user_dependency),
):
    """Total de vendas e faturamento por cliente."""
    rows = (
        db.query(
            Client.id,
            Client.full_name,
            func.count(Sale.id).label("sales_count"),
            func.coalesce(func.sum(Sale.total), 0).label("total_revenue"),
        )
        .outerjoin(Sale, Sale.client_id == Client.id)
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
    current_user: User = Depends(get_current_user_dependency),
):
    """Produtos mais vendidos."""
    rows = (
        db.query(
            SaleItem.product_name,
            func.sum(SaleItem.quantity).label("total_quantity"),
            func.sum(SaleItem.subtotal).label("total_revenue"),
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

