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
    password: str = Field(min_length=6, max_length=72)   
    role: str = "STUDENT"
    display_name: str = ""

class LoginReq(BaseModel): email: EmailStr; password: str
class RefreshReq(BaseModel): refresh_token: str

def public(u: User) -> dict:
    return {"id": u.id, "email": u.email, "role": u.role, "display_name": u.display_name or u.email}

def tokens(u: User) -> dict:
    return {"access_token": create_token(u.id, u.role), "refresh_token": create_token(u.id, u.role, kind="refresh"),
            "token_type": "bearer", "user": public(u)}

def _by_email(db, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email.strip().lower())).scalar_one_or_none()

@router.post("/register", status_code=201)
def register(req: RegisterReq, db=Depends(get_db), caller: dict | None = Depends(optional_user)):
    if req.role not in ROLES:
        raise HTTPException(422, f"unknown role {req.role}")
    if req.role != "STUDENT" and (caller is None or caller["role"] != "SUPER_ADMIN"):
        raise HTTPException(403, "only a SUPER_ADMIN can create non-student accounts")
    if _by_email(db, req.email):
        raise HTTPException(409, "email already registered")
    u = User(id=str(uuid.uuid4()), email=req.email.strip().lower(), password_hash=hash_password(req.password),
             role=req.role, display_name=req.display_name.strip())
    db.add(u)
    db.commit()
    return public(u)

@router.post("/login")
def login(req: LoginReq, db=Depends(get_db)):
    u = _by_email(db, req.email)
    if not u or not verify_password(req.password, u.password_hash):
        raise HTTPException(401, "invalid email or password")
    return tokens(u)

@router.post("/refresh")
def refresh(req: RefreshReq, db=Depends(get_db)):
    try:
        claims = decode_token(req.refresh_token, kind="refresh")
    except TokenError:
        raise HTTPException(401, "invalid refresh token")
    u = db.get(User, claims["sub"])  
    if not u:
        raise HTTPException(401, "account no longer exists")
    return tokens(u)

@router.get("/me")
def me(user: dict = Depends(current_user), db=Depends(get_db)):
    u = db.get(User, user["sub"])
    if not u:
        raise HTTPException(401, "account no longer exists")
    return public(u)
