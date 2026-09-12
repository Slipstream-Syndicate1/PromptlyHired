from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, update

from app.config import settings
from app.deps import CurrentUser, DbSession
from app.models import PasswordResetToken, RefreshToken, User
from app.rate_limit import (
    forgot_password_rate_limit,
    login_rate_limit,
    refresh_rate_limit,
    reset_password_rate_limit,
    signup_rate_limit,
)
from app.schemas import (
    ForgotPasswordRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPair,
    UserCreate,
    UserLogin,
    UserOut,
)
from app.security import (
    create_access_token,
    generate_password_reset_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.services import email as email_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Hashing a throwaway value on a failed login keeps response time roughly
# constant whether or not the email exists, so timing cannot enumerate users.
_DUMMY_HASH = hash_password("not-a-real-password")


def _issue_tokens(db, user: User) -> TokenPair:
    raw_refresh, token_hash, expires_at = generate_refresh_token()
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.commit()
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=raw_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/signup",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(signup_rate_limit)],
)
def signup(payload: UserCreate, db: DbSession) -> TokenPair:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    user = User(email=email, password_hash=hash_password(payload.password), name=payload.name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(db, user)


@router.post("/login", response_model=TokenPair, dependencies=[Depends(login_rate_limit)])
def login(payload: UserLogin, db: DbSession) -> TokenPair:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None:
        verify_password(payload.password, _DUMMY_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password."
        )
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password."
        )
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenPair, dependencies=[Depends(refresh_rate_limit)])
def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    """Rotate the refresh token - the presented one is revoked on use."""
    token = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(payload.refresh_token)
        )
    )
    now = datetime.now(timezone.utc)
    if token is None or token.revoked or token.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token."
        )

    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token."
        )

    token.revoked = True
    return _issue_tokens(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: DbSession) -> None:
    token = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(payload.refresh_token)
        )
    )
    if token is not None:
        token.revoked = True
        db.commit()


# --- Forgot password ---------------------------------------------------------

INVALID_RESET_DETAIL = "This reset link is invalid or has expired. Request a new one."


def _send_reset_email(to: str, link: str) -> None:
    minutes = settings.password_reset_expire_minutes
    text_body = (
        "Someone asked to reset the password for your PromptlyHired account.\n\n"
        f"Choose a new password here. The link works once and expires in {minutes} minutes:\n"
        f"{link}\n\n"
        "If this was not you, ignore this email. Your password stays the same."
    )
    email_service.send_email(to, "Reset your PromptlyHired password", text_body)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(forgot_password_rate_limit)],
)
def forgot_password(
    payload: ForgotPasswordRequest, background: BackgroundTasks, db: DbSession
) -> dict[str, str]:
    """Send a reset link if the account exists.

    The answer is identical either way, so it cannot reveal which emails are
    registered. The email goes out after the response, so response time does
    not reveal it either.
    """
    minutes = settings.password_reset_expire_minutes
    detail = (
        "If an account exists for that email, a reset link is on its way. "
        f"It expires in {minutes} minutes."
    )
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None:
        return {"detail": detail}

    now = datetime.now(timezone.utc)
    # Only the newest link works.
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw, token_hash, expires_at = generate_password_reset_token()
    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.commit()

    link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={raw}"
    background.add_task(_send_reset_email, user.email, link)
    return {"detail": detail}


@router.post(
    "/reset-password",
    response_model=TokenPair,
    dependencies=[Depends(reset_password_rate_limit)],
)
def reset_password(payload: ResetPasswordRequest, db: DbSession) -> TokenPair:
    """Set a new password from a reset link, sign out every session, and sign in."""
    now = datetime.now(timezone.utc)
    token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_refresh_token(payload.token)
        )
    )
    if token is None or token.used_at is not None or token.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_DETAIL)

    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_RESET_DETAIL)

    user.password_hash = hash_password(payload.password)
    token.used_at = now
    # Every existing session ends, including any held by whoever knew the old password.
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    return _issue_tokens(db, user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
