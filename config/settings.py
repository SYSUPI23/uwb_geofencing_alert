"""
설정 관리 모듈
환경 변수를 로드하고 전역 설정 제공

⚠️ 중요: 모든 설정은 config/main.env 파일에서만 관리합니다!
이 파일은 main.env의 값을 읽어오기만 합니다.
"""
import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# config/main.env 파일 로드
BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / "config" / "main.env"

if not ENV_PATH.exists():
    raise FileNotFoundError(f"❌ 설정 파일을 찾을 수 없습니다: {ENV_PATH}")

load_dotenv(ENV_PATH)


def _get_required_env(key: str, value_type=str):
    """필수 환경 변수 가져오기 (없으면 에러)"""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"❌ main.env에 {key} 설정이 필요합니다!")
    
    if value_type == int:
        return int(value)
    elif value_type == float:
        return float(value)
    return value


@dataclass(frozen=True)
class Settings:
    """
    전역 설정 클래스
    
    💡 IP나 설정을 변경하려면 config/main.env만 수정하세요!
    이 파일은 건드릴 필요 없습니다.
    """
    
    # Geofencing
    RETRIGGER_AFTER_SEC: float = _get_required_env("RETRIGGER_AFTER_SEC", float)
    TARGET_TAG_ID: int = _get_required_env("TARGET_TAG_ID", int)
    
    # Danger Zone Settings (Rectangle)
    DANGER_ZONE_MIN_X: float = _get_required_env("DANGER_ZONE_MIN_X", float)
    DANGER_ZONE_MIN_Y: float = _get_required_env("DANGER_ZONE_MIN_Y", float)
    DANGER_ZONE_MAX_X: float = _get_required_env("DANGER_ZONE_MAX_X", float)
    DANGER_ZONE_MAX_Y: float = _get_required_env("DANGER_ZONE_MAX_Y", float)
    DANGER_ZONE_NAME: str = _get_required_env("DANGER_ZONE_NAME")
    
    # LocalSense WebSocket (실시간 위치 수신 - 0x81 프레임)
    LOCALSENSE_WS_HOST: str = _get_required_env("LOCALSENSE_WS_HOST")
    LOCALSENSE_WS_PORT: int = _get_required_env("LOCALSENSE_WS_PORT", int)
    LOCALSENSE_WS_USERNAME: str = _get_required_env("LOCALSENSE_WS_USERNAME")
    LOCALSENSE_WS_PASSWORD: str = _get_required_env("LOCALSENSE_WS_PASSWORD")
    
    # LocalSense Alarm API (부저/진동)
    LOCALSENSE_ALARM_HOST: str = _get_required_env("LOCALSENSE_ALARM_HOST")
    LOCALSENSE_ALARM_PORT: int = _get_required_env("LOCALSENSE_ALARM_PORT", int)
    LOCALSENSE_SECRET_KEY: str = _get_required_env("LOCALSENSE_SECRET_KEY")


# 전역 설정 객체
settings = Settings()
