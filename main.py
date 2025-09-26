import json
import logging
import os
from typing import Dict, Set

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests


# Server config
SERVER_PORT = 5004
MAX_CLIENTS_PER_ROOM = 2


# In-memory room tracking (simple process-local state)
room_counts: Dict[str, int] = {}
sid_rooms: Dict[str, Set[str]] = {}


# Socket.IO server (ASGI, CORS open like the original)
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


# FastAPI app for optional HTTP endpoints and CORS
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Wrap FastAPI with Socket.IO ASGI app
asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)


@app.on_event("startup")
async def on_startup() -> None:
    # Mirror the Node.js startup log
    print(f"Started on : {SERVER_PORT}")


@app.get("/")
async def root():
    return {"status": "ok"}


@sio.event
async def connect(sid, environ, auth):
    logging.info(f"connect sid={sid}")


@sio.event
async def disconnect(sid):
    # Decrement counts for any rooms this sid had joined
    rooms = sid_rooms.pop(sid, set())
    for room_id in rooms:
        if room_id in room_counts:
            room_counts[room_id] -= 1
            if room_counts[room_id] <= 0:
                del room_counts[room_id]
        print(f"disconnect, room:{room_id} count:{room_counts.get(room_id, 0)}")


@sio.on("join")
async def on_join(sid, room_id: str):
    # Enforce max clients per room
    count = room_counts.get(room_id, 0)
    if count >= MAX_CLIENTS_PER_ROOM:
        await sio.emit("room-full", room_id, to=sid)
        print(f"room full {room_id} count:{count}")
        return

    room_counts[room_id] = count + 1
    if sid not in sid_rooms:
        sid_rooms[sid] = set()
    sid_rooms[sid].add(room_id)

    await sio.enter_room(sid, room_id)
    print(f"User joined in a room : {room_id} count:{room_counts[room_id]}")


@sio.on("rtc-message")
async def on_rtc_message(sid, data):
    # Expect either a JSON string or a dict with roomId
    room_id = None
    if isinstance(data, str):
        try:
            payload = json.loads(data)
        except Exception:
            payload = {}
    elif isinstance(data, dict):
        payload = data
    else:
        payload = {}

    room_id = payload.get("roomId")
    if not room_id:
        return

    # Broadcast to the room except the sender (socket.broadcast.to(room))
    await sio.emit("rtc-message", data, room=room_id, skip_sid=sid)


@sio.on("rtc-text")
async def on_rtc_text(sid, data):
    """Receive rtc-text, print it, translate via Ollama, then broadcast (except sender)."""
    if isinstance(data, str):
        try:
            payload = json.loads(data)
        except Exception:
            payload = {"text": data}
    elif isinstance(data, dict):
        payload = data
    else:
        payload = {"text": str(data)}

    room_id = payload.get("roomId")
    text = payload.get("text") or payload.get("message") or ""
    print(f"[RTC-TEXT room={room_id or '-'} sid={sid}] {text}")

    # Translate with Ollama (if available). Fallback to original on failure.
    translated = translate_with_ollama(text)
    if translated:
        payload["translatedText"] = translated
        # Replace text so receivers see translated content directly
        payload["text"] = translated

    if room_id:
        await sio.emit("rtc-text", payload, room=room_id, skip_sid=sid)


def translate_with_ollama(text: str) -> str:
    """Translate English<->Korean using local Ollama.

    - Model: set with OLLAMA_MODEL (default: 'llama3.1')
    - Host: set with OLLAMA_HOST (default: 'http://localhost:11434')
    Returns empty string on error.
    """
    try:
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        model = os.getenv("OLLAMA_MODEL", "llama3.1")
        prompt = (
            "You are a translator. If the input is Korean, translate it to natural, colloquial English. "
            "If the input is English, translate it to natural, colloquial Korean. "
            "Preserve meaning and tone. Output only the translation with no extra words.\n\n"
            f"Input: {text}"
        )
        resp = requests.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        if resp.status_code != 200:
            logging.error("Ollama error %s: %s", resp.status_code, resp.text)
            return ""
        data = resp.json()
        out = data.get("response", "").strip()
        return out
    except Exception:
        logging.exception("Failed to translate via Ollama")
        return ""


if __name__ == "__main__":
    # Run the ASGI app with uvicorn on the desired port
    uvicorn.run(asgi_app, host="0.0.0.0", port=SERVER_PORT)
