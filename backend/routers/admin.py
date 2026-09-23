"""Rotas de gestão de dados restritas a administradores.

Todas as rotas exigem o papel ``admin`` (dependência ``require_admin``):

- POST /admin/database/reset   — zera as tabelas de dados (users preservado)
- GET  /admin/database/export  — baixa um JSON consolidado dos dados
- POST /admin/database/import  — reinsere dados a partir do JSON exportado
- GET  /admin/users            — lista todos os usuários
- DELETE /admin/users/{user_id} — exclui um usuário comum
"""
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from middleware.auth_middleware import require_admin
from models.user import User
from scheduler import ReminderJobBusy, run_due_charges
from schemas.admin import (
    DeleteUserRequest,
    ExportPayload,
    ImportResult,
    ResetRequest,
    ResetResult,
    UserDeleteResult,
    UserListItem,
)
from services import admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])


class ReminderRunRequest(BaseModel):
    user_id: int | None = Field(default=None, gt=0)
    dry_run: bool = Field(default=True, strict=True)
    confirm: bool = Field(default=False, strict=True)


@router.post("/reminders/run")
def run_reminders(
    data: ReminderRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Prévia por padrão. Envio real exige confirmação; pode atingir todos os responsáveis."""
    if not data.dry_run and not data.confirm:
        raise HTTPException(status_code=400, detail="Envio real exige confirm=true.")
    if data.user_id is not None and db.get(User, data.user_id) is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    # Persistir intenção ANTES do efeito externo (push não pode sofrer rollback).
    from uuid import uuid4

    run_id = uuid4().hex
    admin_service.log_action(db, current_user.id, "reminder_run_requested", json.dumps({
        "run_id": run_id, **data.model_dump(),
    }))
    db.commit()
    try:
        result = run_due_charges(user_id=data.user_id, dry_run=data.dry_run,
                                 source="manual", run_id=run_id)
    except ReminderJobBusy as exc:
        raise HTTPException(status_code=409, detail="Verificação já em andamento.") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Falha na verificação. Consulte os logs: {run_id}") from exc
    admin_service.log_action(db, current_user.id, "reminder_run_completed", json.dumps(result))
    db.commit()
    return result


# Tabelas de dados apagadas no reset (usuários são preservados).
DATA_TABLES = ["sale_items", "payments", "push_subscriptions", "sales", "clients"]


@router.post("/database/reset", response_model=ResetResult)
def reset_database(
    data: ResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Zera os dados do ambiente. Exige ``confirm: true`` no corpo.

    A ação é controlada pela flag ``ALLOW_DATABASE_RESET`` (opt-out, ligada
    por padrão). Anteriormente o reset era bloqueado em produção, o que
    impedia o administrador de zerar os dados no ambiente de uso real.
    """
    if not settings.allow_database_reset:
        raise HTTPException(
            status_code=403,
            detail="Reset desabilitado. Defina ALLOW_DATABASE_RESET=true para liberar.",
        )
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
    admin_service.log_action(db, current_user.id, "database_export", "Exportação JSON v1")
    db.commit()
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
        raw = file.file.read(10 * 1024 * 1024 + 1)
        if len(raw) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Arquivo excede o limite de 10 MiB.")
        payload = ExportPayload.model_validate_json(raw)
    except HTTPException:
        raise
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

    try:
        return admin_service.import_data(db, payload, mode=mode, user_id=current_user.id)
    except (IntegrityError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflito de dados ou referência inválida. Nenhum registro foi importado.") from exc


# ---------------------------------------------------------------------------
# Gestão de usuários
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserListItem])
def list_users_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Lista todos os usuários do sistema (somente administradores)."""
    return admin_service.list_users(db)


@router.delete(
    "/users/{user_id}",
    response_model=UserDeleteResult,
    responses={status.HTTP_400_BAD_REQUEST: {"model": None}, status.HTTP_404_NOT_FOUND: {"model": None}},
)
def delete_user_endpoint(
    user_id: int,
    data: DeleteUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Exclui um usuário comum e seus dados associados.

    Exige ``confirm: true`` no corpo para evitar deleção acidental.
    O próprio admin não pode se excluir, e admins não podem excluir outros
    admins.
    """
    try:
        return admin_service.delete_user(db, user_id, current_user.id, data.confirm)
    except ValueError as exc:
        if "não encontrado" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc