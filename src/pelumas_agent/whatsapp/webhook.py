import hashlib
import hmac
import json
from datetime import timedelta

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import delete

from pelumas_agent.config import Settings
from pelumas_agent.db.models import ProcessedMessage, utcnow
from pelumas_agent.db.session import session_factory

DEDUPE_RETENTION = timedelta(days=7)


def verify_signature(settings: Settings, body: bytes, header: str | None) -> bool:
    if not settings.wa_app_secret:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.wa_app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def extract_message(payload: dict) -> dict | None:
    try:
        entry = payload.get("entry") or []
        for change in entry[0].get("changes") or []:
            value = change.get("value") or {}
            messages = value.get("messages") or []
            if not messages:
                continue
            message = messages[0]
            if message.get("type") != "text":
                continue
            return {
                "wamid": message.get("id"),
                "from": message.get("from"),
                "text": (message.get("text") or {}).get("body", ""),
                "timestamp": message.get("timestamp"),
            }
    except (IndexError, AttributeError, TypeError):
        return None
    return None


def make_router(orchestrator_factory, settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/webhook")
    def verify(
        hub_mode: str | None = Query(default=None, alias="hub.mode"),
        hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
        hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    ):
        if hub_mode == "subscribe" and hub_verify_token == settings.wa_verify_token:
            return Response(content=hub_challenge or "", media_type="text/plain")
        return Response(status_code=403)

    @router.post("/webhook")
    async def receive(request: Request):
        body = await request.body()
        if not verify_signature(settings, body, request.headers.get("X-Hub-Signature-256")):
            return Response(status_code=403)
        try:
            payload = json.loads(body) if body else {}
        except ValueError:
            return Response(status_code=400)

        message = extract_message(payload)
        if not message or not message.get("wamid"):
            return {"status": "ignored"}

        factory = session_factory()
        session = factory()
        try:
            cutoff = utcnow() - DEDUPE_RETENTION
            session.execute(
                delete(ProcessedMessage).where(ProcessedMessage.processed_at < cutoff)
            )
            if session.get(ProcessedMessage, message["wamid"]):
                return {"status": "duplicate"}
            session.add(ProcessedMessage(wamid=message["wamid"]))
            session.commit()

            orchestrator = orchestrator_factory(session)
            orchestrator.handle_message(
                wa_thread_id=message["from"],
                from_phone=message["from"],
                text=message["text"],
            )
        finally:
            session.close()
        return {"status": "ok"}

    return router
