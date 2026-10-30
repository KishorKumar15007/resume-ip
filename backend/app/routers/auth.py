import hashlib

import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    MFAConfigurationError,
    create_access_token,
    create_mfa_token,
    decrypt_totp_secret,
    encrypt_totp_secret,
    hash_password,
    settings,
    decode_mfa_token,
    verify_password,
)
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    MFAChallengeResponse,
    MFACodeRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    SignupRequest,
    TokenResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    request: SignupRequest,
    db: Session = Depends(get_db),
):
    email = request.email.lower()

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=email,
        password_hash=hash_password(request.password),
        role=request.role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(
        user_id=str(user.id),
        role=user.role,
        mfa_enabled=False,
    )

    return TokenResponse(
        access_token=access_token,
    )


@router.post(
    "/login",
    response_model=TokenResponse | MFAChallengeResponse,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    email = request.email.lower()

    user = db.scalar(
        select(User).where(User.email == email)
    )

    if user is None or not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.mfa_enabled:
        return MFAChallengeResponse(
            mfa_token=create_mfa_token(user_id=str(user.id), role=user.role),
        )

    access_token = create_access_token(
        user_id=str(user.id),
        role=user.role,
        mfa_enabled=False,
    )

    return TokenResponse(
        access_token=access_token,
    )


def _totp(secret: str) -> pyotp.TOTP:
    return pyotp.TOTP(secret, digits=6, interval=30, digest=hashlib.sha1)


def _mfa_configuration_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="MFA is temporarily unavailable",
    )


@router.post("/mfa/setup", response_model=MFASetupResponse)
def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MFASetupResponse:
    user = db.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
    if user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MFA is already enabled")

    secret = pyotp.random_base32()
    try:
        user.totp_secret_encrypted = encrypt_totp_secret(secret)
    except MFAConfigurationError as exc:
        raise _mfa_configuration_error() from exc
    db.commit()

    return MFASetupResponse(
        provisioning_uri=_totp(secret).provisioning_uri(
            name=user.email,
            issuer_name=settings.mfa_issuer,
        )
    )


@router.post("/mfa/confirm", response_model=TokenResponse)
def confirm_mfa(
    request: MFACodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.get(User, current_user.id)
    if user is None or not user.totp_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA setup is required")

    try:
        secret = decrypt_totp_secret(user.totp_secret_encrypted)
    except MFAConfigurationError as exc:
        raise _mfa_configuration_error() from exc
    if not _totp(secret).verify(request.code, valid_window=1):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")

    user.mfa_enabled = True
    db.commit()
    return TokenResponse(
        access_token=create_access_token(
            str(user.id),
            user.role,
            mfa_enabled=True,
        )
    )


@router.post("/mfa/verify", response_model=TokenResponse)
def verify_mfa(request: MFAVerifyRequest, db: Session = Depends(get_db)) -> TokenResponse:
    payload = decode_mfa_token(request.mfa_token)
    user = db.get(User, payload["sub"])
    if user is None or not user.mfa_enabled or not user.totp_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA verification")

    try:
        secret = decrypt_totp_secret(user.totp_secret_encrypted)
    except MFAConfigurationError as exc:
        raise _mfa_configuration_error() from exc
    if not _totp(secret).verify(request.code, valid_window=1):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA verification")

    return TokenResponse(
        access_token=create_access_token(
            str(user.id),
            user.role,
            mfa_enabled=True,
        )
    )
