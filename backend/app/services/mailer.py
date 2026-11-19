import json
import logging
from typing import Protocol

logger = logging.getLogger("app.services.mailer")


class Mailer(Protocol):
    def send(self, *, to_email: str, subject: str, body: str) -> None: ...


class ConsoleMailer:
    def send(self, *, to_email: str, subject: str, body: str) -> None:
        logger.info(
            json.dumps(
                {
                    "event": "email.sent",
                    "to": to_email,
                    "subject": subject,
                    "body": body,
                }
            )
        )


_mailer: Mailer = ConsoleMailer()


def get_mailer() -> Mailer:
    return _mailer


def set_mailer(mailer: Mailer) -> None:
    global _mailer
    _mailer = mailer
