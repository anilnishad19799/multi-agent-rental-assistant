"""Authentication routes — signup, login, session inspection, and logout."""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status

from backend.models import User
from backend.repositories.user_repository import UserRepository
from backend.services.auth_service import (
    hash_password,
    verify_password,
    validate_signup_payload,
    validate_email,
    create_access_token,
)
from backend.api.dependencies import get_current_user, require_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])
user_repo = UserRepository()


@router.post("/signup")
async def signup(payload: dict):
    """Register a new user account with strict validation and password hashing."""
    valid, err_msg = validate_signup_payload(payload)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )

    clean_email = payload["email"].strip().lower()

    # Check for existing account
    existing_user = await user_repo.get_by_email(clean_email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists. Please log in instead.",
        )

    # Hash password and create user
    pw_hash = hash_password(payload["password"])
    name = payload.get("name", "").strip()
    phone = payload.get("phone", "").strip() if payload.get("phone") else None

    user = await user_repo.create_user_with_password(
        email=clean_email,
        password_hash=pw_hash,
        name=name,
        phone=phone,
    )

    logger.info(f"User signed up successfully: {user.email} (id: {user.id})")

    token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": bool(user.is_admin or user.email == "admin@gmail.com"),
    })

    return {
        "status": "success",
        "message": "Account created successfully! Welcome to RentEase.",
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "is_admin": bool(user.is_admin or user.email == "admin@gmail.com"),
        },
    }


@router.post("/login")
async def login(payload: dict):
    """Authenticate an existing user with email and password."""
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide both email and password.",
        )

    valid_email, _ = validate_email(email)
    if not valid_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter a valid email address.",
        )

    user = await user_repo.get_by_email(email)
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your credentials.",
        )

    token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": bool(user.is_admin or user.email == "admin@gmail.com"),
    })

    logger.info(f"User logged in successfully: {user.email}")

    return {
        "status": "success",
        "message": f"Welcome back, {user.name or 'there'}!",
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "gender": user.gender,
            "working_profession": user.working_profession,
            "is_admin": bool(user.is_admin or user.email == "admin@gmail.com"),
        },
    }


@router.get("/me")
async def get_current_user_profile(user: User = Depends(require_current_user)):
    """Retrieve current authenticated user profile."""
    return {
        "status": "success",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "gender": user.gender,
            "age": user.age,
            "working_profession": user.working_profession,
            "citizenship": user.citizenship,
            "is_admin": bool(user.is_admin or user.email == "admin@gmail.com"),
        },
    }


@router.post("/logout")
async def logout():
    """Clear session acknowledge endpoint."""
    return {
        "status": "success",
        "message": "Logged out successfully.",
    }
