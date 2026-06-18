"""
services/orchestrator.py — LLM-driven tracking/order-status orchestration.

One "advance" step:
  1. Load current tracking state.
  2. Decide the next stage. The LLM is asked to confirm/choose the next
     checkpoint given the route + elapsed progress; a deterministic fallback
     (the fixed STAGE_ORDER) is used if the LLM is unavailable or returns
     something invalid — so tracking always makes forward progress.
  3. Append the checkpoint, update ETA/status, persist.
  4. Write the order-status transition to the Django backend and notify the
     delivery service.
"""
import json
import logging
from datetime import datetime

from app.core import backend_client, delivery_client, state_store
from app.core.config import settings
from app.schemas.tracking import STATUS_TO_ORDER_STATUS
from app.services import tracking_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a shipment tracking orchestrator. Given the current tracking stage "
    "and the remaining route, decide the single next stage of the shipment. "
    "Stages, in order, are: pending → dispatched → in_transit → "
    "out_for_delivery → delivered. You may only advance to the immediate next "
    "stage or stay on the current one; never skip or go backwards. Respond with "
    "ONLY a JSON object: {\"next_status\": \"<stage>\", \"note\": \"<short note>\"}."
)


def _llm_next_stage(state: dict, fallback: str) -> tuple[str, str | None]:
    """Ask the LLM for the next stage; fall back to the deterministic next stage.

    Returns (next_status, note). Never raises — any failure yields the fallback.
    """
    try:
        from app.core.llm import get_llm_client
        client = get_llm_client()
    except Exception as exc:  # noqa: BLE001 — no key/SDK -> deterministic fallback
        logger.info("Orchestrator using deterministic fallback (no LLM): %s", exc)
        return fallback, None

    user = (
        f"Current stage: {state['status']}.\n"
        f"Destination: {state.get('destination')}.\n"
        f"Distance: {state.get('distance_km')} km, "
        f"approx duration: {state.get('duration_hours')} h.\n"
        f"Checkpoints so far: {[c['status'] for c in state.get('checkpoints', [])]}.\n"
        f"The deterministic next stage is '{fallback}'. Confirm it or keep the "
        f"current stage if it's too early."
    )

    try:
        resp = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        content = (resp.choices[0].message.content or "").strip()
        # Tolerate fenced/wrapped JSON.
        start, end = content.find("{"), content.rfind("}")
        data = json.loads(content[start:end + 1]) if start != -1 else {}
        nxt = data.get("next_status")
        note = data.get("note")
        valid = {"pending", "dispatched", "in_transit", "out_for_delivery", "delivered"}
        if nxt in valid:
            return nxt, note
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM orchestration failed, using fallback: %s", exc)

    return fallback, None


def advance(order_id: str, access_token: str | None = None) -> dict:
    """Advance tracking one step for an order. Returns a result dict."""
    state = state_store.load_state(order_id)
    if not state:
        return {"order_id": order_id, "advanced": False, "status": "unknown",
                "message": "No tracking state — start tracking first."}

    current = state["status"]
    if current == "delivered":
        return {"order_id": order_id, "advanced": False, "status": "delivered",
                "message": "Already delivered."}

    deterministic_next = tracking_service.next_stage(current)
    if deterministic_next is None:
        return {"order_id": order_id, "advanced": False, "status": current,
                "message": "No further stages."}

    chosen, note = _llm_next_stage(state, deterministic_next)

    # If the LLM chose to stay put, treat as no-op this tick.
    if chosen == current:
        return {"order_id": order_id, "advanced": False, "status": current,
                "message": "Holding at current stage."}

    route = tracking_service.get_route_for_state(state)
    now = datetime.utcnow()
    checkpoint = tracking_service.build_checkpoint(chosen, route, now)
    if note:
        checkpoint["description"] = note

    # Mark previous checkpoints not-current, append the new one.
    for c in state["checkpoints"]:
        c["is_current"] = False
    state["checkpoints"].append(checkpoint)
    state["status"] = chosen
    state["order_status"] = STATUS_TO_ORDER_STATUS[chosen]
    state["updated_at"] = now.isoformat()
    state_store.save_state(order_id, state)

    # Persist the order-status transition + notify delivery (best-effort).
    backend_client.update_order_status(order_id, state["order_status"], access_token)
    delivery_client.notify_checkpoint(order_id, checkpoint, access_token)

    logger.info("Advanced order %s: %s → %s", order_id, current, chosen)
    return {"order_id": order_id, "advanced": True, "status": chosen,
            "message": f"Advanced to {chosen}."}
