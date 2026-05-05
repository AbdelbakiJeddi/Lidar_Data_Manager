from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.api.dependencies import get_current_user, require_admin


def build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)

    @app.get("/lidar/datasets")
    def list_datasets(_: dict = Depends(get_current_user)) -> dict:
        return {"ok": True}

    @app.post("/lidar/upload")
    def upload_dataset(_: dict = Depends(require_admin)) -> dict:
        return {"ok": True}

    return app


def get_token(client: TestClient, username: str, password: str) -> str:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_missing_token_is_401() -> None:
    client = TestClient(build_test_app())
    response = client.get("/lidar/datasets")
    assert response.status_code == 401


def test_user_cannot_upload() -> None:
    client = TestClient(build_test_app())
    token = get_token(client, "user", "user123")
    response = client.post("/lidar/upload", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_can_upload() -> None:
    client = TestClient(build_test_app())
    token = get_token(client, "admin", "admin123")
    response = client.post("/lidar/upload", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
