from datetime import datetime, timedelta, timezone

from pelumas_agent.db.models import Conversation

WINDOW = timedelta(hours=24)


def in_window(conversation: Conversation, now: datetime | None = None) -> bool:
    if conversation.updated_at is None:
        return True
    updated = conversation.updated_at
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    reference = now or datetime.now(timezone.utc)
    return (reference - updated) <= WINDOW
