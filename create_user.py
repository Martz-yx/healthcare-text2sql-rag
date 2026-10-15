import sys
import bcrypt

def main():
    if len(sys.argv) < 3:
        print("Usage: python create_user.py <username> <password> [display_name] [role]")
        print('  role: "admin" or "user" (default: "user")')
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    display_name = sys.argv[3] if len(sys.argv) > 3 else username
    role = sys.argv[4] if len(sys.argv) > 4 else "user"

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    print("\n-- Run this in DBeaver against the chainlit database:")
    print(
        f"INSERT INTO user_credentials (username, password_hash, display_name, role)\n"
        f"VALUES ('{username}', '{password_hash}', '{display_name}', '{role}')\n"
        f"ON CONFLICT (username) DO NOTHING;"
    )

if __name__ == "__main__":
    main()
