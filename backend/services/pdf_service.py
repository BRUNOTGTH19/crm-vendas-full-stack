"""Geração de PDF de recibo sem dependências externas."""
from io import BytesIO
from decimal import Decimal

from models.client import Client
from models.sale import Sale


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _ascii(text: str) -> str:
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


def _build_pdf(lines: list[tuple[int, int, str]]) -> bytes:
    """Recebe lista de (tamanho_fonte, x, texto) e monta um PDF de 1 página."""
    parts = []
    y = 780
    for size, x, text in lines:
        parts.append(
            f"BT /F1 {size} Tf {x} {y} Td ({_escape(_ascii(text))}) Tj ET"
        )
        y -= size + 8
    content = "\n".join(parts).encode("latin-1")

    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = []

    def write_obj(data: bytes) -> int:
        offsets.append(buffer.tell())
        buffer.write(data)
        return len(offsets)

    write_obj(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    write_obj(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    write_obj(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    content_obj = (
        f"4 0 obj\n<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream\nendobj\n"
    )
    write_obj(content_obj)
    write_obj(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    xref_pos = buffer.tell()
    buffer.write(f"xref\n0 {len(offsets) + 1}\n".encode())
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets:
        buffer.write(f"{offset:010d} 00000 n \n".encode())
    buffer.write(
        f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
    )
    return buffer.getvalue()


def generate_invoice_pdf(sale: Sale, client: Client) -> bytes:
    lines: list[tuple[int, int, str]] = [
        (18, 50, "RECIBO DE VENDA"),
        (10, 50, f"Venda #{sale.id}"),
        (12, 50, f"Cliente: {client.full_name}"),
        (12, 50, f"Data: {sale.sale_date.strftime('%d/%m/%Y')}"),
        (12, 50, f"Status: {'PAGA' if sale.status.value == 'paid' else 'PENDENTE'}"),
        (10, 50, "-" * 60),
    ]
    for item in sale.items:
        lines.append(
            (
                10,
                50,
                f"{item.quantity}x {item.product_name} - "
                f"R$ {item.unit_price:.2f} = R$ {item.subtotal:.2f}",
            )
        )
    lines.append((10, 50, "-" * 60))
    lines.append((14, 50, f"TOTAL: R$ {Decimal(sale.total):.2f}"))
    if sale.due_date:
        lines.append((10, 50, f"Vencimento: {sale.due_date.strftime('%d/%m/%Y')}"))
    return _build_pdf(lines)


# ---------------------------------------------------------------------------
# Relatórios em PDF com ReportLab (doc oficial 1.2 e 2.5 — gerados sob
# demanda, em memória, sem persistência de arquivos em disco)
# ---------------------------------------------------------------------------

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PRIMARY_COLOR = colors.HexColor("#26215C")  # roxo — doc 3.4


def build_report_pdf(
    title: str,
    subtitle: str,
    headers: list[str],
    rows: list[list[str]],
    footers: list[str] | None = None,
) -> bytes:
    """Monta um relatório tabular em PDF e retorna os bytes em memória."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=title,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()

    story: list = [
        Paragraph(title, styles["Title"]),
        Spacer(1, 2 * mm),
        Paragraph(subtitle, styles["Normal"]),
        Spacer(1, 6 * mm),
    ]

    table_data = [headers] + (rows if rows else [["—"] + [""] * (len(headers) - 1)])
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F1F8")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)

    if footers:
        story.append(Spacer(1, 6 * mm))
        for line in footers:
            story.append(Paragraph(f"<b>{line}</b>", styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()

