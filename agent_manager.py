from typing import Dict

from translator import TranslatorAgent


class AgentManager:
    def __init__(self) -> None:
        self._agents: Dict[str, TranslatorAgent] = {}

    def ensure_agent(self, user_id: str) -> TranslatorAgent:
        """
        사용자별로 통역 Agent를 생성하고 반환
        """
        if user_id not in self._agents:
            self._agents[user_id] = TranslatorAgent(user_id)
        return self._agents[user_id]

    async def translate(self, user_id: str, text: str) -> str:
        """
        사용자별로 통역 Agent를 가져온 후 통역 작업을 큐에 추가
        """
        agent = self.ensure_agent(user_id)
        return await agent.translate(text)

    async def release(self, user_id: str) -> None:
        """
        사용자의 agent를 제거하고 종료
        """
        agent = self._agents.pop(user_id, None)
        if agent:
            await agent.stop()
