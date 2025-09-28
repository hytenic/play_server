import json
import logging
from typing import Dict, Set

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_manager import AgentManager

SERVER_PORT = 5004

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

agent_manager = AgentManager()


@app.get("/")
async def health_check():
    """
    Health check
    """
    return {"status": "ok"}


@sio.event
async def connect(sid, environ, auth):
    """
    소켓 연결 및 사용자별 통역 Agent 생성/실행
    """
    logging.info(f"connect sid={sid}")
    agent = agent_manager.ensure_agent(sid)
    agent.start()


@sio.event
async def disconnect(sid):
    """
    소켓 연결 해제 및 사용자별 통역 Agent 종료
    """
    rooms = sid_rooms.pop(sid, set())
    for room_id in rooms:
        logging.info(f"disconnect, room:{room_id}")
    await agent_manager.release(sid)


@sio.on("join")
async def on_join(sid, room_id: str):
    """
    사용자별 room_id 저장 및 소켓 room 입장
    """
    if sid not in sid_rooms:
        sid_rooms[sid] = set()
    sid_rooms[sid].add(room_id)

    await sio.enter_room(sid, room_id)
    logging.info(f"User joined in a room : {room_id}")


@sio.on("rtc-message")
async def on_rtc_message(sid, data):
    room_id = None
    try:
        payload = json.loads(data)
    except Exception as e:
        payload = {}
        logging.error(f"Failed to parse RTC message: {e}")

    room_id = payload.get("roomId")
    if not room_id:
        return

    await sio.emit("rtc-message", data, room=room_id, skip_sid=sid)


@sio.on("rtc-text")
async def on_rtc_text(sid, data):
    room_id = data.get("roomId")
    text = data.get("text")
    logging.info(text)
    data["text"] = await agent_manager.translate(sid, text)
    if room_id:
        await sio.emit("rtc-text", data, room=room_id, skip_sid=sid)


if __name__ == "__main__":
    uvicorn.run(asgi_app, host="0.0.0.0", port=SERVER_PORT)
