from uuid import uuid4

from fastapi.testclient import TestClient

from services.api_gateway.app.auth.two_factor import generate_totp_code
from services.api_gateway.app.main import app


def test_auth_protects_project_routes_and_refreshes_session() -> None:
    client = TestClient(app)

    assert client.get("/api/v1/projects").status_code == 401

    email = f"founder-{uuid4()}@massar.local"
    password = "MassarDemo123!"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Founder Demo", "password": password},
    )
    assert registered.status_code == 200
    assert registered.json()["email"] == email

    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == email

    projects = client.get("/api/v1/projects", headers=headers)
    assert projects.status_code == 200
    assert len(projects.json()) >= 1

    refreshed = client.post("/api/v1/auth/refresh", json={})
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]


def test_two_factor_login_flow() -> None:
    client = TestClient(app)
    email = f"two-factor-{uuid4()}@massar.local"
    password = "MassarDemo123!"

    assert client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Two Factor Founder", "password": password},
    ).status_code == 200
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    setup = client.post("/api/v1/auth/2fa/setup", headers=headers)
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    code = generate_totp_code(secret)

    confirmed = client.post("/api/v1/auth/2fa/confirm", headers=headers, json={"code": code})
    assert confirmed.status_code == 200
    assert confirmed.json()["two_factor_enabled"] is True

    second_login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert second_login.status_code == 200
    assert second_login.json()["requires_2fa"] is True

    verified = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "temporary_login_token": second_login.json()["temporary_login_token"],
            "code": generate_totp_code(secret),
        },
    )
    assert verified.status_code == 200
    assert verified.json()["access_token"]
