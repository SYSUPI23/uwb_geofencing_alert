"""
UWB 지오펜싱 알림 시스템 (FastAPI 기반)

데이터 흐름:
    1. UWB Tag → WebSocket → FastAPI 서버
    2. 0x81 프레임 파싱 (위치 데이터)
    3. 지오펜싱 처리 (위험구역 체크)
    4. 위험구역 진입 시 부저/진동 알림
    5. WebSocket으로 대시보드에 실시간 전송

작성일: 2025.11.06
"""
import asyncio
import websockets
import struct
import hashlib
import time
import json
from typing import List, Optional, Dict, Tuple, Set
from dataclasses import dataclass
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from services.localsense_api import LocalSenseAPI
from services.geofencing_service import GeofencingService, Zone

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =====================================
# ==== 위험 구역 설정 ====
# =====================================
# 위험구역을 설정에서 로드 (직사각형)
DANGER_ZONES = [
    Zone(
        min_x=settings.DANGER_ZONE_MIN_X,
        min_y=settings.DANGER_ZONE_MIN_Y,
        max_x=settings.DANGER_ZONE_MAX_X,
        max_y=settings.DANGER_ZONE_MAX_Y,
        name=settings.DANGER_ZONE_NAME
    ),
]


# =====================================
# ==== 데이터 모델 ====
# =====================================
@dataclass
class TagLocationInfo:
    """태그 위치 정보"""
    tag_id: int
    x_coordinate: float  # m
    y_coordinate: float  # m
    z_coordinate: float  # m
    map_id: int
    battery: int
    sleep_flag: bool
    charging_flag: bool
    timestamp: int
    floor_number: int
    positioning_indication: int
    coordinate_type: str


# =====================================
# ==== 전역 상태 ====
# =====================================
class AppState:
    """앱 전역 상태 관리"""
    def __init__(self):
        self.uwb_collector: Optional['UWBCollector'] = None
        self.geofencing: Optional[GeofencingService] = None
        self.api: Optional[LocalSenseAPI] = None
        self.dashboard_clients: Set[WebSocket] = set()
        self.latest_positions: Dict[int, Tuple[float, float]] = {}
        self.running = False

app_state = AppState()


