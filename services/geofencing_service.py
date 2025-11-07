"""
지오펜싱 서비스 모듈 (Shapely 기반)
위험 구역 정의 및 진입 감지 로직 - 산업 표준 Shapely 라이브러리 사용
"""
import time
from dataclasses import dataclass
from typing import Dict, Tuple, List, Optional, Callable
from shapely.geometry import Point, Polygon
from config.settings import settings


@dataclass
class Zone:
    """
    직사각형 위험 구역 정의 (Shapely 기반)
    4개의 모서리 좌표로 직사각형 영역을 정의합니다.
    """
    min_x: float  # 좌하단 x 좌표
    min_y: float  # 좌하단 y 좌표
    max_x: float  # 우상단 x 좌표
    max_y: float  # 우상단 y 좌표
    name: str = "danger_zone"
    
    def __post_init__(self):
        """좌표 유효성 검증 및 Shapely Polygon 생성"""
        if self.min_x >= self.max_x:
            raise ValueError(f"min_x({self.min_x})는 max_x({self.max_x})보다 작아야 합니다")
        if self.min_y >= self.max_y:
            raise ValueError(f"min_y({self.min_y})는 max_y({self.max_y})보다 작아야 합니다")
        
        # Shapely Polygon 생성 (시계 반대방향)
        object.__setattr__(self, '_polygon', Polygon([
            (self.min_x, self.min_y),  # 좌하단
            (self.max_x, self.min_y),  # 우하단
            (self.max_x, self.max_y),  # 우상단
            (self.min_x, self.max_y),  # 좌상단
            (self.min_x, self.min_y),  # 좌하단 (닫기)
        ]))
    
    def contains_point(self, x: float, y: float) -> bool:
        """
        Shapely를 사용한 점-다각형 포함 관계 체크
        산업 표준 알고리즘으로 매우 정확함
        """
        point = Point(x, y)
        return self._polygon.contains(point) or self._polygon.touches(point)
    
    def get_center(self) -> Tuple[float, float]:
        """직사각형 중심 좌표 반환"""
        center_x = (self.min_x + self.max_x) / 2
        center_y = (self.min_y + self.max_y) / 2
        return (center_x, center_y)
    
    def get_corners(self) -> List[Tuple[float, float]]:
        """4개의 모서리 좌표 반환 (좌하단부터 시계방향)"""
        return [
            (self.min_x, self.min_y),  # 좌하단
            (self.max_x, self.min_y),  # 우하단
            (self.max_x, self.max_y),  # 우상단
            (self.min_x, self.max_y),  # 좌상단
        ]
    
    def distance_to_point(self, x: float, y: float) -> float:
        """점까지의 최단 거리 계산 (Shapely 기능)"""
        point = Point(x, y)
        return self._polygon.distance(point)


class GeofencingService:
    """지오펜싱 AI - Shapely 기반 위험 구역 진입 감지"""
    
    def __init__(
        self,
        zones: List[Zone],
        *,
        on_danger: Optional[Callable] = None,
        retrigger_after_sec: Optional[float] = None,
        target_tag_ids: Optional[set] = None,
    ):
        """
        Args:
            zones: 위험 구역 리스트 (Zone)
            on_danger: 위험 구역 진입 시 호출될 콜백 함수 (tag_id, zone, position)
            retrigger_after_sec: 동일 이벤트 재트리거 최소 간격(초), None이면 설정값 사용
            target_tag_ids: 감지 대상 태그 ID 집합
        """
        self.zones = list(zones)
        self.on_danger = on_danger
        # retrigger_after_sec이 None이면 설정 파일에서 가져오기
        self.retrigger_after_sec = retrigger_after_sec if retrigger_after_sec is not None else settings.RETRIGGER_AFTER_SEC
        self.target_tag_ids = target_tag_ids
        
        # (tag_id, zone_name) -> last_fired_timestamp
        self._fired: Dict[Tuple[int, str], float] = {}
        
        # 최신 위치 정보 저장
        self.latest_positions: Dict[int, Tuple[float, float]] = {}
        
        print(f"✅ GeofencingService 초기화 완료 (Shapely 기반)")
        print(f"   - 위험구역 수: {len(self.zones)}")
        for zone in self.zones:
            print(f"   - {zone.name}: ({zone.min_x:.3f}, {zone.min_y:.3f}) ~ ({zone.max_x:.3f}, {zone.max_y:.3f})")
    
    def _can_fire(self, key: Tuple[int, str]) -> bool:
        """재트리거 가능 여부 확인"""
        if self.retrigger_after_sec is None:
            return key not in self._fired
        
        last_time = self._fired.get(key)
        if last_time is None:
            return True
        
        return (time.time() - last_time) >= self.retrigger_after_sec
    
    def _mark_fired(self, key: Tuple[int, str]):
        """트리거 시간 기록"""
        self._fired[key] = time.time()
    
    def _clear_if_outside(self, tag_id: int, zone: Zone, pos: Tuple[float, float]):
        """구역을 벗어나면 트리거 상태 해제"""
        x, y = pos
        if not zone.contains_point(x, y):
            key = (tag_id, zone.name)
            self._fired.pop(key, None)
    
    def process_positions(self, positions: Dict[int, Tuple[float, float]]) -> List[Dict]:
        """
        태그 최신 좌표를 받아 위험 구역 진입 여부 평가 (Shapely 기반)
        
        Args:
            positions: {tag_id: (x, y)} 형태의 태그 위치 딕셔너리
        
        Returns:
            알림 목록 [{"tag_id": ..., "zone": ..., "position": ...}, ...]
        """
        # 최신 위치 업데이트
        self.latest_positions.update(positions)
        
        alerts = []
        
        for tag_id, (x, y) in positions.items():
            # 타겟 태그 필터링
            if self.target_tag_ids and (tag_id not in self.target_tag_ids):
                continue
            
            for zone in self.zones:
                # 구역 밖으로 나갔다면 상태 초기화
                self._clear_if_outside(tag_id, zone, (x, y))
                
                # Shapely 기반 구역 진입 감지 (매우 정확!)
                if zone.contains_point(x, y):
                    key = (tag_id, zone.name)
                    if self._can_fire(key):
                        self._mark_fired(key)
                        
                        # 위험구역 진입 감지
                        # distance = zone.distance_to_point(x, y)
                        # print(f"🎯 [Shapely] 태그 {tag_id} 구역 '{zone.name}' 진입 확인!")
                        # print(f"   - 좌표: ({x:.3f}, {y:.3f})")
                        # print(f"   - 경계까지 거리: {distance:.3f}m (0이면 내부)")
                        
                        # 알림 목록에 추가
                        alerts.append({
                            "tag_id": tag_id,
                            "zone": zone,
                            "position": (x, y)
                        })
                        
                        # 경고 콜백 실행 (위치 정보 전달)
                        if self.on_danger:
                            self.on_danger(tag_id, zone, (x, y))
        
        return alerts
    
    def get_status(self) -> Dict:
        """현재 상태 조회 (API용)"""
        return {
            "zones": [
                {
                    "name": z.name,
                    "min_x": z.min_x,
                    "min_y": z.min_y,
                    "max_x": z.max_x,
                    "max_y": z.max_y,
                    "center": {"x": z.get_center()[0], "y": z.get_center()[1]},
                    "corners": [
                        {"x": corner[0], "y": corner[1]}
                        for corner in z.get_corners()
                    ],
                }
                for z in self.zones
            ],
            "tracked_tags": list(self.latest_positions.keys()),
            "latest_positions": {
                tag_id: {"x": pos[0], "y": pos[1]}
                for tag_id, pos in self.latest_positions.items()
            },
        }
