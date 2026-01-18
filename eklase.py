import requests
import re

# standardType_fmft_ + folder_id
FOLDER_ID_PREFIX = "standardType_fmft_"
FOLDER_IDS = {"inbox", "unread", "follow", "deleted", "drafts", "sent"}
DEFAULT_USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0'
# type_mfa_ + action
ACTION_PREFIX = "type_mfa_"
ACTIONS = {"refresh", "permanentDelete", "delete"}

class EklaseAuthError(Exception):
    pass

class EklaseSession:

    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://my.e-klase.lv"
        self.api_url = f"{self.base_url}/api/family"
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
            action_match = re.search(r'action=["\']([^"\']+)["\']', response.text)
            if not action_match:
                raise EklaseAuthError("Profile selection form not found")

            action_url = action_match.group(1)
            form_data = self._get_form_data(response.text)

            response = self.session.post(f"{self.base_url}{action_url}", data=form_data)
            response.raise_for_status()

        if "Home?login=1" not in response.url:
            raise EklaseAuthError("Login failed")

    def _get_form_data(self, html_text):
        pattern = r'<input\s+[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']'
        inputs = re.findall(pattern, html_text)
        return {name: value for name, value in inputs}

    def _check_folder_id(self, folder_id: str):
        if folder_id.lower() not in FOLDER_IDS:
            raise ValueError(f"{folder_id} is not a valid mail type. "
                             f"Valid types: {', '.join(FOLDER_IDS)}")

    # get all message id's based on type (inbox, unread, follow, deleted, drafts, sent)
    def _fetch_message_ids(self, folder_id: str = "inbox") -> list[int]:
        self._check_folder_id(folder_id)

        mail_api_url = f"{self.api_url}/mail"
        message_ids_url = f"/folder-message-ids/standardType_fmft_{folder_id.lower()}"
        response = self.session.get(f"{mail_api_url}{message_ids_url}")
        response.raise_for_status()
        return response.json()

    # get (end - start) amount of messages (default: (10-0) = 0). Use only after _fetch_message_ids;
    # if end or start is -1 then all messages from ids list are fetched
    def _fetch_messages(self, ids: list[int], start: int = 0, end: int = 10) -> list[dict]:
        if not ids:
            return []

        if start == -1 or end == -1:
            actual_start = 0
            actual_end = len(ids)
        else:
            actual_start = max(0, start)
            actual_end = min(end, len(ids))
            if actual_start >= actual_end:
                return []

        messages_api_url = f"{self.api_url}/mail/messages"
        response = self.session.post(messages_api_url, json=ids[actual_start:actual_end])
        response.raise_for_status()
        return response.json()

    # get list of dict with message data; use -1 as amount for all messages
    def get_raw_mail(self, folder_id: str = "inbox", start: int = 0, amount: int = 10) -> list:
        message_ids = self._fetch_message_ids(folder_id)

        end = start + amount
        if amount == -1:
            end = -1

        return self._fetch_messages(message_ids, start, end)

    # generator that yields messages one by one, fetching them from api in chunks;
    # use -1 as amount for all messages
    def stream_raw_mail(self, folder_id: str = "inbox", start: int = 0, amount: int = 10, chunk_size: int = 5):
        message_ids = self._fetch_message_ids(folder_id)

        end = start + amount
        if amount == -1:
            end = len(message_ids)

        for i in range(start, end, chunk_size):
            message = self._fetch_messages(message_ids, start=i, end=i + chunk_size)
            yield message

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

    def send_message(self, recipients_ids: list[int], subject: str = ".", body: str = "."):
        send_api_url = f"{self.api_url}/mail/send"
        recipients: list[int] = []
        message = {"message": self._compose_message(recipients_ids, subject, body)}
        response = self.session.post(send_api_url, json=message)
        response.raise_for_status()
        return response.json() # messageId

    def delete_message(self, message_ids: list[int], folder_id: str = "inbox", permanently=False):
        self._check_folder_id(folder_id)

        if permanently is True or folder_id == "deleted" or folder_id == "sent":
            action = "permanentDelete"
        else:
            action = "delete"
        url = f"{self.api_url}/mail/perform-action-on-messages"
        json = {
                "action": ACTION_PREFIX + action,
                "folderId": FOLDER_ID_PREFIX + folder_id,
                "messageIds": message_ids
        }
        response = self.session.post(url, json=json)
        response.raise_for_status()

    def restore_message(self, message_ids: list[int]):
        url = f"{self.api_url}/mail/perform-action-on-messages"
        action = "refresh"
        json = {
                "action": ACTION_PREFIX + action,
                "folderId": FOLDER_ID_PREFIX + "deleted",
                "messageIds": message_ids
        }
        response = self.session.post(url, json=json)
        response.raise_for_status()
