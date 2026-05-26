"""Authentication routes - JWT-based auth with team management."""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError
from passlib.context import CryptContext

from backend.config import settings

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Schemas ---
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    team_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    team_id: str
    team_name: str


# --- Helpers ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency to get current authenticated user."""
    return verify_token(credentials.credentials)


# --- Routes ---
@router.post("/signup", response_model=TokenResponse)
async def signup(request: SignupRequest):
    """Create a new account and team."""
    # In production: check if email exists, create user + team in DB
    hashed_password = pwd_context.hash(request.password)
    
    # Simulate user creation
    user_data = {
        "id": "user_new_id",
        "email": request.email,
        "full_name": request.full_name,
        "role": "owner",
        "team_id": "team_new_id",
        "team_name": request.team_name,
    }

    token = create_access_token({
        "sub": user_data["id"],
        "email": user_data["email"],
        "team_id": user_data["team_id"],
        "role": user_data["role"],
    })

    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_data,
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login and get JWT token."""
    # In production: verify credentials against DB
    user_data = {
        "id": "user_id",
        "email": request.email,
        "full_name": "User",
        "role": "owner",
        "team_id": "team_id",
        "team_name": "My Team",
    }

    token = create_access_token({
        "sub": user_data["id"],
        "email": user_data["email"],
        "team_id": user_data["team_id"],
        "role": user_data["role"],
    })

    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_data,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse(
        id=current_user["sub"],
        email=current_user["email"],
        full_name="User",
        role=current_user["role"],
        team_id=current_user["team_id"],
        team_name="Team",
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh access token."""
    new_token = create_access_token({
        "sub": current_user["sub"],
        "email": current_user["email"],
        "team_id": current_user["team_id"],
        "role": current_user["role"],
    })
    return TokenResponse(
        access_token=new_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={"id": current_user["sub"], "email": current_user["email"]},
    )
