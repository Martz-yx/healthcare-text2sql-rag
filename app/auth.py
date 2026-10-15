import os
import logging

import bcrypt
import psycopg2
import chainlit as cl

logger = logging.getLogger("auth")

_CREDENTIALS_DB_URL = os.getenv(
    "AUTH_DB_URL",
    "postgresql://{user}:{password}@{host}:{port}/{dbname}".format(
        user=os.getenv("CHAINLIT_DB_USER", "chainlit"),
        password=os.getenv("CHAINLIT_DB_PASSWORD", "changeme"),
        host=os.getenv("CHAINLIT_DB_HOST", "chainlit-db"),
        port=os.getenv("CHAINLIT_DB_PORT", "5432"),
        dbname=os.getenv("CHAINLIT_DB_NAME", "chainlit"),
    ),
)

def _get_conn():
    return psycopg2.connect(_CREDENTIALS_DB_URL)


def verify_user(username: str, password: str) -> dict | None:
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT password_hash, display_name, role FROM user_credentials "
                    "WHERE username = %s AND is_active = true",
                    (username,),
                )
                row = cur.fetchone()
    except Exception:
        logger.exception("Error verifying user %s", username)
        return None

    if row is None:
        return None

    password_hash, display_name, role = row
    if bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")):
        return {
            "username": username,
            "display_name": display_name or username,
            "role": role or "user",
        }
    return None


@cl.password_auth_callback
def auth_callback(username: str, password: str):
    user = verify_user(username, password)
    if user is None:
        return None
    return cl.User(
        identifier=user["username"],
        metadata={
            "role": user["role"],
            "display_name": user["display_name"],
        },
    )
