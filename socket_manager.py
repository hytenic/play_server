from typing import Dict, Set

import socketio


class SocketSessionManager:
    """
    사용자별로 참여 중인 room을 추적하고, Socket.IO 서버와의 방 입장/퇴장을
    일관되게 처리하는 매니저.
    """

    def __init__(self, sio: socketio.AsyncServer) -> None:
        self._sio = sio
        self._sid_rooms: Dict[str, Set[str]] = {}

    async def on_connect(self, sid: str) -> None:
        """
        소켓 접속시 사용자별 room 정보 초기화
        """
        self._sid_rooms.setdefault(sid, set())

    async def on_disconnect(self, sid: str) -> Set[str]:
        """
        소켓 접속 종료시 사용자의 room 정보 제거
        """
        return self._sid_rooms.pop(sid, set())

    async def join_room(self, sid: str, room_id: str) -> None:
        """
        사용자별 room 정보 추가 후 room 접속
        """
        if not room_id:
            return
        rooms = self._sid_rooms.setdefault(sid, set())
        rooms.add(room_id)
        await self._sio.enter_room(sid, room_id)

    async def leave_room(self, sid: str, room_id: str) -> None:
        """
        사용자별 room 정보 제거 후 room 퇴장
        """
        if not room_id:
            return
        rooms = self._sid_rooms.get(sid)
        if rooms and room_id in rooms:
            rooms.remove(room_id)
        await self._sio.leave_room(sid, room_id)
