from dataclasses import dataclass
from inspect import signature

@dataclass
class MailItem:
    id: int
    sender: str
    subject: str
    body: str

    @classmethod
    def from_dict(cls, data: dict):
        recipients_data = data.get("recipientsData", {})
        recipients = recipients_data.get("recipients", [])

        if recipients:
            sender_str = recipients[0].get("name") or "Unknown"
        else:
            sender_str = "Hidden recipients"

        return cls(
            id=data["id"],
            sender=sender_str,
            subject=data.get("subject", ""),
            body=data.get("body", ""),
        )
