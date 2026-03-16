"""Configuration API router for managing integrations, anonymization, and general settings."""

import json
import httpx
import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict

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
    # Filter out internal config entries (not real integrations)
    internal = {"anonymization", "agent", "general"}
    return [_serialize_config(row) for row in rows if row.get("system_name") not in internal]


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

    # Hot-reload connectors so changes take effect immediately
    try:
        from ..main import reload_connectors
        await reload_connectors(db)
        logger.info("connectors_hot_reloaded", trigger=name)
    except Exception as e:
        logger.error("connectors_hot_reload_failed", error=str(e))

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
    dark_mode: Optional[bool] = None


async def _get_general_extra(db) -> dict:
    """Get general extra_config from DB, seeding defaults if absent."""
    row = await db.get_system_config("general")
    if row and row.get("extra_config"):
        raw = row["extra_config"]
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(raw, dict):
            return raw
    defaults = {"dark_mode": False}
    await db.upsert_system_config(
        "general",
        display_name="General Settings",
        system_type="internal",
        connector_type="none",
        extra_config=json.dumps(defaults),
    )
    return defaults


@router.get("/general")
async def get_general_settings():
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")
    config = await db.get_system_config("kosin")
    polling = config.get("polling_interval_sec", 60) if config else 60
    extra = await _get_general_extra(db)
    return {"polling_interval_sec": polling, "dark_mode": extra.get("dark_mode", False)}


@router.put("/general")
async def update_general_settings(body: GeneralSettings):
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")
    if body.polling_interval_sec is not None:
        configs = await db.get_all_system_configs()
        for cfg in configs:
            if cfg.get("system_name") and cfg["system_name"] != "general":
                await db.upsert_system_config(
                    cfg["system_name"],
                    polling_interval_sec=body.polling_interval_sec
                )
    if body.dark_mode is not None:
        extra = await _get_general_extra(db)
        extra["dark_mode"] = body.dark_mode
        await db.upsert_system_config("general", extra_config=json.dumps(extra))
    result = {"status": "ok"}
    if body.polling_interval_sec is not None:
        result["polling_interval_sec"] = body.polling_interval_sec
    if body.dark_mode is not None:
        result["dark_mode"] = body.dark_mode
    return result


# --- Agent config endpoints ---

_ALL_TOOLS_META = [
    {"name": "read_ticket", "description": "Consulta ticket completo del sistema origen"},
    {"name": "read_attachment", "description": "Lee adjunto de ticket (PDF, img, docs)"},
    {"name": "update_ticket", "description": "Comenta/cambia estado en ticket"},
    {"name": "create_ticket", "description": "Crea ticket nuevo en sistema destino"},
    {"name": "search_tickets", "description": "Busca tickets con consulta JQL"},
    {"name": "add_worklog", "description": "Imputa horas de trabajo en un ticket"},
    {"name": "get_worklogs", "description": "Consulta horas imputadas en un ticket"},
    {"name": "delete_worklog", "description": "Elimina imputacion de horas"},
    {"name": "execute_action", "description": "Ejecuta accion tecnica controlada"},
]


async def _get_agent_config(db) -> dict:
    """Get agent config from DB, seeding defaults if absent."""
    from ..config import settings as s
    row = await db.get_system_config("agent")
    if row and row.get("extra_config"):
        raw = row["extra_config"]
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(raw, dict):
            return raw
    defaults = {
        "provider": s.llm_provider,
        "model": s.ollama_model if s.llm_provider == "ollama" else (s.openai_model if s.llm_provider == "openai" else s.axet_model),
        "temperature": 0.3,
        "tools": {t["name"]: True for t in _ALL_TOOLS_META},
    }
    await db.upsert_system_config(
        "agent",
        display_name="Agent Config",
        system_type="internal",
        connector_type="none",
        extra_config=json.dumps(defaults),
    )
    return defaults


