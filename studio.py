"""Upstage v2 Files + Studio Agent Responses API. Never substitute demo data on failure."""
import json
import time
from urllib.parse import quote
import requests

BASE_URL = "https://api.upstage.ai/v2"


class StudioError(RuntimeError):
    pass


def parse_output(response: dict) -> dict:
    text = response.get("output_text")
    if not text:
        messages = [m for m in response.get("output", []) if m.get("type") == "message"]
        text = "".join(c.get("text", "") for m in messages[-1:] for c in m.get("content", []) if c.get("type") == "output_text")
    if not isinstance(text, str) or not text.strip():
        raise StudioError("Studio 응답에 최종 출력이 없습니다.")
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise StudioError("Studio 결과가 JSON 형식이 아닙니다. Extract 스키마를 확인하세요.") from exc
    if not isinstance(result, dict):
        raise StudioError("Studio 결과는 JSON 객체여야 합니다.")
    return result


class StudioClient:
    def __init__(self, api_key: str, timeout: float = 300):
        if not api_key:
            raise StudioError("UPSTAGE_API_KEY를 설정해 주세요.")
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_key}"
        self.timeout = timeout
        self.cleanup_warnings = []

    def request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self.session.request(method, BASE_URL + path, timeout=(10, 90), **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            code = exc.response.status_code
            raise StudioError(f"Upstage API 오류 {code}. API 키·Agent ID·사용 한도를 확인하세요.") from None
        except (requests.RequestException, ValueError):
            raise StudioError("Upstage 연결 또는 응답 형식 오류입니다. 네트워크 상태를 확인하세요.") from None

    def run(self, filename: str, content: bytes, agent_id: str, config_id: str = "") -> dict:
        if not agent_id:
            raise StudioError("Studio Agent ID를 입력해 주세요.")
        if len(content) > 10 * 1024 * 1024:
            raise StudioError("데모에서는 파일당 10MB 이하만 처리합니다.")
        uploaded = self.request("POST", "/files", files={"file": (filename, content)}, data={"purpose": "user_data"})
        file_id = uploaded.get("id")
        if not file_id:
            raise StudioError("업로드 응답에 파일 ID가 없습니다.")
        try:
            payload = {"model": agent_id, "include": ["last"], "input": [{"role": "user", "content": [{"type": "input_file", "file_id": file_id}]}]}
            if config_id:
                payload["config_id"] = config_id
            response = self.request("POST", "/responses", json=payload)
            deadline = time.monotonic() + self.timeout
            while response.get("status") in {"queued", "in_progress"}:
                if time.monotonic() >= deadline:
                    raise StudioError("Studio 대기 시간이 초과되었습니다. Studio에서 실행 상태를 확인하세요.")
                if not response.get("id"):
                    raise StudioError("Studio 응답에 작업 ID가 없습니다.")
                time.sleep(2)
                response = self.request("GET", "/responses/" + quote(response["id"], safe=""), params={"include": "last"})
            if response.get("status") != "completed":
                raise StudioError("Studio 실행이 완료되지 않았습니다. Studio 실행 기록을 확인하세요.")
            return parse_output(response)
        finally:
            try:
                self.request("DELETE", "/files/" + quote(file_id, safe=""))
            except StudioError:
                self.cleanup_warnings.append("Upstage 업로드 파일 삭제를 확인하지 못했습니다. Console에서 확인하세요.")
