import json
import logging
from typing import Dict, Set

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from translator import translate_with_ollama

SERVER_PORT = 5004
MAX_CLIENTS_PER_ROOM = 2

room_counts: Dict[str, int] = {}
sid_rooms: Dict[str, Set[str]] = {}

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)


@app.get("/")
async def root():
    return {"status": "ok"}


@sio.event
async def connect(sid, environ, auth):
    logging.info(f"connect sid={sid}")


@sio.event
async def disconnect(sid):
    rooms = sid_rooms.pop(sid, set())
    for room_id in rooms:
        if room_id in room_counts:
            room_counts[room_id] -= 1
            if room_counts[room_id] <= 0:
                del room_counts[room_id]
        print(f"disconnect, room:{room_id} count:{room_counts.get(room_id, 0)}")


@sio.on("join")
async def on_join(sid, room_id: str):
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

    await sio.emit("rtc-message", data, room=room_id, skip_sid=sid)


@sio.on("rtc-text")
async def on_rtc_text(sid, data):
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

    translated = translate_with_ollama(text)
    if translated:
        payload["translatedText"] = translated
        payload["text"] = translated

    if room_id:
        await sio.emit("rtc-text", payload, room=room_id, skip_sid=sid)


if __name__ == "__main__":
    uvicorn.run(asgi_app, host="0.0.0.0", port=SERVER_PORT)