# =====================================
# ==== UWB 수집기 ====
# =====================================
class UWBCollector:
    """UWB 위치 데이터 수신 (백그라운드)"""
    
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        target_tag_id: int,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.websocket = None
        self.salt = "abcdefghijklmnopqrstuvwxyz20191107salt"
        self.target_tag_id = target_tag_id
        self.running = False
        self.total_received = 0
    
    def _calculate_crc16_modbus(self, data: bytes) -> int:
        """CRC16 MODBUS 체크섬 계산"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def _create_auth_packet(self) -> bytes:
        """인증 패킷 생성"""
        pwd_md5 = hashlib.md5(self.password.encode()).hexdigest()
        salt_pwd = hashlib.md5((pwd_md5 + self.salt).encode()).hexdigest()
        
        frame_header = struct.pack('>H', 0xCC5F)
        frame_type = struct.pack('B', 0x27)
        username_len = struct.pack('>I', len(self.username))
        username_bytes = self.username.encode()
        password_len = struct.pack('>I', len(salt_pwd))
        password_bytes = salt_pwd.encode()
        
        crc_data = frame_type + username_len + username_bytes + password_len + password_bytes
        crc = self._calculate_crc16_modbus(crc_data)
        crc_bytes = struct.pack('>H', crc)
        frame_tail = struct.pack('>H', 0xAABB)
        
        return frame_header + crc_data + crc_bytes + frame_tail
    
    def _parse_tag_location_data(self, data: bytes) -> List[TagLocationInfo]:
        """태그 위치 데이터 파싱 (0x81, 0xB4, 0xB5)"""
        if len(data) < 5:
            return []
        
        try:
            header = struct.unpack('>H', data[0:2])[0]
            frame_type = data[2]
            
            if header != 0xCC5F:
                return []
            
            # 좌표 타입 결정
            if frame_type == 0x81:
                coordinate_type = "relative"
            elif frame_type == 0xB4:
                coordinate_type = "longitude_latitude"
            elif frame_type == 0xB5:
                coordinate_type = "global"
            else:
                return []
            
            num_tags = data[3]
            if num_tags == 0:
                return []
            
            expected_size = 4 + (num_tags * 23) + 4
            if len(data) < expected_size:
                return []
            
            tags = []
            offset = 4
            
            for _ in range(num_tags):
                if offset + 23 > len(data) - 4:
                    break
                
                tag_id = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4
                
                x_coord = struct.unpack('>i', data[offset:offset+4])[0]
                offset += 4
                
                y_coord = struct.unpack('>i', data[offset:offset+4])[0]
                offset += 4
                
                z_coord = struct.unpack('>h', data[offset:offset+2])[0]
                offset += 2
                
                map_id = data[offset]
                offset += 1
                
                battery = data[offset]
                offset += 1
                
                sleep_charge_flag = data[offset]
                sleep_flag = bool((sleep_charge_flag >> 4) & 0x0F)
                charging_flag = bool(sleep_charge_flag & 0x0F)
                offset += 1
                
                timestamp = struct.unpack('>I', data[offset:offset+4])[0]
                offset += 4
                
                floor_number = data[offset]
                offset += 1
                
                positioning_indication = data[offset]
                offset += 1
                
                # 좌표 변환
                if frame_type == 0xB4:
                    x_coord = x_coord / 10000000.0
                    y_coord = y_coord / 10000000.0
                    z_coord = 0
                else:
                    # cm → m 변환
                    x_coord = x_coord / 100.0
                    y_coord = y_coord / 100.0
                    z_coord = z_coord / 100.0
                
                tag_info = TagLocationInfo(
                    tag_id=tag_id,
                    x_coordinate=x_coord,
                    y_coordinate=y_coord,
                    z_coordinate=z_coord,
                    map_id=map_id,
                    battery=battery,
                    sleep_flag=sleep_flag,
                    charging_flag=charging_flag,
                    timestamp=timestamp,
                    floor_number=floor_number,
                    positioning_indication=positioning_indication,
                    coordinate_type=coordinate_type
                )
                
                tags.append(tag_info)
            
            return tags
            
        except Exception as e:
            logger.error(f"⚠️ 파싱 오류: {e}")
            return []
    
    async def _process_location_update(self, tags: List[TagLocationInfo]):
        """위치 업데이트 처리 (지오펜싱 + 대시보드 전송)"""
        # 타겟 태그만 필터링 (0이면 모든 태그)
        if self.target_tag_id == 0:
            target_tags = tags  # 모든 태그 허용
        else:
            target_tags = [t for t in tags if t.tag_id == self.target_tag_id]
        
        if not target_tags:
            return
        
        for tag in target_tags:
            # 최신 위치 저장
            app_state.latest_positions[tag.tag_id] = (tag.x_coordinate, tag.y_coordinate)
            
            # 지오펜싱 처리
            positions = {tag.tag_id: (tag.x_coordinate, tag.y_coordinate)}
            alerts = app_state.geofencing.process_positions(positions)
            
            # 알림 전송
            for alert_info in alerts:
                await self._send_alert(alert_info)
            
            # 대시보드에 실시간 전송
            await self._broadcast_to_dashboard({
                "type": "position_update",
                "tag_id": tag.tag_id,
                "x": tag.x_coordinate,
                "y": tag.y_coordinate,
                "battery": tag.battery,
                "timestamp": tag.timestamp,
                "in_danger_zone": len(alerts) > 0
            })
    
    async def _send_buzzer_vibration(self, tag_id: int):
        """별도 WebSocket으로 부저/진동 제어"""
        try:
            logger.info(f"📡 부저/진동 WebSocket 연결 시작...")
            
            # 제어용 WebSocket 연결 (인증 없음)
            control_ws = await websockets.connect(
                f"ws://{self.host}:{self.port}/",
                subprotocols=["localSense-Json"]
            )
            
            # 진동/부저 시작 (enable)
            request_enable = {
                "localsense_conf_request": {
                    "conf_type": "tagvibrateandshake",
                    "conf_value": "enable",
                    "tagid": str(tag_id)
                }
            }
            await control_ws.send(json.dumps(request_enable))
            logger.info(f"✅ 태그 {tag_id} 진동/부저 시작")
            
            # 1초 대기
            await asyncio.sleep(1)
            
            # 진동/부저 중지 (disable)
            request_disable = {
                "localsense_conf_request": {
                    "conf_type": "tagvibrateandshake",
                    "conf_value": "disable",
                    "tagid": str(tag_id)
                }
            }
            await control_ws.send(json.dumps(request_disable))
            logger.info(f"⏹ 태그 {tag_id} 진동/부저 중지")
            
            # 연결 종료
            await control_ws.close()
            
        except Exception as e:
            logger.error(f"❌ 알람 전송 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _send_alert(self, alert_info: dict):
        """알림 전송 (부저/진동/디스플레이)"""
        tag_id = alert_info["tag_id"]
        zone = alert_info["zone"]
        x, y = alert_info["position"]
        
        logger.info(f"🚨 [경고] 태그 {tag_id} 위험구역 '{zone.name}' 진입! 위치: ({x:.2f}, {y:.2f})")
        
        # 부저/진동 전송
        await self._send_buzzer_vibration(tag_id)
        
        # 대시보드에 알림 전송
        await self._broadcast_to_dashboard({
            "type": "alert",
            "tag_id": tag_id,
            "zone_name": zone.name,
            "position": {"x": x, "y": y},
            "timestamp": int(time.time() * 1000)
        })
    
    async def _broadcast_to_dashboard(self, message: dict):
        """대시보드 클라이언트에게 메시지 브로드캐스트"""
        disconnected = set()
        for client in app_state.dashboard_clients:
            try:
                await client.send_json(message)
            except:
                disconnected.add(client)
        
        # 연결 끊긴 클라이언트 제거
        app_state.dashboard_clients -= disconnected
    
    async def connect(self):
        """WebSocket 연결"""
        try:
            logger.info(f"🔌 Connecting to ws://{self.host}:{self.port}")
            self.websocket = await websockets.connect(
                f"ws://{self.host}:{self.port}",
                subprotocols=['localSensePush-protocol'],
                ping_interval=30,
                ping_timeout=10
            )
            logger.info("✅ WebSocket connected successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    async def authenticate(self):
        """인증"""
        if not self.websocket:
            return False
        
        try:
            auth_packet = self._create_auth_packet()
            await self.websocket.send(auth_packet)
            await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            logger.info("🔐 Authentication successful")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Authentication: {e}")
            return True
    
    async def collect_realtime_data(self):
        """실시간 위치 데이터 수신"""
        if not self.websocket:
            return
        
        tag_info = "모든 태그" if self.target_tag_id == 0 else str(self.target_tag_id)
        logger.info(f"👀 실시간 위치 수신 시작 (타겟 태그: {tag_info})...")
        
        self.running = True
        
        try:
            while self.running:
                try:
                    # WebSocket에서 데이터 수신
                    data = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    
                    # 태그 위치 파싱
                    tags = self._parse_tag_location_data(data)
                    
                    if tags:
                        self.total_received += len(tags)
                        # 지오펜싱 처리
                        await self._process_location_update(tags)
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"⚠️ 수신 오류: {e}")
                    continue
        
        finally:
            self.running = False
    
    async def disconnect(self):
        """WebSocket 연결 종료"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("🔌 WebSocket disconnected")
        logger.info(f"📊 총 수신: {self.total_received}개")


