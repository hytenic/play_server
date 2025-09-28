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

    def get_rooms(self, sid: str) -> Set[str]:
        """해당 사용자가 속한 room 집합을 반환합니다. (복사본 아님, 내부 세트)
        호출 측에서 read-only로만 사용하세요.
        """
        return self._sid_rooms.get(sid, set())

    async def on_connect(self, sid: str) -> None:
        """연결 시 내부 구조 초기화"""
        self._sid_rooms.setdefault(sid, set())

    async def on_disconnect(self, sid: str) -> Set[str]:
        """
        연결 종료 시 사용자가 속한 room 목록을 반환하고, 내부 상태를 정리합니다.
        실제 방 퇴장은 Socket.IO가 자동으로 처리하므로 여기서는 추적만 제거합니다.
        """
        return self._sid_rooms.pop(sid, set())

    async def join_room(self, sid: str, room_id: str) -> None:
        """사용자를 room에 참여시킵니다."""
        if not room_id:
            return
        rooms = self._sid_rooms.setdefault(sid, set())
        rooms.add(room_id)
        await self._sio.enter_room(sid, room_id)

    async def leave_room(self, sid: str, room_id: str) -> None:
        """사용자를 room에서 퇴장시킵니다."""
        if not room_id:
            return
        rooms = self._sid_rooms.get(sid)
        if rooms and room_id in rooms:
            rooms.remove(room_id)
        await self._sio.leave_room(sid, room_id)
