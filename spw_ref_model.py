#!/usr/bin/env python3
"""
spw_ref_model.py — SpaceWire 골든모델 (ECSS-E-ST-50-12C Rev.1)

이 파일은 "검증 완료"가 아니라 "검증 시작점"입니다. 함수별 신뢰도는
spec_harness/spec_harness.db의 golden_model_confidence 테이블에 기록되어 있습니다.

현재 범위: §5.4 Encoding layer (draft-golden-model 1차 초안)
"""

# ============================================================
# §5.4.3 Character and control code encoding
# ============================================================

CONTROL_TYPE_CODE = {
    # Spec: §5.4.3.2.c-f — 2비트 control type 값
    "FCT": 0b00,
    "EEP": 0b01,
    "EOP": 0b10,
    "ESC": 0b11,
}
CONTROL_TYPE_NAME = {v: k for k, v in CONTROL_TYPE_CODE.items()}


def byte_to_bits_lsb_first(value: int, width: int) -> list[int]:
    # Spec: §5.4.3.1.c — "transmitted least significant bit first"
    if not (0 <= value < (1 << width)):
        raise ValueError(f"value {value} out of range for width {width}")
    return [(value >> i) & 1 for i in range(width)]


def encode_data_character(byte: int) -> dict:
    # Spec: §5.4.3.1 — 데이터 문자는 10비트(parity + D/C=0 + data 8bit LSB first)
    if not (0 <= byte <= 0xFF):
        raise ValueError("data character must be 0-255")
    return {"dc_flag": 0, "payload_bits": byte_to_bits_lsb_first(byte, 8)}


def encode_control_character(control_type: str) -> dict:
    # Spec: §5.4.3.2 — 제어 문자는 4비트(parity + D/C=1 + 2비트 control type)
    # 주의(assumed): control type 2비트의 전송 비트 순서는 스펙에 명시가 없어
    # 데이터 문자와 동일하게 LSB first로 가정함 — 확인 필요.
    if control_type not in CONTROL_TYPE_CODE:
        raise ValueError(f"unknown control type: {control_type}")
    code = CONTROL_TYPE_CODE[control_type]
    return {"dc_flag": 1, "payload_bits": byte_to_bits_lsb_first(code, 2)}


def encode_null() -> list[dict]:
    # Spec: §5.4.3.3.b — Null = ESC + FCT
    return [encode_control_character("ESC"), encode_control_character("FCT")]


def encode_broadcast_code(type_field: int, value_field: int) -> list[dict]:
    # Spec: §5.4.3.3.c,d — Broadcast code = ESC + data character
    # data character의 상위 2비트(B7:6)=type, 하위 6비트(B5:0)=value
    if not (0 <= type_field <= 0b11):
        raise ValueError("type_field must be 2 bits (0-3)")
    if not (0 <= value_field <= 0b111111):
        raise ValueError("value_field must be 6 bits (0-63)")
    byte = (type_field << 6) | value_field
    return [encode_control_character("ESC"), encode_data_character(byte)]


# ============================================================
# §5.4.3.4 / §5.4.5 / §5.4.7 — Parity
# ============================================================

def compute_next_parity(prev_payload_bits: list[int], current_dc_flag: int) -> int:
    # Spec: §5.4.3.4 — 패리티 비트는 "이전 문자의 payload 비트(8bit 데이터 또는
    # 2bit 제어타입) + 현재 parity 비트 자신 + 현재 D/C 플래그"를 커버하는 odd parity.
    # P 자신이 커버 대상에 포함되므로, P를 뺀 나머지 비트의 1의 개수가 짝수면 P=1,
    # 홀수면 P=0 이 되어야 전체(포함 P)가 홀수가 된다.
    ones = sum(prev_payload_bits) + current_dc_flag
    return 0 if ones % 2 == 1 else 1


def first_null_parity() -> int:
    # Spec: §5.4.5.a — 리셋 후 최초로 전송되는 Null의 첫 parity 비트는 무조건 0
    # (이전 문자가 없어 §5.4.3.4의 일반 공식을 적용할 수 없는 예외 케이스)
    return 0


def check_parity(prev_payload_bits: list[int], current_dc_flag: int, received_parity_bit: int) -> bool:
    # Spec: §5.4.7.b — "parity is not odd" 이면 에러. 반환값 True = 정상(홀수 parity)
    total_ones = sum(prev_payload_bits) + current_dc_flag + received_parity_bit
    return total_ones % 2 == 1


class SerialEncoder:
    """Spec: §5.4.3.4, §5.4.5 — 문자 단위 패리티 체인을 유지하며 직렬화."""

    def __init__(self):
        self._prev_payload_bits: list[int] | None = None

    def reset(self) -> None:
        # Spec: §5.4.4.b와 별개로, 패리티 체인 자체의 리셋 상태를 표현.
        self._prev_payload_bits = None

    def encode(self, symbol: dict, is_first_null: bool = False) -> dict:
        dc_flag = symbol["dc_flag"]
        payload_bits = symbol["payload_bits"]
        if self._prev_payload_bits is None:
            if not is_first_null:
                # Spec: §5.4.5.a — 리셋 후 첫 심볼은 반드시 Null이어야 함
                raise ValueError("리셋 후 첫 심볼은 Null이어야 함 (Spec: §5.4.5)")
            parity = first_null_parity()
        else:
            parity = compute_next_parity(self._prev_payload_bits, dc_flag)
        self._prev_payload_bits = payload_bits
        return {"parity": parity, "dc_flag": dc_flag, "payload_bits": payload_bits}


