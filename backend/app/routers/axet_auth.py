"""Axet OAuth2 Device Authorization flow via OKTA corporate SSO.

Uses Device Code grant (no redirect_uri needed) following the same pattern
as the official Axet OpenCode plugin (axet.ts).
"""

import asyncio
import base64
import json
import time
from typing import Optional

import httpx
import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/axet/auth", tags=["axet-auth"])

def _axet_base_url() -> str:
    return settings.axet_base_url.rstrip("/")
OKTA_SCOPES = ["openid", "profile", "email", "offline_access"]
TOKEN_EXPIRY_BUFFER_S = 30

# In-memory token store (single-user POC)
_token_store: dict = {
    "access_token": None,
    "refresh_token": None,
    "expires_at": 0,
    "user_info": None,
}

# Device flow state (transient, per auth attempt)
_device_state: dict = {
    "device_code": None,
    "interval": 5,
    "expires_at": 0,
    "polling": False,
}


def _build_token_endpoint() -> str:
    return f"{settings.axet_okta_domain}/oauth2/{settings.axet_okta_auth_server_id}/v1/token"


def _build_device_endpoint() -> str:
    return f"{settings.axet_okta_domain}/oauth2/{settings.axet_okta_auth_server_id}/v1/device/authorize"


def _decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without verification (just to extract okta_id)."""
    try:
        payload_b64 = token.split(".")[1]
        # Add padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return {}


def get_active_token() -> Optional[str]:
    """Get the current valid access token, or None if expired/missing."""
    if not _token_store["access_token"]:
        return None
    if time.time() >= _token_store["expires_at"] - TOKEN_EXPIRY_BUFFER_S:
        return None
    return _token_store["access_token"]


def get_token_or_setting() -> str:
    """Get OAuth token if available, otherwise fall back to .env setting."""
    token = get_active_token()
    if token:
        return token
    return settings.axet_bearer_token


# --- Endpoints ---

@router.post("/start")
async def start_device_login():
    """Start OKTA Device Authorization flow. Returns user_code and verification URL."""
    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            resp = await client.post(
                _build_device_endpoint(),
                data={
                    "client_id": settings.axet_okta_client_id,
                    "scope": " ".join(OKTA_SCOPES),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code != 200:
            logger.error("device_auth_failed", status=resp.status_code, detail=resp.text[:300])
            raise HTTPException(status_code=502, detail=f"OKTA device authorization failed: {resp.text[:300]}")

        data = resp.json()

        # Store device flow state
        _device_state["device_code"] = data["device_code"]
        _device_state["interval"] = data.get("interval", 5)
        _device_state["expires_at"] = time.time() + data.get("expires_in", 600)
        _device_state["polling"] = False

        return {
            "user_code": data["user_code"],
            "verification_uri": data["verification_uri"],
            "verification_uri_complete": data["verification_uri_complete"],
            "expires_in": data.get("expires_in", 600),
        }

    except httpx.HTTPError as e:
        logger.error("device_auth_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"Network error: {str(e)}")


@router.post("/poll")
async def poll_for_token():
    """Poll OKTA token endpoint for device code completion.

    The frontend calls this repeatedly until the user completes login in the browser.
    Returns: {status: "pending"|"success"|"expired", ...}
    """
    device_code = _device_state.get("device_code")
    if not device_code:
        raise HTTPException(status_code=400, detail="No pending device authorization. Call /start first.")

    if time.time() >= _device_state.get("expires_at", 0):
        _device_state["device_code"] = None
        return {"status": "expired", "message": "Device code expirado. Inicia el login de nuevo."}

    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            resp = await client.post(
                _build_token_endpoint(),
                data={
                    "client_id": settings.axet_okta_client_id,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        data = resp.json()

        # Success — user completed login
        if resp.status_code == 200 and "access_token" in data:
            _token_store["access_token"] = data["access_token"]
            _token_store["refresh_token"] = data.get("refresh_token")
            _token_store["expires_at"] = time.time() + data.get("expires_in", 3600)

            # Update settings in-memory
            settings.axet_bearer_token = data["access_token"]

            # Fetch Axet user info
            user_info = await _fetch_axet_user(data["access_token"])
            _token_store["user_info"] = user_info

            # Clear device state
            _device_state["device_code"] = None

            logger.info("axet_device_login_success", user=user_info.get("displayName", "unknown"))

            # Revive the resolution agent if it failed to init at startup
            # because the Axet token wasn't present yet. Logging in via OKTA
            # should be enough to make it ready without extra manual steps.
            try:
                from ..main import app_state
                if app_state.get("agent") is None and app_state.get("db"):
                    from ..services.agent import AnonymizationAgent
                    agent = AnonymizationAgent(
                        anonymizer=app_state["anonymizer"],
                        db=app_state["db"],
                        ws_manager=app_state["ws_manager"],
                        anon_llm=app_state.get("anon_llm"),
                    )
                    app_state["agent"] = agent
                    logger.info("agent_revived_after_okta_login", provider="axet")
            except Exception as rev_e:
                logger.warning("agent_revive_after_login_failed", error=str(rev_e))

            return {
                "status": "success",
                "user": user_info,
                "expires_in": data.get("expires_in", 3600),
            }

        # Still waiting for user
        error = data.get("error", "")
        if error == "authorization_pending":
            return {"status": "pending", "message": "Esperando autenticacion en el navegador..."}

        if error == "slow_down":
            _device_state["interval"] = _device_state.get("interval", 5) + 2
            return {"status": "pending", "message": "Esperando... (slow_down)"}

        if error == "expired_token":
            _device_state["device_code"] = None
            return {"status": "expired", "message": "Device code expirado. Inicia el login de nuevo."}

        # Other error
        logger.error("device_poll_error", error=error, description=data.get("error_description"))
        return {"status": "error", "message": data.get("error_description", error)}

    except httpx.HTTPError as e:
        logger.error("device_poll_network_error", error=str(e))
        return {"status": "error", "message": f"Error de red: {str(e)}"}


@router.post("/refresh")
async def refresh_token():
    """Refresh the access token using the stored refresh token."""
    refresh_tk = _token_store.get("refresh_token")
    if not refresh_tk:
        raise HTTPException(status_code=401, detail="No refresh token available. Please login again.")

    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            resp = await client.post(
                _build_token_endpoint(),
                data={
                    "client_id": settings.axet_okta_client_id,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_tk,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code != 200:
            logger.error("okta_refresh_failed", status=resp.status_code, detail=resp.text[:300])
            _token_store["access_token"] = None
            _token_store["refresh_token"] = None
            _token_store["expires_at"] = 0
            raise HTTPException(status_code=401, detail="Refresh token expirado. Inicia sesion de nuevo.")

        token_data = resp.json()
        _token_store["access_token"] = token_data["access_token"]
        _token_store["expires_at"] = time.time() + token_data.get("expires_in", 3600)
        if "refresh_token" in token_data:
            _token_store["refresh_token"] = token_data["refresh_token"]

        settings.axet_bearer_token = token_data["access_token"]

        # Same revive-agent hook as login: if the agent is None (startup
        # failed because no token), now that we have one, build it.
        try:
            from ..main import app_state
            if app_state.get("agent") is None and app_state.get("db"):
                from ..services.agent import AnonymizationAgent
                agent = AnonymizationAgent(
                    anonymizer=app_state["anonymizer"],
                    db=app_state["db"],
                    ws_manager=app_state["ws_manager"],
                    anon_llm=app_state.get("anon_llm"),
                )
                app_state["agent"] = agent
                logger.info("agent_revived_after_token_refresh", provider="axet")
        except Exception as rev_e:
            logger.warning("agent_revive_after_refresh_failed", error=str(rev_e))

        logger.info("axet_token_refreshed", expires_in=token_data.get("expires_in"))
        return {"success": True, "expires_in": token_data.get("expires_in", 3600)}

    except httpx.HTTPError as e:
        logger.error("okta_refresh_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"Network error during refresh: {str(e)}")


@router.get("/status")
async def auth_status():
    """Check current Axet OAuth authentication status."""
    token = get_active_token()
    if token:
        remaining = int(_token_store["expires_at"] - time.time())
        return {
            "authenticated": True,
            "user": _token_store.get("user_info"),
            "expires_in": remaining,
            "has_refresh_token": bool(_token_store.get("refresh_token")),
        }

    if _token_store.get("refresh_token"):
        return {
            "authenticated": False,
            "expired": True,
            "has_refresh_token": True,
            "message": "Token expirado, se puede renovar automaticamente",
        }

    return {"authenticated": False, "expired": False, "has_refresh_token": False}


@router.post("/logout")
async def logout():
    """Clear stored tokens."""
    _token_store["access_token"] = None
    _token_store["refresh_token"] = None
    _token_store["expires_at"] = 0
    _token_store["user_info"] = None
    _device_state["device_code"] = None
    settings.axet_bearer_token = ""
    logger.info("axet_oauth_logout")
    return {"success": True}


@router.get("/models")
async def list_axet_models():
    """Fetch available models from Axet enabler-manager API."""
    token = get_active_token()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            resp = await client.post(
                f"{_axet_base_url()}/api/enabler-manager/v1/llm-models/search",
                json={
                    "search": {"modelType": "chat", "isPublic": True},
                    "pagination": {"size": 50, "page": 0},
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )

        if resp.status_code != 200:
            return {"models": [], "error": f"HTTP {resp.status_code}"}

        data = resp.json()
        models = [
            {
                "id": m.get("model", m.get("id")),
                "displayName": m.get("displayName", m.get("model", "")),
                "provider": m.get("provider", {}).get("slug", "openai"),
            }
            for m in data.get("data", [])
        ]
        return {"models": models}

    except Exception as e:
        logger.warning("axet_models_fetch_failed", error=str(e))
        return {"models": [], "error": str(e)}


@router.get("/projects")
async def list_axet_projects():
    """Fetch available projects from Axet for the current user."""
    token = get_active_token()
    user_info = _token_store.get("user_info")
    if not token or not user_info:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user_info.get("id", "")
    user_projects = user_info.get("projects", [])
    if not user_projects:
        return {"projects": []}

    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            resp = await client.post(
                f"{_axet_base_url()}/api/core/v1/projects/search",
                json={
                    "search": {"ids": user_projects},
                    "pagination": {"size": 50, "page": 0},
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "axet-user-id": user_id,
                    "axet-asset-id": settings.axet_asset_id,
                },
            )

        if resp.status_code != 200:
            return {"projects": [], "error": f"HTTP {resp.status_code}"}

        data = resp.json()
        projects = [
            {"id": p.get("id"), "displayName": p.get("displayName", "")}
            for p in data.get("data", [])
        ]
        return {"projects": projects}

    except Exception as e:
        logger.warning("axet_projects_fetch_failed", error=str(e))
        return {"projects": [], "error": str(e)}


async def _fetch_axet_user(access_token: str) -> dict:
    """Fetch user info from Axet Core API using okta_id from JWT."""
    jwt_payload = _decode_jwt_payload(access_token)
    okta_id = jwt_payload.get("okta_id") or jwt_payload.get("sub", "")

    if not okta_id:
        # Fallback to OKTA userinfo
        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                resp = await client.get(
                    f"{settings.axet_okta_domain}/oauth2/{settings.axet_okta_auth_server_id}/v1/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {}

    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            resp = await client.get(
                f"{_axet_base_url()}/api/core/v1/users/{okta_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning("axet_user_fetch_failed", error=str(e))

    return {"okta_id": okta_id}


async def ensure_valid_token() -> Optional[str]:
    """Get a valid token, auto-refreshing if needed. Used by agent.py."""
    token = get_active_token()
    if token:
        return token

    if _token_store.get("refresh_token"):
        try:
            await refresh_token()
            return get_active_token()
        except Exception as e:
            logger.error("auto_refresh_failed", error=str(e))

    return settings.axet_bearer_token or None


# --- Background auto-renewal task ---

_refresh_task: Optional[asyncio.Task] = None


async def _auto_refresh_loop():
    """Background loop that refreshes the token before it expires."""
    while True:
        try:
            if _token_store.get("access_token") and _token_store.get("refresh_token"):
                remaining = _token_store["expires_at"] - time.time()
                # Refresh when less than 2 minutes remain
                if 0 < remaining < 120:
                    logger.info("auto_refresh_triggered", remaining_s=int(remaining))
                    await refresh_token()
                elif remaining <= 0:
                    # Already expired, try refresh
                    logger.info("auto_refresh_expired_token")
                    await refresh_token()
        except Exception as e:
            logger.warning("auto_refresh_loop_error", error=str(e))
        await asyncio.sleep(30)


def start_auto_refresh():
    """Start the background auto-refresh task."""
    global _refresh_task
    if _refresh_task is None or _refresh_task.done():
        _refresh_task = asyncio.create_task(_auto_refresh_loop())
        logger.info("axet_auto_refresh_started")


def stop_auto_refresh():
    """Stop the background auto-refresh task."""
    global _refresh_task
    if _refresh_task and not _refresh_task.done():
        _refresh_task.cancel()
        _refresh_task = None
        logger.info("axet_auto_refresh_stopped")
