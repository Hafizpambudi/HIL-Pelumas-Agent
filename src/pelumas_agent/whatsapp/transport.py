from dataclasses import dataclass, field

import httpx

from pelumas_agent.config import Settings


class Transport:
    def send(self, to_phone: str, text: str) -> None:
        raise NotImplementedError


@dataclass
class MockTransport(Transport):
    sent: list[tuple[str, str]] = field(default_factory=list)
    templates: list[dict] = field(default_factory=list)

    def send(self, to_phone: str, text: str) -> None:
        self.sent.append((to_phone, text))

    def send_template(self, to_phone: str, template_name: str, components: list[dict]) -> None:
        self.templates.append(
            {"to": to_phone, "template": template_name, "components": components}
        )

    def to(self, phone: str) -> list[str]:
        return [text for to, text in self.sent if to == phone]


class WhatsAppCloudTransport(Transport):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.url = (
            f"https://graph.facebook.com/v20.0/{settings.wa_phone_number_id}/messages"
        )

    def send(self, to_phone: str, text: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        response = httpx.post(
            self.url,
            json=payload,
            headers={
                "Authorization": f"Bearer {self.settings.wa_access_token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()

    def send_template(self, to_phone: str, template_name: str, components: list[dict]) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "id"},
                "components": components,
            },
        }
        response = httpx.post(
            self.url,
            json=payload,
            headers={
                "Authorization": f"Bearer {self.settings.wa_access_token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
