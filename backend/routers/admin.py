"""Rotas de gestão de dados restritas a administradores.

Todas as rotas exigem o papel ``admin`` (dependência ``require_admin``):

- POST /admin/database/reset   — zera as tabelas de dados (users preservado)
- GET  /admin/database/export  — baixa um JSON consolidado dos dados
- POST /admin/database/import  — reinsere dados a partir do JSON exportado
"""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from database import get_db
from middleware.auth_middleware import require_admin
from models.user import User
from schemas.admin import ExportPayload, ImportResult, ResetRequest, ResetResult
from services import admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])

# Tabelas de dados apagadas no reset (usuários são preservados).
DATA_TABLES = ["sale_items", "payments", "push_subscriptions", "sales", "clients"]


@router.post("/database/reset", response_model=ResetResult)
def reset_database(
    data: ResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Zera os dados do ambiente. Exige ``confirm: true`` no corpo."""
    if not data.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmação obrigatória: envie {\"confirm\": true} para zerar os dados.",
        )
    cleared = admin_service.reset_data(db, user_id=current_user.id)
    return ResetResult(cleared=cleared, preserved=["users"])


@router.get("/database/export")
def export_database(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Baixa um JSON consolidado com todos os registros das tabelas de dados."""
    content = admin_service.export_to_json(db)
    filename = "crm_vendas_export.json"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/database/import", response_model=ImportResult)
def import_database(
    file: UploadFile = File(...),
    mode: str = Query("skip", pattern="^(skip|overwrite)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Importa dados de um arquivo JSON no formato exportado.

    ``mode=skip`` (padrão) ignora IDs já existentes; ``mode=overwrite``
    atualiza os registros existentes.
    """
    try:
        raw = file.file.read()
        payload = ExportPayload.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Arquivo inválido: {exc.error_count()} erro(s) de validação.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível ler o arquivo: {exc}",
        ) from exc

    return admin_service.import_data(db, payload, mode=mode, user_id=current_user.id)