from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import resolve_data_owner
from services import queue_service
from services.sale_service import get_sale

router = APIRouter(prefix="/queue", tags=["Queue"])


def _assert_owns_job(db: Session, job: dict, owner_id: int | None) -> None:
    """Garante que o job de PDF pertence a uma venda do dono do escopo."""
    sale = get_sale(db, job["sale_id"], owner_id=owner_id)
    if sale is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado ou expirado"
        )


@router.post("/pdf/{sale_id}", status_code=status.HTTP_202_ACCEPTED)
def enqueue_sale_pdf(
    sale_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    """Enfileira a geração do PDF de recibo de uma venda do escopo."""
    if get_sale(db, sale_id, owner_id=owner_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Venda não encontrada"
        )
    try:
        job_id = queue_service.enqueue_pdf_job(sale_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    background_tasks.add_task(queue_service.process_pdf_job, job_id)
    return {"job_id": job_id, "status": "pending"}


@router.get("/pdf/{job_id}")
def get_pdf_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    result = queue_service.get_job_status(job_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado ou expirado"
        )
    _assert_owns_job(db, result, owner_id)
    return result


@router.get("/pdf/{job_id}/download")
def download_pdf(
    job_id: str,
    db: Session = Depends(get_db),
    owner_id: int | None = Depends(resolve_data_owner),
):
    job = queue_service.get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado ou expirado"
        )
    _assert_owns_job(db, job, owner_id)
    if job["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao gerar PDF: {job['error']}",
        )
    if job["status"] != "done":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="PDF ainda não está pronto, tente novamente em instantes",
        )

    pdf_bytes = queue_service.get_pdf_bytes(job_id)
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PDF expirado"
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="recibo_venda_{job["sale_id"]}.pdf"'},
    )