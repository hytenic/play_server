import json
import logging
import os
from typing import Dict, List

import httpx


DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


class TranslatorAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.history: List[Dict[str, str]] = []

    async def translate(self, text: str) -> str:
        host = os.getenv("OLLAMA_HOST", DEFAULT_HOST).rstrip("/")
        model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        prompt = (
            "You are a translator. If the input is Korean, translate it to natural, colloquial English. "
            "If the input is English, translate it to natural, colloquial Korean. "
            "Preserve meaning and tone. Output only the translation with no extra words.\n\n"
            f"Context: {json.dumps(self.history, ensure_ascii=False)}\n"
            f"Input: {text}"
        )
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{host}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
        except Exception:
            logging.exception("Failed to call Ollama")
            return ""
        if resp.status_code != 200:
            logging.error("Ollama error %s: %s", resp.status_code, resp.text)
            return ""
        try:
            data = resp.json()
        except Exception:
            logging.exception("Invalid Ollama response")
            return ""
        out = data.get("response", "").strip()
        if out:
            self.history.append({"input": text, "output": out})
        return out


agents: Dict[str, TranslatorAgent] = {}


def ensure_agent(user_id: str) -> TranslatorAgent:
    if user_id not in agents:
        agents[user_id] = TranslatorAgent(user_id)
    return agents[user_id]


async def translate_text(user_id: str, text: str) -> str:
    agent = ensure_agent(user_id)
    return await agent.translate(text)


def release_agent(user_id: str) -> None:
    agents.pop(user_id, None)