# =====================================
# ==== FastAPI 앱 생성 ====
# =====================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 컨텍스트 매니저"""
    # 시작
    logger.info("="*60)
    logger.info("🚀 UWB 지오펜싱 알림 시스템 시작 (FastAPI)")
    logger.info("="*60)
    tag_display = "모든 태그" if settings.TARGET_TAG_ID == 0 else settings.TARGET_TAG_ID
    logger.info(f"📍 타겟 태그: {tag_display}")
    logger.info(f"🔌 WebSocket: {settings.LOCALSENSE_WS_HOST}:{settings.LOCALSENSE_WS_PORT}")
    logger.info(f"🔔 알람 API: {settings.LOCALSENSE_ALARM_HOST}:{settings.LOCALSENSE_ALARM_PORT}")
    logger.info("="*60)
    
    # LocalSense API 초기화
    app_state.api = LocalSenseAPI.from_host(
        ip=settings.LOCALSENSE_ALARM_HOST,
        port=settings.LOCALSENSE_ALARM_PORT,
        secret_key=settings.LOCALSENSE_SECRET_KEY
    )
    
    # 지오펜싱 서비스 초기화 (retrigger_after_sec은 자동으로 설정값 사용)
    app_state.geofencing = GeofencingService(
        zones=DANGER_ZONES
    )
    
    # UWB 수집기 초기화
    app_state.uwb_collector = UWBCollector(
        host=settings.LOCALSENSE_WS_HOST,
        port=settings.LOCALSENSE_WS_PORT,
        username=settings.LOCALSENSE_WS_USERNAME,
        password=settings.LOCALSENSE_WS_PASSWORD,
        target_tag_id=settings.TARGET_TAG_ID,
    )
    
    # WebSocket 연결 (재시도 로직)
    max_retries = 3
    retry_delay = 5  # 초
    
    for attempt in range(1, max_retries + 1):
        logger.info(f"🔄 WebSocket 연결 시도 {attempt}/{max_retries}...")
        if await app_state.uwb_collector.connect():
            # 인증 수행
            await app_state.uwb_collector.authenticate()
            logger.info("🔓 인증 성공!")
            # 백그라운드에서 데이터 수신 시작
            asyncio.create_task(app_state.uwb_collector.collect_realtime_data())
            break
        elif attempt < max_retries:
            logger.info(f"⏳ {retry_delay}초 후 재시도...")
            await asyncio.sleep(retry_delay)
        else:
            logger.error("❌ WebSocket 연결 실패 - UWB 장비를 확인하세요")
            logger.warning("⚠️  서버는 계속 실행되지만 위치 데이터를 받을 수 없습니다")
    
    yield
    
    # 종료
    logger.info("🛑 시스템 종료 중...")
    if app_state.uwb_collector:
        await app_state.uwb_collector.disconnect()


