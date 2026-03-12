import argparse
import asyncio
import base64
import getpass
import hashlib
import json
import os
import re
import secrets

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


async def update_user_password(
    db_url: str,
    identifier: str,
    new_password: str,
    iterations: int,
) -> None:
    engine = create_async_engine(to_async_db_url(db_url), pool_pre_ping=True)

    select_query = text(
        'SELECT "id", "metadata" FROM "users" WHERE "identifier" = :identifier LIMIT 1'
    )
    update_query = text(
        'UPDATE "users" SET "metadata" = CAST(:metadata AS JSONB) WHERE "id" = :id'
    )

    async with engine.begin() as conn:
        result = await conn.execute(select_query, {"identifier": identifier})
        existing = result.mappings().first()
        if not existing:
            raise ValueError(f"Utente non trovato: {identifier}")

        metadata = existing.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}

        metadata["password_hash"] = hash_password(new_password, iterations)
        metadata.pop("password", None)
        metadata["provider"] = "email-password"

        await conn.execute(
            update_query,
            {
                "id": str(existing.get("id")),
                "metadata": json.dumps(metadata),
            },
        )

    await engine.dispose()
    print(f"Password aggiornata per: {identifier}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggiorna la password di un utente esistente nella tabella users"
    )
    parser.add_argument("--identifier", required=True, help="Email utente")
    parser.add_argument("--password", help="Nuova password in chiaro")
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

    password = args.password or getpass.getpass("Nuova password: ")
    if not password:
        raise ValueError("Password vuota non consentita")

    asyncio.run(
        update_user_password(
            db_url=db_url,
            identifier=identifier,
            new_password=password,
            iterations=args.iterations,
        )
    )


if __name__ == "__main__":
    main()