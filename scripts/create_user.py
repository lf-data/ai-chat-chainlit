import argparse
import asyncio
import base64
import getpass
import hashlib
import json
import os
import re
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

load_dotenv()


DEFAULT_ITERATIONS = int(os.getenv("PASSWORD_HASH_ITERATIONS", "600000"))


def to_async_db_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def normalize_identifier(identifier: str) -> str:
    return (identifier or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def hash_password(password: str, iterations: int) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    salt_b64 = base64.b64encode(salt).decode("utf-8")
    digest_b64 = base64.b64encode(digest).decode("utf-8")
    return f"pbkdf2_sha256${iterations}${salt_b64}${digest_b64}"


async def create_or_update_user(
    db_url: str,
    identifier: str,
    password: str,
    role: str,
    update_existing: bool,
    iterations: int,
) -> None:
    engine = create_async_engine(to_async_db_url(db_url), pool_pre_ping=True)

    select_query = text(
        'SELECT "id", "metadata" FROM "users" WHERE "identifier" = :identifier LIMIT 1'
    )
    insert_query = text(
        'INSERT INTO "users" ("id", "identifier", "metadata", "createdAt") VALUES (:id, :identifier, CAST(:metadata AS JSONB), :created_at)'
    )
    update_query = text(
        'UPDATE "users" SET "metadata" = CAST(:metadata AS JSONB) WHERE "id" = :id'
    )

    async with engine.begin() as conn:
        result = await conn.execute(select_query, {"identifier": identifier})
        existing = result.mappings().first()

        metadata = {
            "role": role,
            "provider": "email-password",
            "password_hash": hash_password(password, iterations),
        }

        if existing:
            if not update_existing:
                raise ValueError(
                    f"Utente '{identifier}' già presente. Usa --update-existing per aggiornarlo."
                )

            existing_metadata = existing.get("metadata")
            if isinstance(existing_metadata, str):
                try:
                    existing_metadata = json.loads(existing_metadata)
                except json.JSONDecodeError:
                    existing_metadata = {}
            if not isinstance(existing_metadata, dict):
                existing_metadata = {}

            existing_metadata.update(metadata)

            await conn.execute(
                update_query,
                {
                    "id": str(existing.get("id")),
                    "metadata": json.dumps(existing_metadata),
                },
            )
            print(f"Utente aggiornato: {identifier}")
        else:
            await conn.execute(
                insert_query,
                {
                    "id": str(uuid.uuid4()),
                    "identifier": identifier,
                    "metadata": json.dumps(metadata),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            print(f"Utente creato: {identifier}")

    await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crea o aggiorna un utente nella tabella users di Supabase"
    )
    parser.add_argument("--identifier", required=True, help="Email utente")
    parser.add_argument("--password", help="Password in chiaro")
    parser.add_argument("--role", default="user", help="Ruolo salvato in metadata")
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Aggiorna un utente esistente invece di fallire",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help="Iterazioni PBKDF2 (default da PASSWORD_HASH_ITERATIONS o 600000)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_url = os.getenv("SUPABASE_DATABASE_URL", "").strip()

    if not db_url:
        raise ValueError("Variabile SUPABASE_DATABASE_URL non impostata")

    identifier = normalize_identifier(args.identifier)
    if not is_valid_email(identifier):
        raise ValueError("--identifier deve essere una email valida")

    password = args.password or getpass.getpass("Password: ")
    if not password:
        raise ValueError("Password vuota non consentita")

    asyncio.run(
        create_or_update_user(
            db_url=db_url,
            identifier=identifier,
            password=password,
            role=args.role,
            update_existing=args.update_existing,
            iterations=args.iterations,
        )
    )


if __name__ == "__main__":
    main()