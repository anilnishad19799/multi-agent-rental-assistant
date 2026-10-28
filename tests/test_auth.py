"""Unit and integration tests for authentication and validation."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.auth_service import (
    hash_password,
    verify_password,
    validate_email,
    validate_password,
    validate_signup_payload,
    create_access_token,
    decode_access_token,
)
import uuid


def test_password_hashing():
    pw = "SuperSecure123"
    hashed = hash_password(pw)
    assert ":" in hashed
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False
    assert verify_password("", hashed) is False


def test_email_validation():
    valid, _ = validate_email("user@example.com")
    assert valid is True

    valid, _ = validate_email("john.doe+test@domain.co.in")
    assert valid is True

    valid, err = validate_email("invalid-email")
    assert valid is False
    assert "valid email" in err.lower()

    valid, _ = validate_email("")
    assert valid is False


def test_password_validation():
    # Valid: 6+ chars, letter and number
    valid, _ = validate_password("Pass12")
    assert valid is True

    # Too short
    valid, err = validate_password("P1")
    assert valid is False
    assert "at least 6 characters" in err

    # Letters only
    valid, err = validate_password("OnlyLetters")
    assert valid is False
    assert "letter and one number" in err

    # Digits only
    valid, err = validate_password("1234567")
    assert valid is False
    assert "letter and one number" in err


def test_jwt_token_creation_and_decoding():
    payload = {"sub": "user-123", "email": "test@example.com"}
    token = create_access_token(payload)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-123"
    assert decoded["email"] == "test@example.com"


def test_signup_and_login_flow():
    client = TestClient(app)
    unique_suffix = uuid.uuid4().hex[:6]
    email = f"test_{unique_suffix}@example.com"
    password = "Password123"

    # 1. Invalid signup (missing name)
    res_bad = client.post("/api/auth/signup", json={
        "name": "A",
        "email": email,
        "password": password
    })
    assert res_bad.status_code == 400

    # 2. Valid signup
    res_signup = client.post("/api/auth/signup", json={
        "name": "Jane Doe",
        "email": email,
        "password": password,
        "confirm_password": password,
        "phone": "9876543210"
    })
    assert res_signup.status_code == 200
    data_signup = res_signup.json()
    assert data_signup["status"] == "success"
    assert "token" in data_signup
    token = data_signup["token"]
    user_id = data_signup["user"]["id"]

    # 3. Duplicate signup rejected
    res_dup = client.post("/api/auth/signup", json={
        "name": "Jane Doe",
        "email": email,
        "password": password
    })
    assert res_dup.status_code == 409

    # 4. Failed login
    res_wrong = client.post("/api/auth/login", json={
        "email": email,
        "password": "WrongPassword999"
    })
    assert res_wrong.status_code == 401

    # 5. Successful login
    res_login = client.post("/api/auth/login", json={
        "email": email,
        "password": password
    })
    assert res_login.status_code == 200
    data_login = res_login.json()
    assert data_login["status"] == "success"
    assert data_login["user"]["id"] == user_id

    # 6. Verify /me endpoint
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["user"]["email"] == email

    # 7. Logout endpoint
    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200


def test_chat_requires_authentication():
    from unittest.mock import patch, AsyncMock
    client = TestClient(app)

    # 1. Unauthenticated chat request must fail with 401
    res_unauth = client.post("/api/chat", json={"message": "hello"})
    assert res_unauth.status_code == 401
    assert "Authentication required" in res_unauth.json()["detail"]

    # 2. Authenticated chat request succeeds
    unique_suffix = uuid.uuid4().hex[:6]
    email = f"chat_user_{unique_suffix}@example.com"
    res_signup = client.post("/api/auth/signup", json={
        "name": "Chat Tester",
        "email": email,
        "password": "Password123",
        "confirm_password": "Password123"
    })
    assert res_signup.status_code == 200
    token = res_signup.json()["token"]

    with patch("backend.api.routes.run", new_callable=AsyncMock):
        res_auth = client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Looking for PG in Koramangala"}
        )
        assert res_auth.status_code == 200
        assert "session_id" in res_auth.json()


def test_user_chat_isolation_between_accounts():
    from unittest.mock import patch, AsyncMock
    client = TestClient(app)
    suffix = uuid.uuid4().hex[:6]

    with patch("backend.api.routes.run", new_callable=AsyncMock):
        # 1. Anil signs up and sends a chat message
        anil_email = f"anil_{suffix}@gmail.com"
        res_anil_signup = client.post("/api/auth/signup", json={
            "name": "Anil Kumar",
            "email": anil_email,
            "password": "Password123",
            "confirm_password": "Password123"
        })
        assert res_anil_signup.status_code == 200
        anil_token = res_anil_signup.json()["token"]

        res_anil_chat = client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {anil_token}"},
            json={"message": "Anil wants 2BHK in Indiranagar"}
        )
        assert res_anil_chat.status_code == 200
        anil_session_id = res_anil_chat.json()["session_id"]

        # 2. Raj signs up with another email
        raj_email = f"raj_{suffix}@gmail.com"
        res_raj_signup = client.post("/api/auth/signup", json={
            "name": "Rajesh",
            "email": raj_email,
            "password": "Password123",
            "confirm_password": "Password123"
        })
        assert res_raj_signup.status_code == 200
        raj_token = res_raj_signup.json()["token"]

        # 3. Raj's chat history must be completely empty (no messages from Anil)
        res_raj_history = client.get(
            "/api/chat/history",
            headers={"Authorization": f"Bearer {raj_token}"}
        )
        assert res_raj_history.status_code == 200
        raj_data = res_raj_history.json()
        assert raj_data["messages"] == []
        assert raj_data["session_id"] is None

        # 4. If Raj attempts to use Anil's session_id, the system enforces isolation
        res_raj_chat = client.post(
            "/api/chat",
            headers={"Authorization": f"Bearer {raj_token}"},
            json={"message": "Raj message", "session_id": anil_session_id}
        )
        assert res_raj_chat.status_code == 200
        raj_session_id = res_raj_chat.json()["session_id"]
        # Session IDs must be distinct — no cross-contamination
        assert raj_session_id != anil_session_id

        # 5. Anil's conversation history remains isolated to Anil's session
        res_anil_history = client.get(
            "/api/chat/history",
            headers={"Authorization": f"Bearer {anil_token}"}
        )
        assert res_anil_history.status_code == 200
        assert res_anil_history.json()["session_id"] == anil_session_id
