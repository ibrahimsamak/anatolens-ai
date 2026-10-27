import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from app.api.deps import get_db, current_user, optional_user
from app.core.security import hash_password, verify_password, create_token, decode_token, TokenError
from app.models.user import User, ROLES

router = APIRouter(prefix="/api/v1/auth")


class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)  # bcrypt ignores anything past 72 bytes
    role: str = "STUDENT"
    display_name: str = ""

class LoginReq(BaseModel): email: EmailStr; password: str
class RefreshReq(BaseModel): refresh_token: str


def user_info(u: User):
    return {"id": u.id, "email": u.email, "role": u.role, "display_name": u.display_name or u.email}


def token_response(u: User):
    return {
        "access_token": create_token(u.id, u.role),
        "refresh_token": create_token(u.id, u.role, kind="refresh"),
        "token_type": "bearer",
        "user": user_info(u),
    }


def find_by_email(db, email: str):
    email = email.strip().lower()
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


@router.post("/register", status_code=201)
def register(req: RegisterReq, db=Depends(get_db), caller=Depends(optional_user)):
    if req.role not in ROLES:
        raise HTTPException(422, f"unknown role {req.role}")
    if req.role != "STUDENT":
        if caller is None or caller["role"] != "SUPER_ADMIN":
            raise HTTPException(403, "only a SUPER_ADMIN can create non-student accounts")
    if find_by_email(db, req.email):
        raise HTTPException(409, "email already registered")

    u = User(
        id=str(uuid.uuid4()),
        email=req.email.strip().lower(),
        password_hash=hash_password(req.password),
        role=req.role,
        display_name=req.display_name.strip(),
    )
    db.add(u)
    db.commit()
    return user_info(u)


@router.post("/login")
def login(req: LoginReq, db=Depends(get_db)):
    u = find_by_email(db, req.email)
    if not u or not verify_password(req.password, u.password_hash):
        raise HTTPException(401, "invalid email or password")
    return token_response(u)


@router.post("/refresh")
def refresh(req: RefreshReq, db=Depends(get_db)):
    try:
        claims = decode_token(req.refresh_token, kind="refresh")
    except TokenError:
        raise HTTPException(401, "invalid refresh token")
    u = db.get(User, claims["sub"])
    if not u:
        raise HTTPException(401, "account no longer exists")
    return token_response(u)


@router.get("/me")
def me(user=Depends(current_user), db=Depends(get_db)):
    u = db.get(User, user["sub"])
    if not u:
        raise HTTPException(401, "account no longer exists")
    return user_info(u)
