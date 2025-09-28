# 플레이 서버 (Play Server)

실시간 통역을 지원하는 WebRTC 시그널링 및 번역 게이트웨이 서버입니다. FastAPI와 Socket.IO를 기반으로 하여 다수 사용자의 음성/텍스트 스트림을 받아 언어 간 변환 결과를 다시 웹 클라이언트로 전달합니다.

## 주요 구성 요소
- `main.py`: FastAPI 애플리케이션과 Socket.IO 서버를 구동하고, 이벤트 라우팅과 CORS 설정을 담당합니다.
- `agent_manager.py`: 접속한 사용자별로 통역 에이전트를 생성, 재사용, 해제합니다.
- `socket_manager.py`: Socket.IO 세션과 룸 관리를 일관되게 처리합니다.
- `translator.py`: Ollama API를 호출하는 통역 에이전트로, 사용자별 비동기 큐를 통해 번역 요청을 순차 처리합니다.

## 사전 준비
- Python 3.10 이상
- Ollama 서버 또는 호환되는 LLM 서버

## 설치 및 실행
1. 의존성 설치
   ```bash
   python -m venv .venv
   source .venv/bin/activate 
   pip install -r requirements.txt
   ```
2. 서버 실행
   ```bash
   python main.py
   ```

## Socket.IO 이벤트 요약
| `connect` | 클라이언트 → 서버 | 세션 생성 후 사용자 전용 통역 에이전트를 기동합니다. |
| `disconnect` | 클라이언트 → 서버 | 세션 종료 및 에이전트를 정리합니다. |
| `join` | 클라이언트 → 서버 | 지정한 `roomId`로 참여합니다. |
| `rtc-message` | 양방향 브로드캐스트 | WebRTC 시그널링 메시지를 같은 룸의 다른 참가자에게 전달합니다. |
| `rtc-text` | 양방향 브로드캐스트 | 클라이언트 텍스트(STT 결과)를 번역 후 룸 내 다른 참가자에게 전달합니다. |

## 번역 에이전트 동작
1. 사용자별로 `TranslatorAgent` 인스턴스가 한 번만 생성됩니다.
2. 들어오는 번역 요청은 asyncio 큐에 쌓여 순차적으로 처리됩니다.
3. Ollama의 `/api/generate` 엔드포인트를 호출하여 번역 결과를 얻습니다.
4. 응답 실패 시 빈 문자열을 반환하며, 필요에 따라 재시도 로직을 확장할 수 있습니다.