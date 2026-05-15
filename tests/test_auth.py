"""Tests for authentication endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_register_success(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/register", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "password123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert "hashed_password" not in data
    assert "id" in data


async def test_register_duplicate_username(client: AsyncClient) -> None:
    payload = {"username": "bob", "email": "bob@example.com", "password": "password123"}
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    payload2 = {**payload, "email": "bob2@example.com"}
    r2 = await client.post("/api/v1/auth/register", json=payload2)
    assert r2.status_code == 409


async def test_register_duplicate_email(client: AsyncClient) -> None:
    payload = {"username": "charlie1", "email": "charlie@example.com", "password": "password123"}
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    payload2 = {**payload, "username": "charlie2"}
    r2 = await client.post("/api/v1/auth/register", json=payload2)
    assert r2.status_code == 409


async def test_register_short_password(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/register", json={
        "username": "dave",
        "email": "dave@example.com",
        "password": "short",
    })
    assert resp.status_code == 422


async def test_login_success(client: AsyncClient, registered_user: dict) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "securepassword123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient, registered_user: dict) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


async def test_login_unknown_user(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody", "password": "password"},
    )
    assert resp.status_code == 401


async def test_get_me(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.get("/api/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"


async def test_get_me_no_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_refresh_token(client: AsyncClient, auth_tokens: dict) -> None:
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth_tokens["refresh_token"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Tokens should be rotated (new values)
    assert data["refresh_token"] != auth_tokens["refresh_token"]


async def test_refresh_invalid_token(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not.a.valid.token"},
    )
    assert resp.status_code == 400


async def test_health_check(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
