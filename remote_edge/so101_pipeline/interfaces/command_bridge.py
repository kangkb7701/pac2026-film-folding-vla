import json
from dataclasses import dataclass
from urllib import request
from urllib.error import URLError, HTTPError


# 데모 task 공간: 바나나를 세 바구니 중 하나에 넣는 것뿐이므로,
# 자유 발화에서 색상/물체/동작 키워드만 뽑아 학습된 표준 문장으로 재조립한다.
# 표준 문장은 VLA 학습 문장과 동일해야 하고 parse_pick_place_task 정규식도 통과한다.
CANONICAL_TASKS = {
    "green": "pick the banana and place it in the green basket",
    "yellow": "pick the banana and place it in the yellow basket",
    "blue": "pick the banana and place it in the blue basket",
}

COLOR_KEYWORDS = {
    "green": ("green", "초록", "녹색", "그린"),
    "yellow": ("yellow", "노란", "노랑", "노란색", "옐로"),
    "blue": ("blue", "파란", "파랑", "파란색", "블루", "푸른"),
}

# 학습된 task는 바나나뿐이므로 바나나가 명시된 명령만 수행한다.
# ("당근을 파란 바구니에 넣어줘"가 색상/동사 단서만으로 바나나 task로
#  오변환되어 팔이 움직이는 것을 막는다.)
OBJECT_KEYWORDS = ("banana", "바나나")
ACTION_KEYWORDS = (
    "pick", "place", "put", "move", "grab", "drop",
    "집", "넣", "옮겨", "옮기", "놓", "담", "가져",
)


def normalize_command(command_text):
    """자유 발화(한국어/영어)를 표준 task 문장으로 정규화한다.

    바나나 + 지원 색상 정확히 하나 + 명령 단서(동사 또는 '바구니'/'basket')가
    모두 있어야 변환한다. 그 외("검정 바구니", "당근을 집어줘" 등)는 None을
    반환하고, 호출 측은 해당 명령을 무시하고 다음 명령을 기다려야 한다
    (프로그램 종료 금지). 앱은 None이면 "이해하지 못했어요" 알림을 띄운다.
    """
    text = (command_text or "").strip().lower()
    if not text:
        return None

    matched_colors = [
        color for color, keywords in COLOR_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]
    has_object = any(keyword in text for keyword in OBJECT_KEYWORDS)
    has_action = any(keyword in text for keyword in ACTION_KEYWORDS)
    mentions_basket = "바구니" in text or "basket" in text

    if not has_object:
        return None
    # 색상이 없거나("바나나 집어줘"), 미지원 색이거나("검정 바구니"),
    # 여러 색이 섞이면 명령을 특정할 수 없으므로 거부한다.
    if len(matched_colors) != 1:
        return None
    # "바나나가 초록색이네" 같은 서술문이 명령으로 오인되지 않게
    # 동작 동사나 바구니 언급을 요구한다.
    if not (has_action or mentions_basket):
        return None

    return CANONICAL_TASKS[matched_colors[0]]


@dataclass
class CommandBridgeConfig:
    enabled: bool = False
    endpoint: str = "http://127.0.0.1:8000/command/latest"
    timeout_s: float = 1.0


class UserCommandBridge:
    """Fetches user command text and converts it to task description."""

    def __init__(self, config: CommandBridgeConfig):
        self.config = config
        self._last_rejected = None

    def resolve_task_description(self, fallback: str) -> str:
        if not self.config.enabled:
            return fallback
        text = self._fetch_latest_instruction_text()
        if not text:
            return fallback
        normalized = normalize_command(text)
        if normalized is None:
            if text != self._last_rejected:
                self._last_rejected = text
                print(
                    f"⚠️ 해석할 수 없는 명령이라 무시합니다: '{text}' "
                    "(예: '바나나를 파란 바구니에 넣어줘' / 'put the banana in the blue basket')"
                )
            return fallback
        if normalized != text:
            print(f"🈯 명령 정규화: '{text}' → '{normalized}'")
        return normalized

    def _fetch_latest_instruction_text(self):
        try:
            req = request.Request(self.config.endpoint, method="GET")
            with request.urlopen(req, timeout=self.config.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError, TimeoutError, ValueError):
            return None

        instruction = payload.get("instruction") or {}
        text = instruction.get("text")
        if isinstance(text, str):
            text = text.strip()
        return text or None
