import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

import httpx


DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


class TranslatorAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.history: List[Dict[str, str]] = []
        self._queue: asyncio.Queue[Tuple[str, asyncio.Future[str]]] = asyncio.Queue()
        self._task: Optional[asyncio.Task[None]] = None

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self.run(), name=f"translator-agent:{self.user_id}")

    async def stop(self) -> None:
        task = self._task
        if not task:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def run(self) -> None:
        try:
            while True:
                text, future = await self._queue.get()
                if future.cancelled():
                    self._queue.task_done()
                    continue
                try:
                    result = await self._call_ollama(text)
                except Exception:
                    logging.exception("Failed to translate text")
                    result = ""
                if result:
                    self.history.append({"input": text, "output": result})
                if not future.done():
                    future.set_result(result)
                self._queue.task_done()
        except asyncio.CancelledError:
            self._drain_pending()
            raise

    async def translate(self, text: str) -> str:
        if not self._task or self._task.done():
            self.start()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        await self._queue.put((text, future))
        return await future

    async def _call_ollama(self, text: str) -> str:
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
        return out

    def _drain_pending(self) -> None:
        while not self._queue.empty():
            try:
                _, future = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if not future.done():
                future.set_result("")
            self._queue.task_done()


agents: Dict[str, TranslatorAgent] = {}


def ensure_agent(user_id: str) -> TranslatorAgent:
    if user_id not in agents:
        agents[user_id] = TranslatorAgent(user_id)
    return agents[user_id]


async def translate_text(user_id: str, text: str) -> str:
    agent = ensure_agent(user_id)
    return await agent.translate(text)


async def release_agent(user_id: str) -> None:
    agent = agents.pop(user_id, None)
    if agent:
        await agent.stop()
