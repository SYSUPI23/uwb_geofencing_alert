"""
LocalSense API 클래스
부저, 진동, 디스플레이 메시지 전송
"""
import json
import hmac
import hashlib
from typing import List, Dict, Any, Optional

import requests




class LocalSenseAPI:
    def __init__(self, base_url: str, secret_key: str):
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        self.base_url = base_url
        self.secret_key = secret_key

    @classmethod  
    def from_host(cls, ip: str, port: int = 8888, secret_key: str = "") -> "LocalSenseAPI":
        return cls(base_url=f"http://{ip}:{port}", secret_key=secret_key)

    def _sign(self, path: str, body: str) -> str:
        """HMAC-MD5 서명 생성"""
        msg = (path + body).encode("utf-8")
        key = self.secret_key.encode("utf-8")
        return hmac.new(key, msg, hashlib.md5).hexdigest()

    def _post(self, path: str, payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """공통 POST 처리"""
        url = self.base_url + path
        body = json.dumps(payload, separators=(",", ":"))
        headers = {"Content-Type": "application/json", "sign": self._sign(path, body)}

        try:
            resp = requests.post(url, data=body, headers=headers, timeout=timeout)
            try:
                data: Optional[Dict[str, Any]] = resp.json()
            except ValueError:
                data = None

            if resp.status_code == 200 and isinstance(data, dict):
                return data
            return {"issuccess": "false", "message": f"HTTP {resp.status_code}: {resp.text}"}
        except requests.exceptions.RequestException as e:
            return {"issuccess": "false", "message": f"네트워크 오류: {e}"}

    def send_buzzer(
        self,
        tag_ids: List[int],
        *,
        shake_sdur: int = 5,
        shake_edur: int = 15,
        send_counts: int = 1,
        send_interval: int = 1,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """부저만 전송"""
        path = "/andon/alarm"
        payload = {
            "tag_ids": tag_ids,
            "shake_sdur": shake_sdur,
            "shake_edur": shake_edur,
            "vibrate_times": 0,
            "vibrate_dur": 15,
            "send_counts": send_counts,
            "send_interval": send_interval,
        }
        return self._post(path, payload, timeout=timeout)

    def send_vibration(
        self,
        tag_ids: List[int],
        *,
        vibrate_times: int = 1,
        vibrate_dur: int = 6,
        send_counts: int = 1,
        send_interval: int = 1,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """진동만 전송"""
        path = "/andon/alarm"
        payload = {
            "tag_ids": tag_ids,
            "shake_sdur": 0,
            "shake_edur": 15,
            "vibrate_times": vibrate_times,
            "vibrate_dur": vibrate_dur,
            "send_counts": send_counts,
            "send_interval": send_interval,
        }
        return self._post(path, payload, timeout=timeout)

    def send_display_message(
        self,
        tag_id: int,
        *,
        title: str = "경고",
        message: str = "위험구역 진입!",
        msg_type: str = "0",
        vibrate_off: bool = False,  # 진동도 같이 켜기
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """태그 디스플레이에 메시지 전송"""
        path = "/andon/show"
        payload = {
            "iwatchid": str(tag_id),
            "msgid": "10",
            "msgtitle": title,
            "msgdesc": message,
            "msgtime": "123",
            "msgtype": msg_type,
            "vibrateoff": "1" if vibrate_off else "0",
        }
        return self._post(path, payload, timeout=timeout)
    
    def send_vibration_and_buzzer(
        self,
        tag_ids: List[int],
        *,
        shake_sdur: int = 5,
        shake_edur: int = 15,
        vibrate_times: int = 1,
        vibrate_dur: int = 6,
        send_counts: int = 1,
        send_interval: int = 1,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """진동 + 부저 함께 전송"""
        path = "/andon/alarm"
        payload = {
            "tag_ids": tag_ids,
            "shake_sdur": shake_sdur,
            "shake_edur": shake_edur,
            "vibrate_times": vibrate_times,
            "vibrate_dur": vibrate_dur,
            "send_counts": send_counts,
            "send_interval": send_interval,
        }
        return self._post(path, payload, timeout=timeout)
