import requests
from bs4 import BeautifulSoup

VALID_MAIL_TYPES = {"inbox", "unread", "follow", "deleted", "drafts", "sent"}
DEFAULT_USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0'

class EklaseAuthError(Exception):
    pass

class EklaseApiError(Exception):
    pass

class EklaseSession:

    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://my.e-klase.lv"
        self.api_url = f"{self.base_url}/api/family"
        self._mail_idx = 0
        self._prev_mail_type = ""
        # request is blocked without User-Agent
        self.session.headers.update({'User-Agent': DEFAULT_USER_AGENT})

    def login(self, username, password):
        payload = {
            "fake_pass": password,
            "UserName": username,
            "Password": password,
            "cmdLogin": ""
        }

        login_page = f"{self.base_url}/?v=15"

        response = self.session.post(login_page, data=payload)
        response.raise_for_status()

        # handle profile selection
        if "CheckForProfileSelection" in response.url:
            soup = BeautifulSoup(response.text, "html.parser")
            form = soup.find("form")
            if form is None:
                raise EklaseAuthError("Profile selection form not found")

            action_url = form["action"]

            # grab all hidden inputs required for next redirect (TenantId, pf_id)
            form_data = {i["name"]: i.get("value", "")
                         for i in form.find_all("input") if i.has_attr("name")}
            response = self.session.post(f"{self.base_url}{action_url}", data=form_data)
            response.raise_for_status()

        if "Home?login=1" not in response.url:
            raise EklaseAuthError("Login failed")

    def _check_mail_type(self, mail_type: str):
        if mail_type.lower() not in VALID_MAIL_TYPES:
            raise ValueError(f"{mail_type} is not a valid mail type. "
                             f"Valid types: {', '.join(VALID_MAIL_TYPES)}")

    # get all message id's based on type (inbox, unread, follow, deleted, drafts, sent)
    def _fetch_message_ids(self, mail_type: str = "inbox") -> list[int]:
        self._check_mail_type(mail_type)

        mail_api_url = f"{self.api_url}/mail"
        message_ids_url = f"/folder-message-ids/standardType_fmft_{mail_type.lower()}"
        response = self.session.get(f"{mail_api_url}{message_ids_url}")
        response.raise_for_status()
        return response.json()

    # get amount of messages (default: 10). Use only after _fetch_message_ids
    def _fetch_messages(self, ids: list[int], amount=10) -> list[dict]:
        if not ids:
            return []

        max_idx = min(amount + self._mail_idx, len(ids))

        messages_api_url = f"{self.api_url}/mail/messages"
        # assume 0 as a starting idx in the list
        response = self.session.post(messages_api_url, json=ids[self._mail_idx:max_idx])
        response.raise_for_status()
        return response.json()

    # get list of dict with message data
    def get_mail(self, mail_type: str = "inbox", amount=10) -> list:
        self._message_ids = self._fetch_message_ids(mail_type)
        if self._prev_mail_type != mail_type:
            self._mail_idx = 0
            self._prev_mail_type = mail_type

        return self._fetch_messages(self._message_ids, amount)

    def extend_mail(self, amount=10):
        self._mail_idx = min(amount + self._mail_idx, len(self._message_ids))
        return self._fetch_messages(self._message_ids, amount)

    def read_message(self, message_id):
        unread_api_url = f"{self.api_url}/mail/message/read"
        response = self.session.post(unread_api_url, json={"messageId": message_id})
        response.raise_for_status()

    def _compose_message(self, recipients_ids: list[int], subject: str = ".", body: str = ".") -> dir:
        recipients = [{'id': rec_id} for rec_id in recipients_ids]
        return {
            "body": body,
            "draftType": "mdt_new",
            "recipients": recipients,
            "subject": subject
        }

    # def save_draft_message(self, recipients: list[dir], subject: str = ".", body: str = "."):
    #     save_draft_url = f"{self.api_url}/mail/save-draft"
    #     message

    # TODO: Add recipients selection

    def send_message(self, recipients_ids: list[int], subject: str = ".", body: str = "."):
        send_api_url = f"{self.api_url}/mail/send"
        recipients: list[int] = []
        message = {"message": self._compose_message(recipients_ids, subject, body)}
        response = self.session.post(send_api_url, json=message)
        response.raise_for_status()
        return response.json() # messageId
