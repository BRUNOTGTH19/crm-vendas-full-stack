from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from models.user import User
from services import queue_service

router = APIRouter(prefix="/queue", tags=["Queue"])


@router.post("/pdf/{sale_id}", status_code=status.HTTP_202_ACCEPTED)
def enqueue_sale_pdf(
    sale_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    """Enfileira a geração do PDF de recibo de uma venda."""
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
    current_user: User = Depends(get_current_user_dependency),
):
    result = queue_service.get_job_status(job_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado ou expirado"
        )
    return result


@router.get("/pdf/{job_id}/download")
def download_pdf(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
):
    job = queue_service.get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado ou expirado"
        )
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

