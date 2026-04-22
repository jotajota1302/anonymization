"""Estimate time spent on a ticket from chat history when the operator doesn't specify it.

Returns a Jira-compatible time_spent string (e.g. "1h 30m", "45m").
"""

import re
from typing import List, Optional, Tuple

import structlog

logger = structlog.get_logger()


_JIRA_TIME_RE = re.compile(
    r"^\s*(?:(\d+)\s*w)?\s*(?:(\d+)\s*d)?\s*(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+)\s*m)?\s*$",
    re.IGNORECASE,
)


def normalize_jira_time(raw: str) -> Optional[str]:
    """Validate and normalize a user-provided time string to Jira format.

    Accepts: "2h 30m", "1.5h", "45m", "2h", "1d 4h". Returns None if invalid.
    """
    if not raw or not raw.strip():
        return None
    m = _JIRA_TIME_RE.match(raw.strip())
    if not m:
        return None
    w, d, h, mm = m.groups()
    if not any([w, d, h, mm]):
        return None

    parts: List[str] = []
    total_minutes = 0
    if w:
        parts.append(f"{int(w)}w")
        total_minutes += int(w) * 5 * 8 * 60
    if d:
        parts.append(f"{int(d)}d")
        total_minutes += int(d) * 8 * 60
    if h:
        hv = float(h)
        if hv.is_integer():
            parts.append(f"{int(hv)}h")
        else:
            # Jira doesn't accept decimals — split to h + m
            whole = int(hv)
            rem_min = int(round((hv - whole) * 60))
            if whole:
                parts.append(f"{whole}h")
            if rem_min:
                parts.append(f"{rem_min}m")
        total_minutes += int(round(hv * 60))
    if mm:
        parts.append(f"{int(mm)}m")
        total_minutes += int(mm)

    if total_minutes <= 0:
        return None
    return " ".join(parts)


def _heuristic_estimate(chat_messages: List[dict]) -> str:
    """Fallback estimate based on message count when LLM is unavailable.

    Rough rule: 2 min of operator thinking per operator message + 3 min per agent reply.
    Minimum 15m, maximum 8h.
    """
    op = sum(1 for m in chat_messages if m.get("role") == "operator")
    ag = sum(1 for m in chat_messages if m.get("role") == "agent")
    minutes = 15 + op * 2 + ag * 3
    minutes = max(15, min(minutes, 8 * 60))
    if minutes >= 60:
        h, rem = divmod(minutes, 60)
        return f"{h}h {rem}m" if rem else f"{h}h"
    return f"{minutes}m"


async def estimate_time_with_llm(chat_messages: List[dict], llm) -> Tuple[str, str]:
    """Ask the LLM to estimate time spent based on the chat history.

    Returns (time_spent, rationale). Falls back to heuristic if LLM fails.
    """
    if not chat_messages:
        return "15m", "Sin historial de chat — valor minimo por defecto"

    # Build a compact transcript
    transcript_lines = []
    for m in chat_messages[-30:]:  # last 30 messages is plenty
        role = "OPERADOR" if m.get("role") == "operator" else "AGENTE"
        content = (m.get("message") or m.get("content") or "").strip()
        # Strip CHIPS blocks from agent messages
        content = re.sub(r"\[CHIPS[:\s].*?\]", "", content, flags=re.DOTALL).strip()
        if content:
            transcript_lines.append(f"[{role}] {content[:400]}")
    transcript = "\n".join(transcript_lines)

    prompt = f"""Eres un estimador de tiempo. Analiza el siguiente historial de chat entre un operador de soporte y su asistente IA para resolver un ticket, y estima el tiempo REAL de trabajo que el operador ha invertido (lectura, analisis, redaccion, validacion).

## Historial:
---
{transcript[:4000]}
---

## Reglas:
1. Estima en minutos u horas. Minimo 15m, maximo 8h.
2. Considera: numero de turnos, complejidad del problema tecnico, profundidad de la investigacion.
3. Un ticket trivial (1-2 turnos, respuesta inmediata) = 15-30m.
4. Un ticket con varias iteraciones y analisis = 1-3h.
5. Un ticket largo con investigacion profunda = 3-8h.

## Formato de respuesta — SOLO un JSON:
{{"time_spent": "Xh Ym", "rationale": "razon breve en una frase"}}

Responde SOLO el JSON, sin texto adicional."""

    try:
        from langchain_core.messages import HumanMessage
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = (response.content or "").strip()

        import json
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            raise ValueError(f"no JSON found in LLM response: {raw[:200]}")
        data = json.loads(json_match.group())
        time_str = normalize_jira_time(str(data.get("time_spent", "")))
        if not time_str:
            raise ValueError(f"invalid time_spent from LLM: {data.get('time_spent')}")
        rationale = str(data.get("rationale", "")).strip() or "Estimado por IA"
        logger.info("llm_time_estimate", time_spent=time_str, rationale=rationale)
        return time_str, rationale
    except Exception as e:
        logger.warning("llm_time_estimate_failed", error=str(e))
        fallback = _heuristic_estimate(chat_messages)
        return fallback, f"Estimado por heuristica (LLM fallo: {type(e).__name__})"
