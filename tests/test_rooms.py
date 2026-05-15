"""Tests for room management endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_room(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post("/api/v1/rooms", json={
        "name": "General",
        "description": "General discussion",
        "room_type": "public",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "General"
    assert data["room_type"] == "public"
    assert data["member_count"] == 1  # creator is auto-added


async def test_create_room_unauthenticated(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/rooms", json={"name": "Test"})
    assert resp.status_code == 401


async def test_list_rooms(client: AsyncClient, auth_headers: dict) -> None:
    # Create a room first
    await client.post("/api/v1/rooms", json={"name": "Listed Room"}, headers=auth_headers)

    resp = await client.get("/api/v1/rooms", headers=auth_headers)
    assert resp.status_code == 200
    rooms = resp.json()
    assert isinstance(rooms, list)
    assert len(rooms) >= 1


async def test_my_rooms(client: AsyncClient, auth_headers: dict) -> None:
    await client.post("/api/v1/rooms", json={"name": "My Room"}, headers=auth_headers)

    resp = await client.get("/api/v1/rooms/me", headers=auth_headers)
    assert resp.status_code == 200
    rooms = resp.json()
    assert any(r["name"] == "My Room" for r in rooms)


async def test_get_room_detail(client: AsyncClient, auth_headers: dict) -> None:
    create_resp = await client.post("/api/v1/rooms", json={"name": "Detail Room"}, headers=auth_headers)
    room_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/rooms/{room_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == room_id
    assert "members" in data


async def test_join_and_leave_room(client: AsyncClient, auth_headers: dict, client_second_user=None) -> None:
    # Create a room with the main user
    create_resp = await client.post("/api/v1/rooms", json={"name": "Join Test Room"}, headers=auth_headers)
    room_id = create_resp.json()["id"]

    # Register a second user
    await client.post("/api/v1/auth/register", json={
        "username": "seconduser",
        "email": "second@example.com",
        "password": "password123",
    })
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "seconduser", "password": "password123"},
    )
    second_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # Second user joins
    join_resp = await client.post(f"/api/v1/rooms/{room_id}/join", headers=second_headers)
    assert join_resp.status_code == 200
    assert join_resp.json()["member_count"] == 2

    # Second user tries to join again → conflict
    rejoin_resp = await client.post(f"/api/v1/rooms/{room_id}/join", headers=second_headers)
    assert rejoin_resp.status_code == 409

    # Second user leaves
    leave_resp = await client.post(f"/api/v1/rooms/{room_id}/leave", headers=second_headers)
    assert leave_resp.status_code == 204


async def test_get_nonexistent_room(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.get(
        "/api/v1/rooms/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404
