from typing import Dict

from translator import TranslatorAgent


class AgentManager:
    def __init__(self) -> None:
        self._agents: Dict[str, TranslatorAgent] = {}

    def ensure_agent(self, user_id: str) -> TranslatorAgent:
        if user_id not in self._agents:
            self._agents[user_id] = TranslatorAgent(user_id)
        return self._agents[user_id]

    async def translate(self, user_id: str, text: str) -> str:
        agent = self.ensure_agent(user_id)
        return await agent.translate(text)

    async def release(self, user_id: str) -> None:
        agent = self._agents.pop(user_id, None)
        if agent:
            await agent.stop()
