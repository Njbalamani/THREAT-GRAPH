from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    identity = form.username.strip().lower()
    user = db.scalar(select(User).where(or_(User.email == identity, User.username == identity)))
    if not user or not verify_password(form.password, user.hashed_password) or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": user.id, "role": user.role.value, "email": user.email})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserOut:
    existing = db.scalar(select(User).where(or_(User.email == payload.email, User.username == payload.username)))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or username already exists")
    user = User(
        email=payload.email.lower(),
        username=payload.username.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[UserOut]:
    users = list(db.scalars(select(User).order_by(User.created_at)).all())
    return [UserOut.model_validate(user) for user in users]
