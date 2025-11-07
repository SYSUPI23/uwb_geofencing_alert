# 🎯 UWB Geofencing Alert System

> Real-time UWB geofencing system with buzzer alerts using FastAPI and LocalSense

FastAPI 기반 실시간 UWB 지오펜싱 시스템입니다. LocalSense UWB에서 WebSocket으로 태그 위치를 실시간 수신하여 위험 구역 진입을 감지하고, 자동으로 부저/진동 알림을 전송합니다.

[![Python](https://img.shields.io/badge/Python-3.14+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 시스템 구조

```
[UWB 위치엔진] --WebSocket(0x81)--> [FastAPI 서버] --> [지오펜싱 AI]
                                          |                    |
                                          |              [알림 전송]
                                          |
                                    --WebSocket-->
                                          |
                                    [대시보드]
```

## 주요 기능

- ✅ **FastAPI 웹 서버** (REST API + WebSocket)
- ✅ **WebSocket 실시간 위치 수신** (0x81 프레임 파싱)
- ✅ **Shapely 기반 정밀 지오펜싱** (산업 표준 알고리즘)
- ✅ **직사각형 위험 구역** 정의 및 진입 감지 (좌하단 + 우상단 좌표)
- ✅ **LocalSense API 연동** (부저, 진동, 디스플레이 메시지)
- ✅ **대시보드 실시간 연동** (WebSocket 스트리밍)
- ✅ **REST API 제공** (상태 조회, 위치 조회)
- ✅ **재트리거 방지** (쿨다운 설정 가능)

## 기술 스택

- **Python 3.14+**
- **FastAPI**: REST API 및 WebSocket 서버
- **Uvicorn**: ASGI 웹 서버
- **WebSockets**: UWB 데이터 수신
- **Shapely**: 산업 표준 지오메트리 라이브러리
- **LocalSense API**: UWB 태그 제어
- **asyncio**: 비동기 처리

---

## 설치 방법

### 1. 가상환경 활성화
```bash
C:\Users\USER\venvs\myapi\Scripts\activate
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

**주요 패키지:**
- `fastapi>=0.104.0` - FastAPI 웹 프레임워크
- `uvicorn[standard]>=0.24.0` - ASGI 서버
- `websockets>=12.0` - WebSocket 클라이언트
- `shapely>=2.0.0` - 지오메트리 계산
- `requests>=2.31.0` - HTTP API 호출
- `python-dotenv>=1.0.0` - 환경 변수 관리

---

## 설정

`config/main.env` 파일에서 설정을 변경할 수 있습니다:

```env
# 지오펜싱 설정
RETRIGGER_AFTER_SEC=10         # 재트리거 간격 (초, 0=즉시)
TARGET_TAG_ID=1564130          # 감지 대상 태그 ID

# 위험구역 설정 (직사각형)
DANGER_ZONE_MIN_X=3.86         # 위험구역 좌하단 X 좌표 (m)
DANGER_ZONE_MIN_Y=0            # 위험구역 좌하단 Y 좌표 (m)
DANGER_ZONE_MAX_X=5.7          # 위험구역 우상단 X 좌표 (m)
DANGER_ZONE_MAX_Y=1.3          # 위험구역 우상단 Y 좌표 (m)
DANGER_ZONE_NAME=위험구역1      # 위험구역 이름

# LocalSense WebSocket (실시간 위치 수신)
LOCALSENSE_WS_HOST=192.168.1.11
LOCALSENSE_WS_PORT=48300
LOCALSENSE_WS_USERNAME=admin
LOCALSENSE_WS_PASSWORD=doublt1!

# LocalSense Alarm API (부저/진동)
LOCALSENSE_ALARM_HOST=127.0.0.1
LOCALSENSE_ALARM_PORT=48400
LOCALSENSE_SECRET_KEY=16CusxZhMzwSl08zQVxHvCC4mQ3376cJ
```

---

## ⚙️ 설정 변경 방법

### 🎯 중요: IP나 설정을 바꾸려면?

**답변: `config/main.env` 파일만 수정하세요!**

- ✅ **수정할 파일**: `config/main.env` (여기만 바꾸면 됨!)
- ❌ **수정하지 말 것**: `config/settings.py` (코드 파일, 읽기 전용)

`settings.py`는 단순히 `main.env`의 값을 읽어오는 역할만 합니다. **모든 설정은 `main.env`에서만 관리됩니다!**

> 💡 `main.env`에 필수 설정이 없으면 프로그램이 명확한 에러 메시지를 보여줍니다.

---

## 위험 구역 설정

`config/main.env` 파일에서 직사각형 위험 구역을 설정할 수 있습니다.

### 예시: 직사각형 구역 (3.86, 0) ~ (5.7, 1.3)
```env
DANGER_ZONE_MIN_X=3.86         # 좌하단 X 좌표
DANGER_ZONE_MIN_Y=0            # 좌하단 Y 좌표
DANGER_ZONE_MAX_X=5.7          # 우상단 X 좌표
DANGER_ZONE_MAX_Y=1.3          # 우상단 Y 좌표
DANGER_ZONE_NAME=위험구역1      # 구역 이름
```

### 위험구역 시각화
```
      (3.86, 1.3) -------- (5.7, 1.3)
           |                    |
           |   위험구역1         |
           |                    |
      (3.86, 0.0) -------- (5.7, 0.0)
```

### Zone 파라미터 설명
- `min_x`: 직사각형 좌하단 X 좌표 (m)
- `min_y`: 직사각형 좌하단 Y 좌표 (m)
- `max_x`: 직사각형 우상단 X 좌표 (m)
- `max_y`: 직사각형 우상단 Y 좌표 (m)
- `name`: 구역 이름 (로그 및 API 응답에 표시됨)

**참고:** 현재는 1개의 직사각형 위험구역만 지원합니다. 여러 개가 필요하면 `main.py`의 `DANGER_ZONES` 리스트에 추가하세요.

**💡 Shapely는 4개의 좌표로 Polygon을 생성하여 매우 정확하게 포함 관계를 체크합니다!**

---

## 실행 방법

### 방법 1: Python으로 직접 실행
```bash
python main.py
```

서버가 `http://0.0.0.0:8000`에서 시작됩니다.

### 방법 2: Uvicorn으로 실행 (개발 모드)
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**개발 모드 특징:**
- `--reload`: 코드 변경 시 자동 재시작
- `--host 0.0.0.0`: 모든 네트워크 인터페이스에서 접근 가능
- `--port 8000`: 포트 번호 지정

---

## 예상 출력

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
============================================================
🚀 UWB 지오펜싱 알림 시스템 시작 (FastAPI)
============================================================
📍 타겟 태그: 1564130
🔌 WebSocket: 127.0.0.1:48300
🔔 알람 API: 127.0.0.1:48400
============================================================
✅ GeofencingService 초기화 완료 (Shapely 기반)
   - 위험구역 수: 1
   - 위험구역1: (3.860, 0.000) ~ (5.700, 1.300)
🔌 Connecting to ws://127.0.0.1:48300
✅ WebSocket connected successfully
🔐 Authentication successful
👀 실시간 위치 수신 시작 (타겟 태그: 1564130)...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 위험 구역 진입 시
```
🎯 [Shapely] 태그 1564130 구역 '위험구역1' 진입 확인!
   - 좌표: (4.370, 7.410)
   - 경계까지 거리: 0.000m (0이면 내부)
🚨 [경고] 태그 1564130 위험구역 '위험구역1' 진입! 위치: (4.37, 7.41)
✅ 디스플레이 메시지 전송 성공
✅ 부저+진동 전송 성공
```

---

## API 엔드포인트

### REST API

#### 1. 헬스 체크
```
GET /
```

**응답:**
```json
{
  "status": "running",
  "service": "UWB Geofencing Alert System",
  "version": "1.0.0"
}
```

#### 2. 시스템 상태 조회
```
GET /api/status
```

**응답:**
```json
{
  "uwb_connected": true,
  "total_received": 1234,
  "dashboard_clients": 1,
  "target_tag_id": 1564130,
  "zones": [...],
  "latest_positions": {
    "1564130": {"x": 4.37, "y": 7.41}
  }
}
```

#### 3. 위험 구역 목록 조회
```
GET /api/zones
```

**응답:**
```json
{
  "zones": [
    {
      "name": "위험구역1",
      "min_x": 3.37,
      "min_y": 6.41,
      "max_x": 5.37,
      "max_y": 8.41,
      "center": {"x": 4.37, "y": 7.41},
      "corners": [...]
    }
  ]
}
```

#### 4. 모든 태그 위치 조회
```
GET /api/positions
```

**응답:**
```json
{
  "positions": {
    "1564130": {"x": 4.37, "y": 7.41}
  }
}
```

#### 5. 특정 태그 위치 조회
```
GET /api/tags/{tag_id}/position
```

**응답:**
```json
{
  "tag_id": 1564130,
  "x": 4.37,
  "y": 7.41
}
```

---

### WebSocket API (대시보드용)

#### 연결
```
WS /ws/dashboard
```

#### 메시지 타입

**1. 초기 상태 (연결 시 자동 전송)**
```json
{
  "type": "initial_state",
  "zones": [...],
  "positions": {...}
}
```

**2. 위치 업데이트**
```json
{
  "type": "position_update",
  "tag_id": 1564130,
  "x": 4.37,
  "y": 7.41,
  "battery": 95,
  "timestamp": 1699234567890,
  "in_danger_zone": false
}
```

**3. 알림 이벤트**
```json
{
  "type": "alert",
  "tag_id": 1564130,
  "zone_name": "위험구역1",
  "position": {"x": 4.37, "y": 7.41},
  "timestamp": 1699234567890
}
```

---

## 대시보드 연동 예시 (JavaScript)

```javascript
// WebSocket 연결
const ws = new WebSocket('ws://localhost:8000/ws/dashboard');

// 연결 성공
ws.onopen = () => {
    console.log('✅ 대시보드 연결 성공');
};

// 메시지 수신
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'initial_state') {
        // 초기 상태: 위험 구역 및 현재 위치 표시
        console.log('초기 상태:', data);
        renderZones(data.zones);
        renderPositions(data.positions);
    }
    else if (data.type === 'position_update') {
        // 위치 업데이트: 태그 위치 갱신
        updateTagPosition(data.tag_id, data.x, data.y);
        
        if (data.in_danger_zone) {
            highlightTag(data.tag_id, 'red');
        }
    }
    else if (data.type === 'alert') {
        // 알림: 경고 표시
        showAlert(`태그 ${data.tag_id} 위험구역 진입!`);
    }
};

// 연결 종료
ws.onclose = () => {
    console.log('❌ 대시보드 연결 종료');
};

// REST API 호출 예시
async function getStatus() {
    const response = await fetch('http://localhost:8000/api/status');
    const data = await response.json();
    console.log('시스템 상태:', data);
}
```

---

## 프로젝트 구조

```
geofencing_buzzer_doublt4/
│
├── main.py                      # FastAPI 메인 서버
├── requirements.txt             # Python 의존성
├── README.md                    # 프로젝트 문서
├── .gitignore                   # Git 무시 파일
│
├── config/                      # 설정 파일
│   ├── __init__.py
│   ├── settings.py              # 설정 로드
│   └── main.env                 # 환경 변수
│
└── services/                    # 서비스 모듈
    ├── __init__.py
    ├── geofencing_service.py    # Shapely 기반 지오펜싱 로직
    └── localsense_api.py        # LocalSense API 클라이언트
```

---

## 핵심 로직 설명

### 1. FastAPI 라이프사이클 관리

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시
    # - LocalSense API 초기화
    # - 지오펜싱 서비스 초기화
    # - UWB WebSocket 연결
    # - 백그라운드에서 데이터 수신 시작
    asyncio.create_task(uwb_collector.collect_realtime_data())
    
    yield
    
    # 앱 종료 시
    # - WebSocket 연결 종료
```

### 2. 백그라운드 데이터 수신

```python
async def collect_realtime_data(self):
    while self.running:
        # WebSocket에서 데이터 수신
        data = await self.websocket.recv()
        
        # 0x81 프레임 파싱
        tags = self._parse_tag_location_data(data)
        
        # 지오펜싱 처리
        alerts = geofencing.process_positions(positions)
        
        # 알림 전송 (부저/진동)
        await self._send_alert(alert_info)
        
        # 대시보드에 실시간 전송
        await self._broadcast_to_dashboard(message)
```

### 3. Shapely 기반 지오펜싱

```python
# services/geofencing_service.py
from shapely.geometry import Point, Polygon

# 직사각형 Polygon 생성
polygon = Polygon([
    (min_x, min_y),  # 좌하단
    (max_x, min_y),  # 우하단
    (max_x, max_y),  # 우상단
    (min_x, max_y),  # 좌상단
])

# 포함 관계 체크 (산업 표준 알고리즘)
point = Point(x, y)
is_inside = polygon.contains(point) or polygon.touches(point)
```

---

## 문제 해결

### WebSocket 연결 실패
```
❌ Connection failed: timed out
```
**원인**: 다른 프로그램이 이미 WebSocket 연결 중 (LocalSense는 1개만 허용)

**해결**:
1. DB 저장 프로그램 종료
2. 웹 대시보드 닫기
3. Chrome에서 LocalSense 웹 UI 닫기

**확인**:
```bash
netstat -ano | findstr :48300
```

### 알람 API 실패 (404 error)
```
❌ 부저+진동 실패: 404 page not found
```
**원인**: SECRET_KEY가 잘못되었거나 API 서버가 실행 중이지 않음

**해결**:
1. `config/main.env`의 `LOCALSENSE_SECRET_KEY` 확인
2. LocalSense API 서버 실행 확인 (포트 48400)

### 지오펜싱이 작동하지 않음
```
구역 내부인데 알림이 안 울림
```
**원인**: 좌표 범위가 잘못 설정되었거나 태그 ID가 다름

**디버깅**:
1. `main.py`의 `DANGER_ZONES` 좌표 확인
2. `TARGET_TAG_ID`가 실제 태그와 일치하는지 확인
3. Shapely 디버그 로그 확인 (경계까지 거리 출력)

### FastAPI 서버가 시작되지 않음
```
ModuleNotFoundError: No module named 'fastapi'
```
**해결**:
```bash
pip install fastapi uvicorn[standard]
```

---

## 📜 License

This project is licensed under the MIT License.

## 🤝 Contributing

Contributions, issues and feature requests are welcome!

## 👤 Author

**Created**: 2025.11.06  
**Powered by**: FastAPI + LocalSense + Shapely

---

⭐ If you found this project helpful, please consider giving it a star!
