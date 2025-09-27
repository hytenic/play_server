import os
import requests
import logging


def translate_with_ollama(text: str) -> str:
    try:
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
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
