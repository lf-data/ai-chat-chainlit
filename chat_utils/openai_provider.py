import io
from openai import OpenAI
import os
from langchain_openai import ChatOpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# General-purpose chat model
model = ChatOpenAI(
    model="gpt-5.4",
    max_completion_tokens=16384,
    store=False
)

# Specialized model for mathematical reasoning
math_model = ChatOpenAI(
    model="gpt-5.4",
    max_completion_tokens=16384,
    store=False
)

# OpenAI client for audio transcription
client_openai = OpenAI(api_key=OPENAI_API_KEY)


def transcribe_audio_bytes(audio_bytes: bytes, filename: str) -> str:
    """
    Transcribe audio bytes using OpenAI's Whisper model.
    Args:
        audio_bytes (bytes): The audio data in bytes.
        filename (str): The name of the audio file. 
    Returns:
        str: The transcribed text.
    """
    bio = io.BytesIO(audio_bytes)
    bio.seek(0)
    transcript = client_openai.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, bio),
        response_format="text",
    )
    return transcript.strip()
