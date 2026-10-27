from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    role: Literal["candidate", "recruiter"]

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MFAChallengeResponse(BaseModel):
    mfa_required: Literal[True] = True
    mfa_token: str
    token_type: str = "bearer"


class MFASetupResponse(BaseModel):
    provisioning_uri: str


class MFACodeRequest(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if len(value) != 6 or not value.isdigit():
            raise ValueError("MFA code must contain exactly six digits")
        return value


class MFAVerifyRequest(MFACodeRequest):
    mfa_token: str
