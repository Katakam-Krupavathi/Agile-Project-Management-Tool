import json
import logging
from typing import Protocol

logger = logging.getLogger("app.services.mailer")


class Mailer(Protocol):
    def send(self, *, to_email: str, subject: str, body: str) -> None: ...


def mask_email(email: str) -> str:
    local, sep, domain = email.strip().partition("@")
    if not sep or not domain:
        return "***"
    masked_local = "*" if len(local) <= 1 else f"{local[0]}***"
    return f"{masked_local}@{domain}"


class ConsoleMailer:
    def send(self, *, to_email: str, subject: str, body: str) -> None:
        _ = body
        logger.info(
            json.dumps(
                {
                    "event": "email.sent",
                    "to": mask_email(to_email),
                    "subject": subject,
                }
            )
        )


_mailer: Mailer = ConsoleMailer()


def get_mailer() -> Mailer:
    return _mailer


def set_mailer(mailer: Mailer) -> None:
    global _mailer
    _mailer = mailer
