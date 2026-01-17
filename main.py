from eklase import EklaseSession
from models import MailItem

eklase = EklaseSession()

username = input("Username: ")
password = input("Password: ")

try:
    eklase.login(username, password)
except Exception as e:
    print(e)
    exit(1)

raw_emails = eklase.get_mail()
filtered_emails = [MailItem.from_dict(mail) for mail in raw_emails]
