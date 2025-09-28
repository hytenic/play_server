import asyncio
import os
from typing import Optional, Tuple

import httpx


DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


class TranslatorAgent:
    """
    사용자별로 통역을 위한 Agent
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._queue: asyncio.Queue[Tuple[str, asyncio.Future[str]]] = asyncio.Queue()
        self._task: Optional[asyncio.Task[None]] = None

    def start(self) -> None:
        """
        통역 비동기 처리를 위한 task 생성
        """
        if self._task and not self._task.done():
            return
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(
            self.run(), name=f"translator-agent:{self.user_id}"
        )

    async def stop(self) -> None:
        """
        비동기 task 종료
        """
        task = self._task
        if not task:
            return
        task.cancel()
        try:
            # task에서 기존에 처리중이던 작업이 cancel되어 발생할 수 있는 CancelledError 처리
            await task
        except asyncio.CancelledError:
            print("TranslatorAgent task cancelled")
        self._task = None

    async def run(self) -> None:
        """
        큐에 쌓여있는 통역 요청을 가져와서 처리
        """
        try:
            while True:
                text, future = await self._queue.get()
                if future.cancelled():
                    self._queue.task_done()
                    continue
                result = await self._call_ollama(text)
                if not future.done():
                    # 비동기 작업 결과 설정
                    future.set_result(result)
                # 큐에서 처리된 작업을 완료처리
                self._queue.task_done()
        except asyncio.CancelledError:
            self._drain_pending()
            raise

    async def translate(self, text: str) -> str:
        """
        통역 요청 작업을 큐에 추가
        """
        if not self._task or self._task.done():
            self.start()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        await self._queue.put((text, future))
        return await future

    async def _call_ollama(self, text: str) -> str:
        """
        Ollama API를 호출하여 통역
        """
        host = os.getenv("OLLAMA_HOST", DEFAULT_HOST).rstrip("/")
        model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        prompt = self._build_prompt(text)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{host}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            print("Failed to call Ollama")
            return ""
        return data.get("response", "").strip()

    def _build_prompt(self, text: str) -> str:
        """
        통역 요청을 위한 프롬프트 생성
        """
        return (
            "You are a translator. If the input is Korean, translate it to natural, colloquial English. "
            "If the input is English, translate it to natural, colloquial Korean. "
            "Preserve meaning and tone. Output only the translation with no extra words.\n\n"
            f"Input: {text}"
        )

    def _drain_pending(self) -> None:
        """
        큐에 쌓여있는 작업을 완료처리하여 큐를 비움
        """
        while not self._queue.empty():
            try:
                _, future = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if not future.done():
                future.set_result("")
            self._queue.task_done()
