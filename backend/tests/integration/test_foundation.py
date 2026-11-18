"""
Integration tests: health endpoint and sessions CRUD.
"""
import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_create_session(client):
    response = await client.post("/api/sessions/", json={"title": "Test Session", "type": "technical"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Test Session"
    assert body["type"] == "technical"
    assert body["status"] == "created"
    assert "id" in body


@pytest.mark.asyncio
async def test_list_sessions(client):
    # Create sessions with different types and statuses
    await client.post("/api/sessions/", json={"title": "Session A", "type": "hr"})
    b = await client.post("/api/sessions/", json={"title": "Session B", "type": "behavioral"})
    b_id = b.json()["id"]
    await client.patch(f"/api/sessions/{b_id}", json={"status": "active"})

    # List all
    response = await client.get("/api/sessions/")
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) >= 2

    # Filter by type
    hr_resp = await client.get("/api/sessions/?type=hr")
    assert hr_resp.status_code == 200
    assert all(s["type"] == "hr" for s in hr_resp.json())

    # Filter by status
    act_resp = await client.get("/api/sessions/?status=active")
    assert act_resp.status_code == 200
    assert all(s["status"] == "active" for s in act_resp.json())


@pytest.mark.asyncio
async def test_session_lifecycle_and_cascade_delete(client):
    # 1. Create session
    c_resp = await client.post("/api/sessions/", json={"title": "Lifecycle Test", "type": "technical"})
    s_id = c_resp.json()["id"]
    assert c_resp.json()["status"] == "created"

    # 2. Transition created -> active
    a_resp = await client.patch(f"/api/sessions/{s_id}", json={"status": "active"})
    assert a_resp.json()["status"] == "active"

    # 3. Transition active -> paused
    p_resp = await client.patch(f"/api/sessions/{s_id}", json={"status": "paused"})
    assert p_resp.json()["status"] == "paused"

    # 4. Transition paused -> active
    r_resp = await client.patch(f"/api/sessions/{s_id}", json={"status": "active"})
    assert r_resp.json()["status"] == "active"

    # 5. Transition active -> ended
    e_resp = await client.patch(f"/api/sessions/{s_id}", json={"status": "ended"})
    assert e_resp.json()["status"] == "ended"
    assert e_resp.json()["duration_seconds"] is not None
    assert e_resp.json()["duration_seconds"] >= 0

    # 6. Check transcript endpoint
    t_resp = await client.get(f"/api/sessions/{s_id}/transcript")
    assert t_resp.status_code == 200
    assert isinstance(t_resp.json(), list)

    # 7. Check questions endpoint
    q_resp = await client.get(f"/api/sessions/{s_id}/questions")
    assert q_resp.status_code == 200
    assert isinstance(q_resp.json(), list)

    # 8. Delete and verify 404
    d_resp = await client.delete(f"/api/sessions/{s_id}")
    assert d_resp.status_code == 204
    assert (await client.get(f"/api/sessions/{s_id}")).status_code == 404


@pytest.mark.asyncio
async def test_get_session(client):
    create_resp = await client.post("/api/sessions/", json={"title": "Get Test", "type": "general"})
    session_id = create_resp.json()["id"]

    response = await client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    assert response.json()["id"] == session_id


@pytest.mark.asyncio
async def test_get_session_not_found(client):
    response = await client.get("/api/sessions/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_session_status(client):
    create_resp = await client.post("/api/sessions/", json={"title": "Update Test", "type": "general"})
    session_id = create_resp.json()["id"]

    response = await client.patch(f"/api/sessions/{session_id}", json={"status": "active"})
    assert response.status_code == 200
    assert response.json()["status"] == "active"


@pytest.mark.asyncio
async def test_end_session_sets_timestamps(client):
    create_resp = await client.post("/api/sessions/", json={"title": "End Test", "type": "general"})
    session_id = create_resp.json()["id"]

    response = await client.patch(f"/api/sessions/{session_id}", json={"status": "ended"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ended"
    assert body["ended_at"] is not None
    assert body["duration_seconds"] is not None
    assert body["duration_seconds"] >= 0


@pytest.mark.asyncio
async def test_delete_session(client):
    create_resp = await client.post("/api/sessions/", json={"title": "Delete Test", "type": "general"})
    session_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/sessions/{session_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/sessions/{session_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_settings_get_creates_defaults(client):
    response = await client.get("/api/settings/")
    assert response.status_code == 200
    body = response.json()
    assert body["stt_provider"] == "whisper"
    assert body["llm_provider"] == "gemini"
    assert body["theme"] == "dark"


@pytest.mark.asyncio
async def test_settings_update(client):
    # Create defaults
    await client.get("/api/settings/")

    response = await client.patch("/api/settings/", json={"theme": "light", "default_answer_style": "detailed"})
    assert response.status_code == 200
    body = response.json()
    assert body["theme"] == "light"
    assert body["default_answer_style"] == "detailed"
