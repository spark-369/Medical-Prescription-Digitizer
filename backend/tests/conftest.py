"""Hermetic pytest fixtures.

* Database: file-backed SQLite via aiosqlite (API) and sqlite3 (Celery tasks).
* Redis: fakeredis for both async (API) and sync (worker) clients.
* Celery: eager mode so tasks run inline during tests.
* Ollama: ``run_inference`` is monkeypatched with a deterministic extraction.

Environment variables are set *before* the app package is imported so the
cached settings object picks them up.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from fakeredis import FakeRedis
from fakeredis.aioredis import FakeRedis as AsyncFakeRedis
from httpx import ASGITransport, AsyncClient

_TMP_DIR = tempfile.mkdtemp(prefix="mpd-tests-")
_TMP_DB_DIR = tempfile.mkdtemp(prefix="mpd-tests-db-")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP_DB_DIR}/test.db")
os.environ.setdefault("DATABASE_URL_SYNC", f"sqlite:///{_TMP_DB_DIR}/test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("UPLOAD_DIR", _TMP_DIR)
os.environ.setdefault("CREATE_ALL_TABLES", "false")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_TIMEOUT_SECONDS", "5")

from app.db.base import Base  # noqa: E402
from app.db.session import AsyncSessionLocal, async_engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import Role  # noqa: E402
from app.schemas.prescription import PrescriptionOut  # noqa: E402
from app.services.inference import (  # noqa: E402
    MedicationExtraction,
    PrescriptionExtraction,
)

FAKE_EXTRACTION = PrescriptionExtraction(
    patient_name="John Doe",
    patient_age=42,
    doctor_name="Dr. Sarah Smith",
    prescribed_date="2026-01-15",
    medications=[
        MedicationExtraction(
            name="Amoxicillin",
            dosage="500 mg",
            frequency="3 times daily",
            duration="7 days",
            instructions="Take after meals",
        ),
        MedicationExtraction(
            name="Ibuprofen",
            dosage="200 mg",
            frequency="as needed",
            duration="5 days",
            instructions=None,
        ),
    ],
    notes="Return if symptoms persist.",
    confidence=0.93,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * (16 * 1024)  # ~16 KB, above the minimum


@pytest.fixture(autouse=True)
async def _database(monkeypatch):
    """Fresh schema per test + async fakeredis backing the API."""
    fake_redis = AsyncFakeRedis(decode_responses=True)
    monkeypatch.setattr("app.core.redis.get_redis", lambda: fake_redis)
    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def _celery_eager(monkeypatch):
    from app.workers.celery_app import celery_app

    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=False,
        task_store_eager_result=True,
    )
    sync_fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.workers.tasks.get_sync_redis", lambda: sync_fake)
    yield sync_fake
    # Dispose the worker sync engine so it does not hold the sqlite file lock.
    from app.db.session import reset_sync_session_factory

    reset_sync_session_factory()


@pytest.fixture(autouse=True)
def _fake_inference(monkeypatch):
    monkeypatch.setattr(
        "app.workers.tasks.run_inference", lambda image_b64: FAKE_EXTRACTION
    )


@pytest.fixture
async def client():
    async def override_get_db():
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()


async def register(client: AsyncClient, **overrides) -> dict:
    payload = {
        "email": "doctor@example.com",
        "password": "supersecret123",
        "full_name": "Dr. Test",
        **overrides,
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def login(client: AsyncClient, email: str = "doctor@example.com",
                password: str = "supersecret123") -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def upload_prescription(
    client: AsyncClient, token: str, filename: str = "rx.png"
) -> PrescriptionOut:
    response = await client.post(
        "/api/v1/prescriptions",
        files={"file": (filename, PNG_BYTES, "image/png")},
        headers=bearer(token),
    )
    assert response.status_code == 201, response.text
    return PrescriptionOut.model_validate(response.json())


_ = Role  # imported for readability of role assertions in tests
