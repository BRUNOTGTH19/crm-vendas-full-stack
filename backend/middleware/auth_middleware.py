from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models.user import User, UserRole
from services.auth_service import get_current_user

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não informado",
        )
    try:
        return get_current_user(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def require_admin(
    current_user: User = Depends(get_current_user_dependency),
) -> User:
    """Exige que o usuário autenticado tenha papel de administrador.

    Usado nas rotas de gestão de dados (reset/export/import). Levanta 403
    quando o usuário está autenticado, mas não é admin.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return current_user


def resolve_data_owner(
    x_view_user: int | None = Header(default=None, alias="X-View-User"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_dependency),
) -> int | None:
    """Resolve o ESCOPO dos dados que a requisição pode acessar.

    Regras de isolamento:
    - Usuário comum: sempre acessa **apenas** os próprios dados. O header
      ``X-View-User`` é ignorado (não é possível espiar outro usuário).
    - Administrador: por padrão acessa o escopo GLOBAL (``None`` = sem filtro,
      mantendo a visão consolidada do painel). Ao enviar
      ``X-View-User: <id>`` passa a operar no escopo daquele usuário
      específico.

    Retorna o ``user_id`` dono do escopo, ou ``None`` para escopo global.
    """
    if current_user.role == UserRole.admin:
        if x_view_user is None:
            return None
        if db.get(User, x_view_user) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário selecionado não encontrado.",
            )
        return x_view_user
    return current_user.id
