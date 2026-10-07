"""Create or change the dashboard login.

    python 08_Dashboard/set_password.py

Asks for a login and a password (typed twice, not shown) and saves the salted
hash to .streamlit/secrets.toml. The dashboard picks it up immediately.
"""
import sys
from getpass import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402,F401
import auth  # noqa: E402

if __name__ == "__main__":
    username = input("Login: ").strip()
    password = getpass("Parol: ")
    if not username or len(password) < 8:
        sys.exit("Login bo'sh bo'lmasligi va parol kamida 8 belgidan iborat bo'lishi kerak.")
    if getpass("Parolni takrorlang: ") != password:
        sys.exit("Parollar mos kelmadi.")
    auth.write_account(username, password)
    print(f"Saqlandi: {auth.SECRETS}")
