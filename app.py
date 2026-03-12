import chainlit as cl
import hmac
import os
import re
import json
import base64
import hashlib
import secrets
import logging
from typing import List, Optional
from chat_utils.prompts import SYSTEM_PROMPT
from chat_utils.openai_provider import model, client_openai
from chat_utils.tools import load_tools
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.messages.tool import ToolMessage
from langchain.agents.middleware import (
    SummarizationMiddleware,
    ToolRetryMiddleware,
    ModelRetryMiddleware,
)
import numpy as np
import wave
import io
from chainlit.types import ThreadDict
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.data.storage_clients.s3 import S3StorageClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

storage_client = S3StorageClient(bucket=os.getenv("BUCKET_NAME"), endpoint_url=os.getenv("AWS_ENDPOINT"), aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"), aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"), region_name=os.getenv("AWS_DEFAULT_REGION"))
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "30"))
SUPABASE_DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL", "")
PASSWORD_HASH_ITERATIONS = int(os.getenv("PASSWORD_HASH_ITERATIONS", "600000"))

logger = logging.getLogger(__name__)


def _to_async_db_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


AUTH_DB_URL = _to_async_db_url(SUPABASE_DATABASE_URL) if SUPABASE_DATABASE_URL else ""
auth_engine: Optional[AsyncEngine] = (
    create_async_engine(AUTH_DB_URL, pool_pre_ping=True) if AUTH_DB_URL else None
)

@cl.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(conninfo=SUPABASE_DATABASE_URL, storage_provider=storage_client)


def _normalize_identifier(identifier: str) -> str:
    return (identifier or "").strip().lower()


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    salt_b64 = base64.b64encode(salt).decode("utf-8")
    digest_b64 = base64.b64encode(digest).decode("utf-8")
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt_b64}${digest_b64}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64)
        expected_digest = base64.b64decode(digest_b64)
    except Exception:
        return False

    computed_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(computed_digest, expected_digest)


def _safe_metadata_dict(metadata: object) -> dict:
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


async def _get_user_by_identifier(identifier: str) -> Optional[dict]:
    if not auth_engine:
        return None

    query = text(
        'SELECT "id", "identifier", "metadata" FROM "users" WHERE "identifier" = :identifier LIMIT 1'
    )
    async with auth_engine.connect() as conn:
        result = await conn.execute(query, {"identifier": identifier})
        row = result.mappings().first()
    return dict(row) if row else None


async def _update_user_metadata(user_id: str, metadata: dict) -> None:
    if not auth_engine:
        return

    query = text(
        'UPDATE "users" SET "metadata" = CAST(:metadata AS JSONB) WHERE "id" = :user_id'
    )
    async with auth_engine.begin() as conn:
        await conn.execute(
            query,
            {
                "user_id": str(user_id),
                "metadata": json.dumps(metadata),
            },
        )


@cl.password_auth_callback
async def password_auth_callback(username: str, password: str) -> Optional[cl.User]:
    if not auth_engine:
        logger.warning("SUPABASE_DATABASE_URL non impostata: autenticazione disabilitata")
        return None

    identifier = _normalize_identifier(username)
    if not identifier or not password or not _is_valid_email(identifier):
        return None

    user = await _get_user_by_identifier(identifier)
    if not user:
        return None

    metadata = _safe_metadata_dict(user.get("metadata"))
    stored_hash = metadata.get("password_hash")

    if isinstance(stored_hash, str) and _verify_password(password, stored_hash):
        return cl.User(
            identifier=identifier,
            metadata={
                **metadata,
                "user_id": str(user.get("id")),
                "provider": "email-password",
            },
        )

    legacy_password = metadata.get("password")
    if isinstance(legacy_password, str) and hmac.compare_digest(password, legacy_password):
        metadata.pop("password", None)
        metadata["password_hash"] = _hash_password(password)
        await _update_user_metadata(str(user.get("id")), metadata)
        return cl.User(
            identifier=identifier,
            metadata={
                **metadata,
                "user_id": str(user.get("id")),
                "provider": "email-password",
            },
        )

    return None

@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    cl.user_session.set("chat_history", [])

    for message in thread["steps"]:
        if message["type"] == "user_message":
            cl.user_session.get("chat_history").append(
                HumanMessage(content=message["output"])
            )
        elif message["type"] == "assistant_message":
            cl.user_session.get("chat_history").append(
                AIMessage(content=message["output"])
            )


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("chat_history", [])


def is_silent(audio_bytes, threshold=500):
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
    if len(audio_np) == 0:
        return True
    volume = np.abs(audio_np).mean()
    return volume < threshold

@cl.on_audio_start
async def on_audio_start():
    cl.user_session.set("audio_chunks", [])
    return True

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    audio_chunks = cl.user_session.get("audio_chunks")
    if not is_silent(chunk.data):
        audio_chunk = np.frombuffer(chunk.data, dtype=np.int16)
        audio_chunks.append(audio_chunk)
        cl.user_session.set("audio_chunks", audio_chunks)

async def generate_transcript(audio_data):
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 2 bytes per sample (16-bit)
        wav_file.setframerate(24000)  # sample rate (24kHz PCM)
        wav_file.writeframes(audio_data.tobytes())
    wav_buffer.seek(0)
    audio_buffer = wav_buffer.getvalue()

    return client_openai.audio.transcriptions.create(
        model="whisper-1",
        file=("audio.wav", audio_buffer, "audio/wav"),
        response_format="text",
    )

@cl.on_audio_end
async def on_audio_end():
    audio_chunks = cl.user_session.get("audio_chunks")
    if not audio_chunks:
        return
    audio_data = np.concatenate(list(audio_chunks))
    cl.user_session.set("audio_chunks", [])
    
    text = await generate_transcript(audio_data)

    msg = cl.Message(
        content=text,
        author=cl.context.session.user.identifier,
        type="user_message"
    )

    await msg.send()

    await on_message(msg)


@cl.on_message
async def on_message(message: cl.Message):
    thread_id = cl.context.session.id
    config = {"configurable": {"thread_id": thread_id}}
    history = cl.user_session.get("chat_history", [])
    history.append(HumanMessage(content=message.content))

    final_answer = cl.Message(content="")
    assistant_chunks: List[str] = []
    tools = load_tools()


    client = create_agent(
        model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            SummarizationMiddleware(
                model=model, trigger=("tokens", 4000), keep=("messages", MAX_MESSAGES)
            ),
            ToolRetryMiddleware(
                max_retries=3,
                backoff_factor=2.0,
                initial_delay=1.0,
            ),
            ModelRetryMiddleware(
                max_retries=3,
                backoff_factor=2.0,
                initial_delay=1.0,
            ),
        ],
    )
    msg_type = "ai"
    async for msg, _ in client.astream(
        {"messages": history},
        stream_mode="messages",
        config=RunnableConfig(**config),
    ):
        if (
            msg.content
            and isinstance(msg, AIMessageChunk)
        ):
            if msg_type != "ai":
                final_answer.content = ""
                await final_answer.update()
            msg_type = "ai"
            assistant_chunks.append(msg.content)
            await final_answer.stream_token(msg.content)
        elif isinstance(msg, ToolMessage):
            msg_type = "tool"
        elif not isinstance(msg, AIMessageChunk):
            msg_type = "other"

    assistant_text = "".join(assistant_chunks).strip()
    if assistant_text:
        history.append(AIMessage(content=assistant_text))

    await final_answer.send()