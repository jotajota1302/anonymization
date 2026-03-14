"""Configuration API router for managing integrations and general settings."""

import json
import httpx
import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = structlog.get_logger()

router = APIRouter(prefix="/api/config", tags=["config"])


def _get_app_state():
    from ..main import app_state
    return app_state


def _mask_token(token: str) -> str:
    """Mask a token, showing only the last 4 characters."""
    if not token or len(token) <= 4:
        return "****"
    return "****" + token[-4:]


def _serialize_config(row: dict) -> dict:
    """Convert a DB row to API response, masking the token."""
    data = dict(row)
    data["auth_token_masked"] = _mask_token(data.pop("auth_token", ""))
    data["is_active"] = bool(data.get("is_active", 0))
    data["is_mock"] = bool(data.get("is_mock", 0))
    if isinstance(data.get("extra_config"), str):
        try:
            data["extra_config"] = json.loads(data["extra_config"])
        except (json.JSONDecodeError, TypeError):
            data["extra_config"] = {}
    return data


# --- Integration endpoints ---

@router.get("/integrations")
async def list_integrations():
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")
    rows = await db.get_all_system_configs()
    return [_serialize_config(row) for row in rows]


@router.get("/integrations/{name}")
async def get_integration(name: str):
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")
    row = await db.get_system_config(name)
    if not row:
        raise HTTPException(status_code=404, detail=f"Integration '{name}' not found")
    return _serialize_config(row)


class IntegrationUpdate(BaseModel):
    display_name: Optional[str] = None
    base_url: Optional[str] = None
    auth_token: Optional[str] = None
    auth_email: Optional[str] = None
    project_key: Optional[str] = None
    extra_config: Optional[dict] = None
    is_active: Optional[bool] = None
    is_mock: Optional[bool] = None
    polling_interval_sec: Optional[int] = None


@router.put("/integrations/{name}")
async def update_integration(name: str, body: IntegrationUpdate):
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")

    existing = await db.get_system_config(name)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Integration '{name}' not found")

    fields = {}
    if body.display_name is not None:
        fields["display_name"] = body.display_name
    if body.base_url is not None:
        fields["base_url"] = body.base_url
    if body.auth_token is not None and body.auth_token != "":
        fields["auth_token"] = body.auth_token
    if body.auth_email is not None:
        fields["auth_email"] = body.auth_email
    if body.project_key is not None:
        fields["project_key"] = body.project_key
    if body.extra_config is not None:
        fields["extra_config"] = json.dumps(body.extra_config)
    if body.is_active is not None:
        fields["is_active"] = int(body.is_active)
    if body.is_mock is not None:
        fields["is_mock"] = int(body.is_mock)
    if body.polling_interval_sec is not None:
        fields["polling_interval_sec"] = body.polling_interval_sec

    if fields:
        await db.upsert_system_config(name, **fields)

    updated = await db.get_system_config(name)
    return _serialize_config(updated)


@router.post("/integrations/{name}/test")
async def test_integration(name: str):
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")

    config = await db.get_system_config(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Integration '{name}' not found")

    if config.get("is_mock"):
        await db.update_connection_status(name, "connected")
        return {"status": "connected", "message": "Modo mock: conexion simulada OK", "user": "mock_user"}

    base_url = config.get("base_url", "").rstrip("/")
    token = config.get("auth_token", "")

    if not base_url or not token:
        await db.update_connection_status(name, "error", "URL o token no configurados")
        return {"status": "error", "message": "URL o token no configurados"}

    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(
                f"{base_url}/rest/api/2/myself",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
        if resp.status_code == 200:
            user_data = resp.json()
            display = user_data.get("displayName", user_data.get("name", "unknown"))
            await db.update_connection_status(name, "connected")
            return {"status": "connected", "message": f"Conectado como {display}", "user": display}
        else:
            error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            await db.update_connection_status(name, "error", error_msg)
            return {"status": "error", "message": error_msg}
    except Exception as e:
        error_msg = str(e)[:300]
        await db.update_connection_status(name, "error", error_msg)
        return {"status": "error", "message": error_msg}


# --- General settings endpoints ---

class GeneralSettings(BaseModel):
    polling_interval_sec: Optional[int] = None


@router.get("/general")
async def get_general_settings():
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")
    # Use kosin config as reference for global polling interval
    config = await db.get_system_config("kosin")
    polling = config.get("polling_interval_sec", 60) if config else 60
    return {"polling_interval_sec": polling}


@router.put("/general")
async def update_general_settings(body: GeneralSettings):
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")
    if body.polling_interval_sec is not None:
        # Update polling interval on all systems
        configs = await db.get_all_system_configs()
        for cfg in configs:
            await db.upsert_system_config(
                cfg["system_name"],
                polling_interval_sec=body.polling_interval_sec
            )
    return {"status": "ok", "polling_interval_sec": body.polling_interval_sec}
