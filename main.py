from eklase import EklaseSession
from models import MailItem

eklase = EklaseSession()

username = input("Username: ")
password = input("Password: ")

try:
    eklase.login(username, password)
except Exception as e:
    print(e)