@router.get("/agent")
async def get_agent_config():
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")

    from ..config import settings as s
    config = await _get_agent_config(db)
    state = _get_app_state()

    tool_states = config.get("tools", {})
    tools_list = [
        {**t, "enabled": tool_states.get(t["name"], True)}
        for t in _ALL_TOOLS_META
    ]

    result = {
        "provider": config.get("provider", s.llm_provider),
        "model": config.get("model", s.ollama_model),
        "temperature": config.get("temperature", 0.3),
        "system_prompt": state.get("system_prompt", ""),
        "available_providers": ["ollama", "openai", "axet"],
        "tools": tools_list,
        "ollama_config": {
            "base_url": s.ollama_base_url,
            "available_models": [],
        },
        "openai_config": {
            "api_key_masked": _mask_token(s.openai_api_key),
            "model": s.openai_model,
            "available_models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        },
        "axet_config": {
            "token_masked": _mask_token(s.axet_bearer_token),
            "asset_id": config.get("axet_asset_id", s.axet_asset_id),
            "project_id": config.get("axet_project_id", s.axet_project_id),
            "model": config.get("model", s.axet_model) if config.get("provider") == "axet" else s.axet_model,
        },
    }

    # Fetch available Ollama models
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{s.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                result["ollama_config"]["available_models"] = [
                    m.get("name", m.get("model", "")) for m in data.get("models", [])
                ]
    except Exception:
        pass

    return result


class AgentConfigUpdate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None
    axet_project_id: Optional[str] = None
    axet_asset_id: Optional[str] = None


@router.put("/agent")
async def update_agent_config(body: AgentConfigUpdate):
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")

    state = _get_app_state()
    config = await _get_agent_config(db)

    if body.provider is not None:
        config["provider"] = body.provider
    if body.model is not None:
        config["model"] = body.model
    if body.temperature is not None:
        config["temperature"] = max(0.0, min(1.0, body.temperature))
    if body.axet_project_id is not None:
        config["axet_project_id"] = body.axet_project_id
        from ..config import settings as s
        s.axet_project_id = body.axet_project_id
    if body.axet_asset_id is not None:
        config["axet_asset_id"] = body.axet_asset_id
        from ..config import settings as s
        s.axet_asset_id = body.axet_asset_id

    await db.upsert_system_config("agent", extra_config=json.dumps(config))

    # Hot-reload system prompt
    if body.system_prompt is not None:
        state["system_prompt"] = body.system_prompt
        logger.info("system_prompt_hot_reloaded", length=len(body.system_prompt))

    # Hot-reload LLM if provider or model changed
    if body.provider is not None or body.model is not None or body.temperature is not None:
        agent = state.get("agent")
        if agent:
            try:
                agent.update_llm(
                    provider=config["provider"],
                    model=config["model"],
                    temperature=config.get("temperature", 0.3),
                )
            except Exception as e:
                logger.error("agent_llm_hot_reload_failed", error=str(e))
                return {**config, "warning": f"Config guardada pero fallo al recargar LLM: {str(e)}"}

    return config


class AgentToolsUpdate(BaseModel):
    tools: Dict[str, bool]


@router.put("/agent/tools")
async def update_agent_tools(body: AgentToolsUpdate):
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")

    state = _get_app_state()
    config = await _get_agent_config(db)
    config["tools"] = {**config.get("tools", {}), **body.tools}

    await db.upsert_system_config("agent", extra_config=json.dumps(config))

    # Hot-reload tools on agent
    agent = state.get("agent")
    if agent:
        agent.set_active_tools(config["tools"])

    return {"tools": config["tools"]}


@router.get("/agent/default-prompt")
async def get_default_prompt():
    from ..services.agent import DEFAULT_SYSTEM_PROMPT
    return {"system_prompt": DEFAULT_SYSTEM_PROMPT}


class TestConnectionRequest(BaseModel):
    provider: str
    model: Optional[str] = None
    api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    axet_bearer_token: Optional[str] = None
    axet_asset_id: Optional[str] = None
    axet_project_id: Optional[str] = None


@router.post("/agent/test-connection")
async def test_agent_connection(body: TestConnectionRequest):
    """Test LLM connection with given provider config."""
    from ..services.agent import AnonymizationAgent
    from ..config import settings as s

    try:
        kwargs = {}
        model = body.model

        if body.provider == "openai":
            kwargs["openai_api_key"] = body.api_key or s.openai_api_key
            model = model or s.openai_model
        elif body.provider == "axet":
            kwargs["axet_bearer_token"] = body.axet_bearer_token or s.axet_bearer_token
            kwargs["axet_asset_id"] = body.axet_asset_id or s.axet_asset_id
            kwargs["axet_project_id"] = body.axet_project_id or s.axet_project_id
            model = model or s.axet_model
        elif body.provider == "ollama":
            kwargs["ollama_base_url"] = body.ollama_base_url or s.ollama_base_url
            model = model or s.ollama_model

        llm = AnonymizationAgent._create_llm(
            provider=body.provider,
            model=model,
            temperature=0.1,
            **kwargs,
        )

        # Send a simple test message
        from langchain_core.messages import HumanMessage
        response = await llm.ainvoke([HumanMessage(content="Responde solo: OK")])
        content = response.content if hasattr(response, "content") else str(response)

        return {"success": True, "message": f"Conexion exitosa con {body.provider}/{model}", "response": content[:100]}
    except Exception as e:
        logger.error("test_connection_failed", provider=body.provider, model=model, error=repr(e))
        return {"success": False, "message": f"Error de conexion: {str(e)}"}


class UpdateApiKeyRequest(BaseModel):
    provider: str
    api_key: str


@router.put("/agent/api-key")
async def update_agent_api_key(body: UpdateApiKeyRequest):
    """Update API key for a provider (runtime only, does not persist to .env)."""
    from ..config import settings as s

    if body.provider == "openai":
        s.openai_api_key = body.api_key
    elif body.provider == "axet":
        s.axet_bearer_token = body.api_key
    else:
        raise HTTPException(status_code=400, detail=f"Provider '{body.provider}' no soporta API key")

    return {"success": True, "message": f"API key actualizada para {body.provider}"}


# --- Anonymization settings endpoints ---

# Default anonymization config (seeded on first GET if not in DB)
_DEFAULT_ANON_CONFIG = {
    "detector_type": "composite",
    "sensitivity": 65,
    "pii_rules": {
        "names": True,
        "emails": True,
        "phones": True,
        "ips": True,
        "cards": True,
        "addresses": False,
        "dni": True,
        "license_plates": False,
    },
    "substitution_technique": "synthetic",
}


async def _get_anon_config(db) -> dict:
    """Get anonymization config from system_config table, seeding defaults if absent."""
    row = await db.get_system_config("anonymization")
    if row and row.get("extra_config"):
        raw = row["extra_config"]
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(raw, dict):
            return raw
    # Seed defaults
    await db.upsert_system_config(
        "anonymization",
        display_name="Anonymization Settings",
        system_type="internal",
        connector_type="none",
        extra_config=json.dumps(_DEFAULT_ANON_CONFIG),
    )
    return dict(_DEFAULT_ANON_CONFIG)


@router.get("/anonymization")
async def get_anonymization_settings():
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")

    config = await _get_anon_config(db)

    # Report which detector is actually active
    state = _get_app_state()
    detector = state.get("detector")
    active_detector = "unknown"
    if detector:
        cls_name = type(detector).__name__
        if "Composite" in cls_name:
            active_detector = "composite"
        elif "Presidio" in cls_name:
            active_detector = "presidio"
        elif "Regex" in cls_name:
            active_detector = "regex"

    # Check if presidio is available
    presidio_available = False
    try:
        from ..services.detection import PresidioDetector  # noqa: F401
        import importlib
        presidio_available = importlib.util.find_spec("presidio_analyzer") is not None
    except Exception:
        pass

    return {
        **config,
        "active_detector": active_detector,
        "presidio_available": presidio_available,
    }


class AnonymizationUpdate(BaseModel):
    detector_type: Optional[str] = None  # "regex", "presidio", "composite"
    sensitivity: Optional[int] = None  # 0-100
    pii_rules: Optional[Dict[str, bool]] = None
    substitution_technique: Optional[str] = None  # "redacted", "synthetic", "aes256"


@router.put("/anonymization")
async def update_anonymization_settings(body: AnonymizationUpdate):
    db = _get_app_state().get("db")
    if not db:
        raise HTTPException(status_code=503, detail="Database not ready")

    config = await _get_anon_config(db)

    if body.detector_type is not None:
        if body.detector_type not in ("regex", "presidio", "composite"):
            raise HTTPException(status_code=400, detail="detector_type must be 'regex', 'presidio', or 'composite'")
        config["detector_type"] = body.detector_type

    if body.sensitivity is not None:
        config["sensitivity"] = max(0, min(100, body.sensitivity))

    if body.pii_rules is not None:
        config["pii_rules"] = {**config.get("pii_rules", {}), **body.pii_rules}

    if body.substitution_technique is not None:
        config["substitution_technique"] = body.substitution_technique

    # Persist
    await db.upsert_system_config(
        "anonymization",
        extra_config=json.dumps(config),
    )

    # Hot-reload detector if changed
    if body.detector_type is not None:
        try:
            state = _get_app_state()
            new_detector = _create_detector(body.detector_type)
            state["detector"] = new_detector
            # Recreate anonymizer with new detector
            from ..services.anonymizer import Anonymizer
            state["anonymizer"] = Anonymizer(detector=new_detector)
            logger.info("detector_hot_reloaded", type=body.detector_type)
        except Exception as e:
            logger.error("detector_hot_reload_failed", error=str(e))
            return {**config, "warning": f"Config guardada pero fallo al cambiar detector: {str(e)}"}

    return config


def _create_detector(detector_type: str):
    """Create a new detector instance by type."""
    if detector_type == "regex":
        from ..services.detection import RegexDetector
        return RegexDetector()
    elif detector_type == "presidio":
        from ..services.detection import PresidioDetector
        return PresidioDetector()
    else:  # composite
        from ..services.detection import CompositeDetector
        return CompositeDetector()
