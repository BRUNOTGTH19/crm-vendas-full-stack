"""Geração de PDF de recibo sem dependências externas."""
from datetime import date
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape as escape_xml

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
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import settings

PRIMARY_COLOR = colors.HexColor("#26215C")  # roxo — doc 3.4
LIGHT_ROW_COLOR = colors.HexColor("#F2F1F8")
GRID_COLOR = colors.HexColor("#999999")
MUTED_COLOR = colors.HexColor("#555555")

REPORT_FONT_SIZE = 8
REPORT_LEADING = 10
MIN_COLUMN_WIDTH = 16 * mm
NO_ROWS_TEXT = "Nenhum registro no período."

_CELL_STYLE = ParagraphStyle(
    "ReportCell",
    fontName="Helvetica",
    fontSize=REPORT_FONT_SIZE,
    leading=REPORT_LEADING,
)
_HEADER_STYLE = ParagraphStyle(
    "ReportHeader",
    fontName="Helvetica-Bold",
    fontSize=REPORT_FONT_SIZE,
    leading=REPORT_LEADING,
    textColor=colors.white,
)


def _column_widths(
    headers: list[str], rows: list[list[str]], available: float
) -> list[float]:
    """Largura de cada coluna proporcional ao conteúdo, somando ``available``.

    Sem esse cálculo a tabela assumia a largura natural do conteúdo e
    ultrapassava a área útil do A4 (ex.: 538pt para 451pt disponíveis nos
    relatórios de 5 colunas), cortando as últimas colunas na margem direita.
    """
    weights: list[float] = []
    for index, header in enumerate(headers):
        widest = stringWidth(str(header), "Helvetica-Bold", REPORT_FONT_SIZE)
        for row in rows:
            cell = row[index] if index < len(row) else ""
            widest = max(widest, stringWidth(str(cell), "Helvetica", REPORT_FONT_SIZE))
        weights.append(max(widest + 8, MIN_COLUMN_WIDTH))

    total = sum(weights) or 1.0
    return [weight / total * available for weight in weights]


def _footer_canvas(company: str, emitted_at: str):
    """Rodapé com empresa/data da emissão e número da página.

    Relatórios com muitas linhas geram várias páginas; sem o número fica
    impossível remontar o documento impresso.
    """

    def draw(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED_COLOR)
        canvas.drawString(
            doc.leftMargin, 10 * mm, f"{company} · emitido em {emitted_at}"
        )
        canvas.drawRightString(
            doc.pagesize[0] - doc.rightMargin, 10 * mm, f"Página {doc.page}"
        )
        canvas.restoreState()

    return draw


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
        author=settings.company_name,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()

    story: list = [
        Paragraph(title, styles["Title"]),
        Spacer(1, 2 * mm),
        Paragraph(subtitle, styles["Normal"]),
        Spacer(1, 6 * mm),
    ]

    if rows:
        # Células como Paragraph: nomes longos quebram em várias linhas em vez
        # de empurrar a tabela para fora da página.
        body: list[list] = [
            [Paragraph(escape_xml(str(cell)), _CELL_STYLE) for cell in row]
            for row in rows
        ]
        empty_table = False
    else:
        body = [
            [Paragraph(NO_ROWS_TEXT, _CELL_STYLE)] + [""] * (len(headers) - 1)
        ]
        empty_table = True

    table_data = [
        [Paragraph(escape_xml(str(headers_col)), _HEADER_STYLE) for headers_col in headers]
    ] + body
    table = Table(
        table_data,
        colWidths=_column_widths(headers, rows, doc.width),
        repeatRows=1,
    )
    table_style = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), REPORT_FONT_SIZE),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_ROW_COLOR]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if empty_table:
        table_style.append(("SPAN", (0, 1), (-1, 1)))
    table.setStyle(TableStyle(table_style))
    story.append(table)

    if footers:
        story.append(Spacer(1, 6 * mm))
        for line in footers:
            story.append(Paragraph(f"<b>{escape_xml(line)}</b>", styles["Normal"]))

    footer = _footer_canvas(settings.company_name, date.today().strftime("%d/%m/%Y"))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()

