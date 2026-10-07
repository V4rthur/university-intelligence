"""Manage the dashboard accounts.

    python 08_Dashboard/set_password.py            create an account or change its password / role
    python 08_Dashboard/set_password.py --list     show the accounts and their roles
    python 08_Dashboard/set_password.py --delete LOGIN

Each account has a role (rahbariyat, dekan, oqituvchi); a dean's account also
names its faculty. Passwords are typed twice, not shown, and only their salted
hash is saved to .streamlit/secrets.toml. The dashboard picks changes up
immediately.
"""
import argparse
import json
import sys
from getpass import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import auth  # noqa: E402

ROLE_HELP = {"rahbariyat": "universitet rahbariyati - hamma narsa",
             "dekan": "fakultet dekani - faqat o'z fakulteti",
             "oqituvchi": "professor-o'qituvchi - faqat umumlashtirilgan ko'rsatkichlar"}


def choose(title: str, options: list[str], notes: dict | None = None) -> str:
    print(title)
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}" + (f"  ({notes[option]})" if notes else ""))
    answer = input("Raqam: ").strip()
    if not answer.isdigit() or not 1 <= int(answer) <= len(options):
        sys.exit("Noto'g'ri tanlov.")
    return options[int(answer) - 1]


def faculties() -> list[str]:
    try:
        return [f["FacultyName"] for f in json.loads((config.RAW_DIR / "faculties.json").read_text("utf-8"))]
    except (OSError, ValueError, KeyError):
        return []


def main():
    ap = argparse.ArgumentParser(description="Dashboard hisoblarini boshqarish")
    ap.add_argument("--list", action="store_true", help="hisoblar ro'yxati")
    ap.add_argument("--delete", metavar="LOGIN", help="hisobni o'chirish")
    args = ap.parse_args()

    if args.list:
        for acc in auth.accounts().values():
            print(f"{acc['username']:<20} {acc['role']:<11} {acc.get('faculty', '')}")
        return
    if args.delete:
        sys.exit(None if auth.delete_account(args.delete) else f"Bunday hisob yo'q: {args.delete}")

    username = input("Login: ").strip()
    if not username:
        sys.exit("Login bo'sh bo'lmasligi kerak.")
    role = choose("Rol:", list(auth.ROLES), ROLE_HELP)
    faculty = None
    if role == "dekan":
        names = faculties()
        faculty = choose("Fakultet:", names) if names else input("Fakultet nomi: ").strip()
    password = getpass("Parol (kamida 8 belgi): ")
    if len(password) < 8:
        sys.exit("Parol kamida 8 belgidan iborat bo'lishi kerak.")
    if getpass("Parolni takrorlang: ") != password:
        sys.exit("Parollar mos kelmadi.")
    auth.write_account(username, password, role, faculty)
    print(f"Saqlandi: {username} ({role}{' · ' + faculty if faculty else ''}) -> {auth.SECRETS}")


if __name__ == "__main__":
    main()