# ============================================================
# §5.4.4 Data strobe encoding and decoding
# ============================================================

def encode_data_strobe(bitstream: list[int]) -> tuple[list[int], list[int]]:
    # Spec: §5.4.4.a — Data는 비트값을 그대로 따르고, Strobe는 Data가 이전 비트와
    # 같은 값을 유지할 때마다 상태를 바꾼다. §5.4.4.b — 전원 인가 리셋 시 Data=0, Strobe=0.
    data_signal: list[int] = []
    strobe_signal: list[int] = []
    prev_data = 0
    prev_strobe = 0
    for bit in bitstream:
        data_signal.append(bit)
        if bit == prev_data:
            strobe = 1 - prev_strobe
        else:
            strobe = prev_strobe
        strobe_signal.append(strobe)
        prev_data, prev_strobe = bit, strobe
    return data_signal, strobe_signal


def reset_data_strobe_lines(*_args, **_kwargs):
    # Spec: §5.4.4.c,d,e — ErrorReset 진입 시 Data/Strobe를 리셋하되 동시 전이를
    # 피하기 위한 지연(delay)이 필요함. 지연 값은 "500ns ~ 구현별 최대 송신 비트 주기"
    # 범위로만 규정되어 구체적인 알고리즘/값이 확정되지 않음.
    # 이 골든모델은 아직 시간/클럭 모델을 갖고 있지 않아 이 리셋 시퀀스를 표현할 수 없음.
    raise NotImplementedError(
        "TODO: §5.4.4.c-e 리셋 시 Data/Strobe 지연 시퀀스 미구현 - "
        "시간/클럭 모델 필요, 지연값은 구현 정의 범위(500ns~구현별 최대)라 확인 필요"
    )


# ============================================================
# §5.4.6 Null detection
# ============================================================

class NullDetector:
    """Spec: §5.4.6 — gotNull 조건 검출."""

    # Spec: §5.4.6.d NOTE 1 — 수신 enable 이후 첫 Null의 비트 시퀀스
    FIRST_NULL_BIT_PATTERN = [0, 1, 1, 1, 0, 1, 0, 0, 0]

    def __init__(self):
        self.rx_enabled = False
        self.got_null = False
        self._window: list[int] = []

    def enable_rx(self) -> None:
        # Spec: §5.4.6.a — Null detection은 receiver가 enable될 때마다 활성화
        self.rx_enabled = True
        self.got_null = False
        self._window = []

    def disable_rx(self) -> None:
        # Spec: §5.4.6.b — gotNull은 RX Enable이 de-assert될 때만 클리어됨
        self.rx_enabled = False
        self.got_null = False
        self._window = []

    def feed_bit(self, bit: int) -> bool:
        # Spec: §5.4.6.c,d — enable 이후 첫 Null 관련 3개 parity bit를 포함해 판단
        if not self.rx_enabled or self.got_null:
            return self.got_null
        self._window.append(bit)
        if len(self._window) > len(self.FIRST_NULL_BIT_PATTERN):
            self._window.pop(0)
        if self._window == self.FIRST_NULL_BIT_PATTERN:
            self.got_null = True
        return self.got_null


# ============================================================
# §5.4.7 Parity error / §5.4.9 ESC error
# ============================================================

def is_esc_error(prev_control_type: str, current_control_type: str) -> bool:
    # Spec: §5.4.9.a — ESC 다음에 ESC, EOP, EEP가 오면 무효 시퀀스
    if prev_control_type != "ESC":
        return False
    return current_control_type in ("ESC", "EOP", "EEP")


# ============================================================
# §5.4.8 Disconnect
# ============================================================

def is_disconnect(time_since_last_transition_ns: float, threshold_ns: float = 727) -> bool:
    # Spec: §5.4.8.c — "727ns(10MHz*8cyc+10%) 초과 ~ 1us(10MHz*9cyc-10%) 이내"에서
    # disconnect가 발생해야 함. 정확히 어느 시점에서 트리거할지는 구현 정의 범위이므로
    # threshold_ns를 파라미터화함 (기본값 727ns = 범위의 최솟값).
    # confidence=assumed: 스펙은 "range"만 규정, 단일 임계값은 합리적 추정.
    return time_since_last_transition_ns > threshold_ns


# ============================================================
# §5.4.10 Data signalling rate
# ============================================================

def is_valid_initial_rate(mbps: float) -> bool:
    # Spec: §5.4.10.1.a,b — 리셋/디스커넥트 후 초기 동작 속도는 10 ± 1 Mb/s
    return 9.0 <= mbps <= 11.0


# ============================================================
# §5.4.2 Serialisation / de-serialisation — 수신측 게이팅 로직
# ============================================================

class EncodingLayer:
    """Spec: §5.4.2 — 데이터링크 계층과의 인터페이스 규칙(순서 보장 + 게이팅)."""

    def __init__(self):
        self.transmit_enable = False
        self.receive_enable = False
        self.got_null = False
        self.disconnect = False

    def receive_symbol(self, has_parity_error: bool) -> bool:
        # Spec: §5.4.2.c,d — parity error가 없고, gotNull이 asserted된 이후에만
        # 수신 문자/제어코드를 데이터링크 계층으로 전달
        if not self.receive_enable:
            return False
        if has_parity_error:
            return False
        if not self.got_null:
            return False
        return True
