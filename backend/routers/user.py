from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserAIConfig
from schemas import UserLogin, UserCreate, UserUpdate, PasswordChange, RefreshRequest, AIConfigUpdate
from auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    get_current_user,
    _decode_token,
)

router = APIRouter(prefix="/user", tags=["user"])


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _ok(data=None, message: str = "成功") -> dict:
    return {"code": 200, "message": message, "data": data}


def _fail(message: str, code: int = 400) -> dict:
    return {"code": code, "message": message, "data": None}


def _user_info(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
    }


# ------------------------------------------------------------------ #
# Endpoints                                                            #
# ------------------------------------------------------------------ #

@router.post("/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.hashed_password):
        return _fail("用户名或密码错误")
    token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return _ok({"token": token, "refresh_token": refresh_token, "userInfo": _user_info(user)}, "登录成功")


@router.post("/register")
def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username).first():
        return _fail("用户名已存在")
    if db.query(User).filter(User.email == data.email).first():
        return _fail("邮箱已被注册")
    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _ok(_user_info(user), "注册成功")


@router.get("/info")
def get_info(current_user: User = Depends(get_current_user)):
    return _ok(_user_info(current_user))


@router.put("/update")
def update_user(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.email is not None:
        if (
            db.query(User)
            .filter(User.email == data.email, User.id != current_user.id)
            .first()
        ):
            return _fail("邮箱已被其他账号使用")
        current_user.email = data.email
    db.commit()
    db.refresh(current_user)
    return _ok(_user_info(current_user), "更新成功")


@router.put("/password")
def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.old_password, current_user.hashed_password):
        return _fail("旧密码不正确")
    current_user.hashed_password = get_password_hash(data.new_password)
    db.commit()
    return _ok(None, "密码修改成功")


@router.post("/refresh")
def refresh_token(data: RefreshRequest, db: Session = Depends(get_db)):
    user_id = _decode_token(data.refresh_token, expected_type="refresh")
    if user_id is None:
        return _fail("无效的 refresh token", 401)

    user = db.get(User, user_id)
    if not user or not user.is_active:
        return _fail("用户不存在或已禁用", 401)

    token = create_access_token({"sub": str(user.id)})
    new_refresh_token = create_refresh_token({"sub": str(user.id)})
    return _ok({"token": token, "refresh_token": new_refresh_token}, "Token 已刷新")


@router.get("/ai-config")
def get_ai_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cfg = db.query(UserAIConfig).filter(UserAIConfig.user_id == current_user.id).first()
    if not cfg:
        from config import settings
        return _ok({
            "model": settings.ANTHROPIC_MODEL,
            "base_url": "",
            "has_api_key": bool(settings.ANTHROPIC_API_KEY),
        })
    return _ok({
        "model": cfg.model,
        "base_url": cfg.base_url or "",
        "has_api_key": bool(cfg.api_key),
    })


@router.put("/ai-config")
def update_ai_config(
    data: AIConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cfg = db.query(UserAIConfig).filter(UserAIConfig.user_id == current_user.id).first()
    if cfg:
        cfg.model = data.model
        cfg.base_url = data.base_url or None
        if data.api_key:  # only update key if a new one is provided
            cfg.api_key = data.api_key
    else:
        cfg = UserAIConfig(
            user_id=current_user.id,
            model=data.model,
            base_url=data.base_url or None,
            api_key=data.api_key or None,
        )
        db.add(cfg)
    db.commit()
    return _ok({
        "model": cfg.model,
        "base_url": cfg.base_url or "",
        "has_api_key": bool(cfg.api_key),
    }, "AI 配置已保存")
