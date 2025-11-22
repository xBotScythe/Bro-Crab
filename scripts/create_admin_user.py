import argparse
import getpass
import sys
from pathlib import Path

# ensure project root is on sys.path when running directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import admin_auth


# quick cli helper for seeding the first portal user
def main():
    parser = argparse.ArgumentParser(description="Create an admin portal user")
    parser.add_argument("--username", help="Username for the admin account")
    args = parser.parse_args()

    username = args.username or input("Admin username: ").strip()
    if not username:
        print("username is required")
        return
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("passwords do not match")
        return
    try:
        admin_auth.create_admin_user(username, password)
        print(f"Admin user '{username}' created.")
    except Exception as exc:
        print(f"Failed to create admin user: {exc}")


if __name__ == "__main__":
    main()
