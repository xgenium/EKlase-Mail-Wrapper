from eklase import *

if __name__ == "__main__":
    eklase = EklaseSession()

    username = input("Username: ")
    password = input("Password: ")

    eklase.login(username, password)
