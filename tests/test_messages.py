"""Tests for message persistence and read receipts."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _setup_room(client: AsyncClient, auth_headers: dict) -> str:
    resp = await client.post("/api/v1/rooms", json={"name": "msg-test-room"}, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_get_empty_history(client: AsyncClient, auth_headers: dict) -> None:
    room_id = await _setup_room(client, auth_headers)
    resp = await client.get(f"/api/v1/messages/{room_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


async def test_message_history_unauthorized(client: AsyncClient, auth_headers: dict) -> None:
    room_id = await _setup_room(client, auth_headers)

    # Register a user who is NOT a member
    await client.post("/api/v1/auth/register", json={
        "username": "outsider",
        "email": "outsider@example.com",
        "password": "password123",
    })
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "outsider", "password": "password123"},
    )
    outsider_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp = await client.get(f"/api/v1/messages/{room_id}", headers=outsider_headers)
    assert resp.status_code == 403


async def test_mark_read_non_member(client: AsyncClient, auth_headers: dict) -> None:
    room_id = await _setup_room(client, auth_headers)

    await client.post("/api/v1/auth/register", json={
        "username": "outsider2",
        "email": "outsider2@example.com",
        "password": "password123",
    })
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "outsider2", "password": "password123"},
    )
    outsider_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp = await client.post(
        f"/api/v1/messages/{room_id}/read",
        json={"message_ids": ["00000000-0000-0000-0000-000000000000"]},
        headers=outsider_headers,
    )
    assert resp.status_code == 403


async def test_pagination_params(client: AsyncClient, auth_headers: dict) -> None:
    room_id = await _setup_room(client, auth_headers)

    # page and page_size validation
    resp = await client.get(
        f"/api/v1/messages/{room_id}",
        params={"page": 1, "page_size": 10},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["page_size"] == 10


async def test_notifications_empty(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.get("/api/v1/notifications", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_unread_count(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.get("/api/v1/notifications/unread-count", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["count"] == 0