app = FastAPI(
    title="UWB 지오펜싱 알림 시스템",
    description="실시간 UWB 위치 데이터 수신 및 지오펜싱 처리",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정 (대시보드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================
# ==== REST API 엔드포인트 ====
# =====================================
@app.get("/")
async def root():
    """헬스 체크"""
    return {
        "status": "running",
        "service": "UWB Geofencing Alert System",
        "version": "1.0.0"
    }


@app.get("/api/status")
async def get_status():
    """시스템 상태 조회"""
    return {
        "uwb_connected": app_state.uwb_collector.running if app_state.uwb_collector else False,
        "total_received": app_state.uwb_collector.total_received if app_state.uwb_collector else 0,
        "dashboard_clients": len(app_state.dashboard_clients),
        "target_tag_id": settings.TARGET_TAG_ID,
        "zones": app_state.geofencing.get_status()["zones"] if app_state.geofencing else [],
        "latest_positions": {
            tag_id: {"x": pos[0], "y": pos[1]}
            for tag_id, pos in app_state.latest_positions.items()
        }
    }


@app.get("/api/zones")
async def get_zones():
    """위험 구역 목록 조회"""
    if not app_state.geofencing:
        return {"zones": []}
    return {"zones": app_state.geofencing.get_status()["zones"]}


@app.get("/api/positions")
async def get_positions():
    """모든 태그의 최신 위치 조회"""
    return {
        "positions": {
            tag_id: {"x": pos[0], "y": pos[1]}
            for tag_id, pos in app_state.latest_positions.items()
        }
    }


@app.get("/api/tags/{tag_id}/position")
async def get_tag_position(tag_id: int):
    """특정 태그의 위치 조회"""
    pos = app_state.latest_positions.get(tag_id)
    if pos:
        return {"tag_id": tag_id, "x": pos[0], "y": pos[1]}
    return JSONResponse(
        status_code=404,
        content={"error": f"Tag {tag_id} not found"}
    )


# =====================================
# ==== WebSocket 엔드포인트 (대시보드용) ====
# =====================================
@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """대시보드 실시간 연결"""
    await websocket.accept()
    app_state.dashboard_clients.add(websocket)
    logger.info(f"📱 대시보드 클라이언트 연결 (총 {len(app_state.dashboard_clients)}개)")
    
    try:
        # 초기 상태 전송
        await websocket.send_json({
            "type": "initial_state",
            "zones": app_state.geofencing.get_status()["zones"] if app_state.geofencing else [],
            "positions": {
                tag_id: {"x": pos[0], "y": pos[1]}
                for tag_id, pos in app_state.latest_positions.items()
            }
        })
        
        # 연결 유지 (메시지 수신 대기)
        while True:
            data = await websocket.receive_text()
            # 클라이언트에서 메시지 보내면 처리 (필요 시)
    
    except WebSocketDisconnect:
        app_state.dashboard_clients.discard(websocket)
        logger.info(f"📱 대시보드 클라이언트 연결 해제 (남은 {len(app_state.dashboard_clients)}개)")


# =====================================
# ==== 메인 실행 ====
# =====================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
