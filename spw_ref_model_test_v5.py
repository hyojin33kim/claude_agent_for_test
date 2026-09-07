#!/usr/bin/env python3
"""
spw_ref_model_test_v5.py — SpaceWire 골든모델(spw_ref_model.py) Phase A 회귀 테스트

이 파일은 이 프로젝트의 "첫" 테스트 파일입니다 (scenario_id는 1부터 시작).
이전 세션에서 동일한 파일명을 가진, 완전히 무관한 다른 프로젝트(SpWNode/SpWLink
노드-링크 시뮬레이션)의 파일이 실수로 이 디렉토리에 들어와 있었으나 삭제되었습니다.
이 파일은 그 파일과 아무 관련이 없으며, spw_ref_model.py(ECSS-E-ST-50-12C 골든모델)만을
대상으로 합니다.

실행법 (CLAUDE.md §9 회귀 테스트 컨벤션 준수):
    .venv/bin/python3 spw_ref_model_test_v5.py > spec_harness/ingest/last_test_run.log 2>&1
    tail -20 spec_harness/ingest/last_test_run.log

컨벤션:
- 시나리오 함수는 `scenario_NNN_<clause_id 요약>` 형태로 이름 붙이고,
  docstring 첫 줄에 반드시 `clause_id="X.X.X"`를 명시한다.
- "조항 하나당 시나리오 하나" 원칙(원인 추적 용이성)에 따라, 하나의 시나리오 함수
  안에서 여러 개의 경계값/서브케이스를 검증하되 각 서브케이스는 개별적으로
  pass/fail을 리포트한다 (실패 시 어느 서브케이스인지 즉시 식별 가능하도록).
- 시나리오 함수는 SubCaseResult 리스트를 반환한다. main()이 이를 취합해
  전체 PASS/FAIL 카운트를 출력한다.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import spw_ref_model as ref


@dataclass
class SubCaseResult:
    scenario_id: int
    clause_id: str
    subcase: str
    expected: object
    actual: object
    note: str = ""

    @property
    def passed(self) -> bool:
        return self.expected == self.actual

    def report(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        line = (
            f"[{status}] scenario={self.scenario_id} clause={self.clause_id} "
            f"subcase={self.subcase!r} expected={self.expected!r} actual={self.actual!r}"
        )
        if self.note:
            line += f"\n         note: {self.note}"
        return line


# ============================================================
# 헬퍼: §5.4.8.c "the length of time since the last transition on
# either the Data or Strobe line" 를 재구성하기 위한 테스트 전용 헬퍼.
#
# 주의: spw_ref_model.py의 is_disconnect()는 이미 계산된
# "마지막 전이 이후 경과 시간(time_since_last_transition_ns)"을 인자로
# 받는 stateless 함수이며, Data/Strobe 두 라인의 개별 전이 이력을 직접
# 추적하지 않는다. 즉 "어느 라인의 전이를 기준점으로 삼을지"를 올바르게
# 계산하는 책임은 전적으로 호출자(caller) 쪽에 있고, 골든모델 자체는
# 이 계산 로직을 갖고 있지 않다 — 이는 골든모델의 커버리지 공백이며
# (mistake_pattern 재발 방지 관점에서) 반드시 별도로 검증되어야 한다.
# 이 헬퍼는 그 "올바른" 계산을 스펙 원문 그대로 재현한 것으로, 실제
# spw_ref_model.py 코드가 아니라 테스트 픽스처임에 유의할 것.
# ============================================================

def _time_since_last_transition_either_line(
    last_data_transition_ns: float,
    last_strobe_transition_ns: float,
    now_ns: float,
) -> float:
    """
    Spec 원문 (§5.4.8.c): "the length of time since the last transition on
    either the Data or Strobe line is longer than 727 ns ... and 1 µs maximum".

    "either ... or ..." 이므로 기준 시점은 Data/Strobe 두 라인의 마지막 전이
    시각 중 "더 최근" 쪽(= max)이다. Data만 보거나 Strobe만 보는 것은 모두
    스펙 원문과 다르다 (mistake_pattern: 신호semantics-미검증 재발 케이스).
    """
    last_transition_ns = max(last_data_transition_ns, last_strobe_transition_ns)
    return now_ns - last_transition_ns


# ============================================================
# scenario_id=1 — clause_id="5.4.8" Disconnect
# ============================================================

def scenario_001_disconnect_boundary() -> list[SubCaseResult]:
    """
    clause_id="5.4.8"

    §5.4.8.b 원문: "The disconnect detection shall be enabled when the link
    state machine leaves the ErrorReset state and the first edge is detected
    on the Data or Strobe line."
    §5.4.8.c 원문: "A disconnect shall occur when the length of time since the
    last transition on either the Data or Strobe line is longer than 727 ns
    (8 cycles of 10 MHz clock + 10 %) and 1 µs maximum (9 cycles of 10 MHz
    clock - 10 %)."

    → 기준 시점은 "Data 또는 Strobe 라인 중 더 최근에 전이한 쪽"이며(§5.4.8.c),
      disconnect는 그 시점으로부터 727ns 초과 ~ 1µs 이내에서 발생해야 한다.

    현재 golden model(spw_ref_model.is_disconnect)은 confidence='assumed'
    상태로, 스펙이 규정한 [727ns, 1us] "범위" 중 최솟값 727ns를 단일
    임계값으로 채택했다 (todo_note: "727ns~1us 범위 규정, 단일 임계값
    미지정 — 최솟값 727ns를 기본 threshold로 추정, 실제 구현체 값 대조
    확인 필요"). 이 시나리오는:
      1) 스펙이 명확히 규정하는 경계(727ns 이하 미발생, 1us 이내 발생 필수)를 검증하고,
      2) 727ns~1us "범위 안"이지만 727 초과인 지점(예: 900ns)에서 현재
         golden model이 이미 True를 반환하는 것을 "회귀 감시(regression
         guard)" 용도로 고정한다 — 이는 버그가 아니라 confidence='assumed'
         가정이 실제로 코드에 어떻게 반영되어 있는지를 드러내는 것이며,
         이 값이 나중에 실제 구현체 대조 확인 후 바뀔 수 있음을 명시한다.
      3) mistake_pattern("신호semantics-미검증") 재발 방지를 위해, "마지막
         전이 이후 경과 시간"의 기준점이 Data/Strobe 중 하나만이 아니라
         "더 최근에 전이한 쪽"이어야 함을 별도 서브케이스로 검증한다.
    """
    scenario_id = 1
    clause_id = "5.4.8"
    results: list[SubCaseResult] = []

    # --- 서브케이스 1~2: 727ns 이하 → 미발생 (스펙 명문 "longer than 727 ns") ---
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "t=700ns (< 727ns lower bound)",
            expected=False, actual=ref.is_disconnect(700.0),
            note="스펙 하한(727ns) 미만 — disconnect 미발생은 스펙 원문상 모호성 없음.",
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "t=727ns (exactly at lower bound)",
            expected=False, actual=ref.is_disconnect(727.0),
            note='스펙이 "longer than 727 ns"(초과)라고 명시 — 정확히 727ns는 아직 미발생이어야 함.',
        )
    )

    # --- 서브케이스 3: 727ns 초과 직후 → 발생 시작 가능 (스펙 하한을 막 넘은 지점) ---
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "t=727.1ns (just above lower bound)",
            expected=True, actual=ref.is_disconnect(727.1),
            note="727ns를 초과하는 최소 지점 — 스펙상 disconnect가 허용되기 시작하는 경계.",
        )
    )

    # --- 서브케이스 4: 727ns~1us "범위 안" 임의 지점 → 회귀 감시(assumed 임계값 고정) ---
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "t=900ns (within [727,1000] range, assumed-threshold regression guard)",
            expected=True, actual=ref.is_disconnect(900.0),
            note=(
                "주의: 이 케이스는 '버그 검출'이 아니라 golden model이 confidence='assumed'로 "
                "채택한 단일 임계값(727ns)의 현재 동작을 고정하는 회귀 감시용이다. 스펙은 "
                "727ns~1us '범위' 안 어디서 트리거해도 규정 준수이므로, 실제 구현체 대조 확인 후 "
                "이 golden model의 threshold_ns 기본값이 바뀌면 이 서브케이스의 expected 값도 "
                "재검토해야 한다 (todo_note 참고)."
            ),
        )
    )

    # --- 서브케이스 5: 1us(상한) 정확히 → 스펙상 이 시점까지는 이미 발생했어야 함 ---
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "t=1000ns (=1us upper bound)",
            expected=True, actual=ref.is_disconnect(1000.0),
            note='스펙 "1 µs maximum" — 늦어도 1us 시점에는 disconnect가 이미 발생했어야 함.',
        )
    )

    # --- 서브케이스 6: 1us 초과 → 골든모델의 stateless 한계 노출 ---
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "t=1500ns (> 1us upper bound, stateless limitation)",
            expected=True, actual=ref.is_disconnect(1500.0),
            note=(
                "1us를 넘어선 시점 — 현재 golden model은 단순 threshold 비교(stateless)라서 "
                "'1us 이내에 이미 발생했어야 한다'는 시간 흐름상의 불변식 자체는 검증하지 못하고, "
                "단지 '경과시간 > threshold'이면 True를 반환할 뿐이다. 이 서브케이스는 이 한계를 "
                "기록해 두기 위한 것이며, 실제 '1us를 넘겨서까지 미발생'하는 결함을 잡으려면 "
                "시간 경과에 따라 반복 호출하는 상태 기반(state-based) 모델이 별도로 필요하다."
            ),
        )
    )

    # --- 서브케이스 7~8: "either the Data or Strobe line" 기준점 재발 방지 검증 ---
    # mistake_pattern("신호semantics-미검증") 재발 방지: Data만 보거나 Strobe만 보고
    # 기준 시점을 잘못 잡으면 안 된다. §5.4.8.c 원문의 "either ... or ..."를
    # max(last_data, last_strobe)로 재현한 헬퍼로 올바른 값을 계산하고,
    # "한쪽만 본" 잘못된 계산과의 차이를 명시적으로 드러낸다.

    # 7a) Strobe만 최근에 전이한 경우: Data는 오래전(0ns)에 멈췄고, Strobe가
    #     600ns 시점에 전이했다면(§5.4.4.a에 따라 Data가 반복될 때 Strobe가 토글),
    #     현재 시각 800ns 기준 "올바른" 경과시간은 800-600=200ns (미발생 구간).
    correct_elapsed_a = _time_since_last_transition_either_line(
        last_data_transition_ns=0.0, last_strobe_transition_ns=600.0, now_ns=800.0
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id,
            "either-line ref: strobe-only transition resets timer (correct elapsed=200ns -> no disconnect)",
            expected=False, actual=ref.is_disconnect(correct_elapsed_a),
            note=(
                f"§5.4.8.c 'either the Data or Strobe line' 원문에 따라 last_transition="
                f"max(0,600)=600ns, elapsed={correct_elapsed_a}ns. Data 라인만 보고 계산했다면 "
                f"(0ns 기준) elapsed=800ns가 되어 잘못 True(오탐 disconnect)를 반환했을 것 — 실제로 "
                f"확인: ref.is_disconnect(800.0)={ref.is_disconnect(800.0)} (Data-only 오독 시 발생하는 값)."
            ),
        )
    )

    # 7b) Data만 최근에 전이한 경우 (대칭 케이스): Strobe는 오래전(0ns), Data가
    #     750ns 시점에 전이했다면, 800ns 기준 올바른 경과시간은 800-750=50ns.
    correct_elapsed_b = _time_since_last_transition_either_line(
        last_data_transition_ns=750.0, last_strobe_transition_ns=0.0, now_ns=800.0
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id,
            "either-line ref: data-only transition resets timer (correct elapsed=50ns -> no disconnect)",
            expected=False, actual=ref.is_disconnect(correct_elapsed_b),
            note=(
                f"last_transition=max(750,0)=750ns, elapsed={correct_elapsed_b}ns. Strobe 라인만 "
                f"보고 계산했다면(0ns 기준) elapsed=800ns가 되어 잘못 True를 반환했을 것 — 실제로 "
                f"확인: ref.is_disconnect(800.0)={ref.is_disconnect(800.0)} (Strobe-only 오독 시 발생하는 값)."
            ),
        )
    )

    return results


# ============================================================
# 헬퍼: 예외 발생 여부를 SubCaseResult로 비교 가능한 값으로 변환
# ============================================================

def _raises(fn, *args, **kwargs) -> str | None:
    try:
        fn(*args, **kwargs)
        return None
    except Exception as e:  # noqa: BLE001 - 테스트 픽스처, 예외 타입명만 필요
        return type(e).__name__


# ============================================================
# scenario_id=2 — clause_id="5.4.3.1.c" byte_to_bits_lsb_first
# ============================================================

def scenario_002_byte_to_bits_lsb_first() -> list[SubCaseResult]:
    """
    clause_id="5.4.3.1.c"

    §5.4.3.1.c 원문: "The eight-bit data value shall be transmitted least
    significant bit first."
    """
    scenario_id = 2
    clause_id = "5.4.3.1.c"
    results: list[SubCaseResult] = []

    results.append(
        SubCaseResult(
            scenario_id, clause_id, "value=5(0b101), width=8 -> LSB first",
            expected=[1, 0, 1, 0, 0, 0, 0, 0],
            actual=ref.byte_to_bits_lsb_first(5, 8),
            note="5=0b00000101. bit0(LSB)=1이 리스트 맨 앞에 와야 함(LSB first).",
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "value=0, width=8 -> all zero",
            expected=[0, 0, 0, 0, 0, 0, 0, 0],
            actual=ref.byte_to_bits_lsb_first(0, 8),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "value=255, width=8 -> all one",
            expected=[1, 1, 1, 1, 1, 1, 1, 1],
            actual=ref.byte_to_bits_lsb_first(255, 8),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "value=0b10(2), width=2 -> [0,1] (control type 필드용 폭)",
            expected=[0, 1],
            actual=ref.byte_to_bits_lsb_first(0b10, 2),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "value=256, width=8 -> out of range -> ValueError",
            expected="ValueError",
            actual=_raises(ref.byte_to_bits_lsb_first, 256, 8),
        )
    )

    return results


# ============================================================
# scenario_id=3 — clause_id="5.4.3.1" encode_data_character
# ============================================================

def scenario_003_encode_data_character() -> list[SubCaseResult]:
    """
    clause_id="5.4.3.1"

    §5.4.3.1.a 원문: "A data character shall be encoded in 10 bits with the
    resulting data symbol containing a parity bit, a data-control flag and
    eight bits of data..."
    §5.4.3.1.b 원문: "The data-control flag shall be set to zero to indicate
    that the current symbol holds a data character."
    §5.4.3.1.c: LSB first (scenario_002에서 별도 검증).

    Figure 5-15 예시 문자값 0x5C를 사용 (그림 자체는 clause_images에
    vlm_description 미등록 상태라 파형 대조는 못 했고, byte 값 0x5C만
    본문 캡션에서 재사용 — 아래 payload_bits는 byte_to_bits_lsb_first의
    이미 검증된 동작(scenario_002)으로부터 파생 계산한 값).
    """
    scenario_id = 3
    clause_id = "5.4.3.1"
    results: list[SubCaseResult] = []

    results.append(
        SubCaseResult(
            scenario_id, clause_id, "byte=0x5C(92) -> dc_flag=0, LSB-first payload",
            expected={"dc_flag": 0, "payload_bits": [0, 0, 1, 1, 1, 0, 1, 0]},
            actual=ref.encode_data_character(0x5C),
            note="92=0b01011100. LSB-first 전개: bit0..7 = 0,0,1,1,1,0,1,0.",
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "byte=0 -> dc_flag=0, all-zero payload",
            expected={"dc_flag": 0, "payload_bits": [0] * 8},
            actual=ref.encode_data_character(0),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "byte=255 -> dc_flag=0, all-one payload",
            expected={"dc_flag": 0, "payload_bits": [1] * 8},
            actual=ref.encode_data_character(255),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "byte=256 (out of range) -> ValueError",
            expected="ValueError",
            actual=_raises(ref.encode_data_character, 256),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "byte=-1 (out of range) -> ValueError",
            expected="ValueError",
            actual=_raises(ref.encode_data_character, -1),
        )
    )

    return results


# ============================================================
# scenario_id=4 — clause_id="5.4.3.3.b" encode_null
# ============================================================

def scenario_004_encode_null() -> list[SubCaseResult]:
    """
    clause_id="5.4.3.3.b"

    §5.4.3.3.b 원문: "The Null control code shall be encoded as an ESC
    followed by a flow control token (FCT)..."

    주의(궁금한 것으로 별도 보고): encode_null은 내부적으로
    encode_control_character를 호출하는데, 그 함수는
    golden_model_confidence.confidence='assumed' 상태(2비트 control type의
    전송 비트 순서를 스펙 미명시로 LSB-first 가정)이다. 즉 encode_null 자체는
    'cited'로 기록되어 있지만 그 정확성이 내부적으로 'assumed' 함수에
    의존한다 — 이 테스트는 "현재 구현이 이렇게 동작한다"를 고정하는
    것이지, encode_control_character의 비트 순서 가정 자체를 검증하는
    것은 아니다.
    """
    scenario_id = 4
    clause_id = "5.4.3.3.b"
    results: list[SubCaseResult] = []

    esc = ref.encode_control_character("ESC")
    fct = ref.encode_control_character("FCT")

    results.append(
        SubCaseResult(
            scenario_id, clause_id, "encode_null() == [ESC, FCT] (개별 encode_control_character와 동일)",
            expected=[esc, fct],
            actual=ref.encode_null(),
            note=f"esc={esc}, fct={fct} (encode_control_character의 현재 구현값을 그대로 재사용해 비교).",
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "encode_null()[0]는 ESC이므로 dc_flag=1 (제어문자)",
            expected=1,
            actual=ref.encode_null()[0]["dc_flag"],
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "encode_null() 길이는 정확히 2 (ESC + FCT)",
            expected=2,
            actual=len(ref.encode_null()),
        )
    )

    return results


# ============================================================
# scenario_id=5 — clause_id="5.4.3.3.c,d" encode_broadcast_code
# ============================================================

def scenario_005_encode_broadcast_code() -> list[SubCaseResult]:
    """
    clause_id="5.4.3.3.c,d"

    §5.4.3.3.c 원문: "The broadcast code (BC) shall be encoded as an ESC
    followed by a single data character..."
    §5.4.3.3.d 원문: "The eight bits of data in the data character of a
    broadcast code shall be separated into two fields: 1. The most
    significant two bits (B7:6) form the type field. 2. The least
    significant six bits (B5:0) form the value field."
    """
    scenario_id = 5
    clause_id = "5.4.3.3.c,d"
    results: list[SubCaseResult] = []

    # type_field=0b10(2), value_field=0 -> byte = (2<<6)|0 = 128 = 0b10000000
    bc1 = ref.encode_broadcast_code(0b10, 0)
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "type=0b10,value=0 -> byte=128, ESC 뒤에 data character",
            expected=[ref.encode_control_character("ESC"),
                      {"dc_flag": 0, "payload_bits": [0, 0, 0, 0, 0, 0, 0, 1]}],
            actual=bc1,
            note="128=0b10000000. LSB-first payload=[0,0,0,0,0,0,0,1] (bit7만 1).",
        )
    )

    # type_field=0b11(3), value_field=0b000001(1) -> byte=(3<<6)|1=193=0b11000001
    bc2 = ref.encode_broadcast_code(0b11, 1)
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "type=0b11,value=1 -> byte=193, B7:6=type/B5:0=value 분리 검증",
            expected=[ref.encode_control_character("ESC"),
                      {"dc_flag": 0, "payload_bits": [1, 0, 0, 0, 0, 0, 1, 1]}],
            actual=bc2,
            note="193=0b11000001. LSB-first payload=[1,0,0,0,0,0,1,1].",
        )
    )

    results.append(
        SubCaseResult(
            scenario_id, clause_id, "type_field=4 (2비트 초과) -> ValueError",
            expected="ValueError",
            actual=_raises(ref.encode_broadcast_code, 4, 0),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "value_field=64 (6비트 초과) -> ValueError",
            expected="ValueError",
            actual=_raises(ref.encode_broadcast_code, 0, 64),
        )
    )

    return results


# ============================================================
# scenario_id=6 — clause_id="5.4.3.4" compute_next_parity
# ============================================================

def scenario_006_compute_next_parity() -> list[SubCaseResult]:
    """
    clause_id="5.4.3.4"

    §5.4.3.4.b 원문: "The parity bit shall cover the previous eight bits of
    an encoded data character or two bits of an encoded control character,
    the current parity bit, and the current data-control flag..."
    §5.4.3.4.c 원문: "The parity bit shall be set to produce odd parity so
    that the total number of 1's in the field covered is an odd number."

    주의(궁금한 것): Figure 5-15("sending data character 0x5C followed by
    Null")는 이미지이며 clause_images.vlm_description이 비어 있어 그림의
    구체적 비트값으로 대조하지 못했다. 아래 테스트는 본문 텍스트(b,c)에서
    직접 유도되는 "커버 비트의 홀수 패리티" 대수적 성질만으로 검증한다.
    """
    scenario_id = 6
    clause_id = "5.4.3.4"
    results: list[SubCaseResult] = []

    cases = [
        ("prev=[1,1](ESC), dc_flag=1(제어문자 뒤 제어문자)", [1, 1], 1, 0),
        ("prev=[0,0](FCT), dc_flag=1", [0, 0], 1, 0),
        ("prev=0x5C 데이터 payload, dc_flag=0", [0, 0, 1, 1, 1, 0, 1, 0], 0, 1),
        ("prev=all-zero(8bit 데이터), dc_flag=0", [0] * 8, 0, 1),
        ("prev=all-one(8bit 데이터), dc_flag=0", [1] * 8, 0, 1),
    ]
    for desc, prev, dc, expected_p in cases:
        actual_p = ref.compute_next_parity(prev, dc)
        results.append(
            SubCaseResult(scenario_id, clause_id, desc, expected=expected_p, actual=actual_p)
        )
        total = sum(prev) + dc + actual_p
        results.append(
            SubCaseResult(
                scenario_id, clause_id, f"{desc} -> 홀수 패리티 불변식(sum(prev)+dc+P가 홀수)",
                expected=True, actual=(total % 2 == 1),
                note=f"total={total}",
            )
        )

    return results


# ============================================================
# scenario_id=7 — clause_id="5.4.5.a" first_null_parity
# ============================================================

def scenario_007_first_null_parity() -> list[SubCaseResult]:
    """
    clause_id="5.4.5.a"

    §5.4.5.a 원문: "The first bit of the first Null to be sent after the
    Transmitter Enabled flag is asserted shall be a parity bit, which is
    set to zero so that the first transition is on the Strobe line."
    """
    scenario_id = 7
    clause_id = "5.4.5.a"
    results: list[SubCaseResult] = []

    results.append(
        SubCaseResult(
            scenario_id, clause_id, "리셋 후 첫 Null의 첫 parity bit는 항상 0",
            expected=0, actual=ref.first_null_parity(),
        )
    )

    return results


# ============================================================
# scenario_id=8 — clause_id="5.4.7.b" check_parity
# ============================================================

def scenario_008_check_parity() -> list[SubCaseResult]:
    """
    clause_id="5.4.7.b"

    §5.4.7.b 원문: "A parity error shall be detected when the parity is not
    odd." (NOTE: Parity is not odd when there is an even number of bits set
    to '1', per clause 5.4.3.4.) golden model의 check_parity는 "정상(홀수
    패리티, 에러 없음)"일 때 True를 반환한다.
    """
    scenario_id = 8
    clause_id = "5.4.7.b"
    results: list[SubCaseResult] = []

    results.append(
        SubCaseResult(
            scenario_id, clause_id, "prev=[1,1],dc=1,received_P=0 -> total=3(홀수) -> 정상(True)",
            expected=True, actual=ref.check_parity([1, 1], 1, 0),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "prev=[1,1],dc=1,received_P=1 -> total=4(짝수) -> parity error(False)",
            expected=False, actual=ref.check_parity([1, 1], 1, 1),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "prev=[0]*8,dc=0,received_P=1 -> total=1(홀수) -> 정상(True)",
            expected=True, actual=ref.check_parity([0] * 8, 0, 1),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "prev=[0]*8,dc=0,received_P=0 -> total=0(짝수) -> parity error(False)",
            expected=False, actual=ref.check_parity([0] * 8, 0, 0),
        )
    )

    return results


# ============================================================
# scenario_id=9 — clause_id="5.4.4.a,b" encode_data_strobe
# ============================================================

def scenario_009_encode_data_strobe() -> list[SubCaseResult]:
    """
    clause_id="5.4.4.a,b"

    §5.4.4.a.1 원문: "The Data signal is high when the data bit is 1 and low
    when the data bit is 0."
    §5.4.4.a.2 원문: "The Strobe signal changes state whenever the Data has
    the same value from one bit to the next."
    §5.4.4.b 원문: "The Data and Strobe signals shall be set to zero on
    power up reset." (golden model의 encode_data_strobe는 매 호출마다
    prev_data=0, prev_strobe=0에서 시작 — 이 리셋 상태 가정과 일치.)

    주의(궁금한 것): Figure 5-16(DS 인코딩 파형)은 clause_images에
    vlm_description이 없어 그림 대조는 못 했다. 아래는 본문 텍스트(a.1,
    a.2)만으로 유도한 값이며, 텍스트 자체가 알고리즘을 완전히 규정하므로
    그림 없이도 인용 근거로 충분하다고 판단했다.
    """
    scenario_id = 9
    clause_id = "5.4.4.a,b"
    results: list[SubCaseResult] = []

    data, strobe = ref.encode_data_strobe([1, 1, 0, 0, 1])
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "bitstream=[1,1,0,0,1] -> Data 라인은 비트값 그대로",
            expected=[1, 1, 0, 0, 1], actual=data,
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "bitstream=[1,1,0,0,1] -> Strobe: 이전 비트와 같을 때만 토글",
            expected=[0, 1, 1, 0, 0], actual=strobe,
            note=(
                "bit1(=1)은 reset상태 prev_data=0과 달라 strobe 유지(0). "
                "bit2(=1)는 이전 bit(1)과 같아 strobe 토글(0->1). "
                "bit3(=0)은 이전(1)과 달라 strobe 유지(1). "
                "bit4(=0)는 이전(0)과 같아 strobe 토글(1->0). "
                "bit5(=1)는 이전(0)과 달라 strobe 유지(0)."
            ),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "빈 bitstream -> 빈 Data/Strobe",
            expected=([], []), actual=ref.encode_data_strobe([]),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "단일 bit=0 (reset 직후, prev_data=0과 같음) -> strobe 토글(0->1)",
            expected=([0], [1]), actual=ref.encode_data_strobe([0]),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "단일 bit=1 (reset 직후, prev_data=0과 다름) -> strobe 유지(0)",
            expected=([1], [0]), actual=ref.encode_data_strobe([1]),
        )
    )

    return results


# ============================================================
# scenario_id=10 — clause_id="5.4.3.4;5.4.5" SerialEncoder.encode
# ============================================================

def scenario_010_serial_encoder() -> list[SubCaseResult]:
    """
    clause_id="5.4.3.4;5.4.5"

    §5.4.5.a: 리셋 후 첫 Null의 첫 parity bit는 0.
    §5.4.3.4.b,c: 그 이후는 이전 문자의 payload+dc_flag+P 자신을 커버하는
    홀수 패리티.
    """
    scenario_id = 10
    clause_id = "5.4.3.4;5.4.5"
    results: list[SubCaseResult] = []

    se = ref.SerialEncoder()
    se.reset()

    s1 = se.encode(ref.encode_control_character("ESC"), is_first_null=True)
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "리셋 후 첫 심볼(ESC, is_first_null=True) -> parity=0 (§5.4.5.a)",
            expected={"parity": 0, "dc_flag": 1, "payload_bits": [1, 1]}, actual=s1,
        )
    )

    s2 = se.encode(ref.encode_control_character("FCT"))
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "두 번째 심볼(FCT) -> compute_next_parity([1,1],1)로 체인",
            expected={"parity": 0, "dc_flag": 1, "payload_bits": [0, 0]}, actual=s2,
        )
    )

    s3 = se.encode(ref.encode_data_character(0x5C))
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "세 번째 심볼(0x5C 데이터) -> compute_next_parity(prev=[0,0], 현재dc_flag=0)로 체인",
            expected={"parity": 1, "dc_flag": 0, "payload_bits": [0, 0, 1, 1, 1, 0, 1, 0]}, actual=s3,
            note="prev_payload_bits=[0,0](직전 FCT의 payload)이지만, parity 계산에 쓰이는 dc_flag는 "
                 "'현재(이번) 심볼'인 데이터문자의 dc_flag=0 (§5.4.3.4.b: 커버 대상은 이전 payload + "
                 "'current parity bit, current data-control flag'). ones=sum([0,0])+0=0(짝수)->P=1.",
        )
    )

    se2 = ref.SerialEncoder()
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "리셋 직후 is_first_null=False로 첫 심볼 인코딩 시도 -> ValueError",
            expected="ValueError",
            actual=_raises(se2.encode, ref.encode_data_character(1), False),
        )
    )

    return results


# ============================================================
# scenario_id=11 — clause_id="5.4.6" NullDetector.feed_bit
# ============================================================

def scenario_011_null_detector() -> list[SubCaseResult]:
    """
    clause_id="5.4.6"

    §5.4.6.a: Null detection은 receiver enable 시 활성화.
    §5.4.6.b: gotNull은 RX Enable de-assert 시에만 클리어.
    §5.4.6.d, NOTE 1 원문: "The first Null after the receiver is enable is
    the 011101000 sequence of bits..."
    """
    scenario_id = 11
    clause_id = "5.4.6"
    results: list[SubCaseResult] = []
    pattern = [0, 1, 1, 1, 0, 1, 0, 0, 0]

    nd_disabled = ref.NullDetector()
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "enable_rx() 전에는 feed_bit해도 got_null=False",
            expected=False, actual=nd_disabled.feed_bit(pattern[0]),
        )
    )

    nd = ref.NullDetector()
    nd.enable_rx()
    intermediate_ok = all(nd.feed_bit(b) is False for b in pattern[:-1])
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "패턴의 앞 8비트까지는 got_null=False 유지",
            expected=True, actual=intermediate_ok,
        )
    )
    final = nd.feed_bit(pattern[-1])
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "011101000 전체 시퀀스 완료 시 got_null=True",
            expected=True, actual=final,
        )
    )

    nd_wrong = ref.NullDetector()
    nd_wrong.enable_rx()
    wrong_result = any(nd_wrong.feed_bit(b) for b in [0] * 9)
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "잘못된 시퀀스(전부 0)는 got_null이 절대 True가 되지 않음",
            expected=False, actual=wrong_result,
        )
    )

    nd2 = ref.NullDetector()
    nd2.enable_rx()
    for b in pattern:
        nd2.feed_bit(b)
    nd2.disable_rx()
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "disable_rx() 후 got_null 클리어 (§5.4.6.b)",
            expected=False, actual=nd2.got_null,
        )
    )
    nd2.enable_rx()
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "재enable 후 got_null=False로 재시작, 재검출 필요",
            expected=False, actual=nd2.got_null,
        )
    )

    nd3 = ref.NullDetector()
    nd3.enable_rx()
    for b in [1, 1] + pattern:
        result3 = nd3.feed_bit(b)
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "패턴 앞에 잡음(1,1)이 있어도 슬라이딩 윈도우로 마지막 9비트만 보고 검출",
            expected=True, actual=result3,
        )
    )

    return results


# ============================================================
# scenario_id=12 — clause_id="5.4.2.c,d" EncodingLayer.receive_symbol
# ============================================================

def scenario_012_encoding_layer_receive_symbol() -> list[SubCaseResult]:
    """
    clause_id="5.4.2.c,d"

    §5.4.2.c 원문: "Only received characters and control codes without a
    parity error shall be passed to the data link layer."
    §5.4.2.d 원문: "Only while gotNull is asserted... shall characters and
    control codes that are received be passed to the data link layer."
    (receive_enable 게이팅 자체는 §5.4.2.e.2에서 "Receive Enable...resets
    it when de-asserted"로 규정 — 코드 주석은 c,d만 인용하나 receive_enable
    선행조건은 e.2에 근거함을 여기서 명시.)
    """
    scenario_id = 12
    clause_id = "5.4.2.c,d"
    results: list[SubCaseResult] = []

    el = ref.EncodingLayer()
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "receive_enable=False -> 항상 차단 (§5.4.2.e.2)",
            expected=False, actual=el.receive_symbol(False),
        )
    )

    el.receive_enable = True
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "receive_enable=True, got_null=False -> 차단 (§5.4.2.d)",
            expected=False, actual=el.receive_symbol(False),
        )
    )

    el.got_null = True
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "got_null=True, parity error 있음 -> 차단 (§5.4.2.c)",
            expected=False, actual=el.receive_symbol(True),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "receive_enable=True, got_null=True, parity error 없음 -> 통과",
            expected=True, actual=el.receive_symbol(False),
        )
    )

    return results


# ============================================================
# scenario_id=13 — clause_id="5.4.9.a" is_esc_error
# ============================================================

def scenario_013_is_esc_error() -> list[SubCaseResult]:
    """
    clause_id="5.4.9.a"

    §5.4.9.a 원문: "An escape character (ESC) followed by ESC, EOP or EEP is
    an invalid sequence and when received shall produce an ESC error."
    (NOTE: ESC followed by FCT is a Null and ESC followed by a data
    character is a broadcast code — 즉 에러 아님.)
    """
    scenario_id = 13
    clause_id = "5.4.9.a"
    results: list[SubCaseResult] = []

    for cur in ["ESC", "EOP", "EEP"]:
        results.append(
            SubCaseResult(
                scenario_id, clause_id, f"prev=ESC, current={cur} -> ESC error",
                expected=True, actual=ref.is_esc_error("ESC", cur),
            )
        )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "prev=ESC, current=FCT -> Null(에러 아님)",
            expected=False, actual=ref.is_esc_error("ESC", "FCT"),
        )
    )
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "prev=FCT, current=ESC -> prev가 ESC 아니므로 에러 아님",
            expected=False, actual=ref.is_esc_error("FCT", "ESC"),
        )
    )

    return results


# ============================================================
# scenario_id=14 — clause_id="5.4.10.1.a,b" is_valid_initial_rate
# ============================================================

def scenario_014_is_valid_initial_rate() -> list[SubCaseResult]:
    """
    clause_id="5.4.10.1.a,b"

    §5.4.10.1.a 원문: "After a reset or disconnect... an output port shall
    start operating at a data signalling rate of 10 ± 1 Mb/s."
    """
    scenario_id = 14
    clause_id = "5.4.10.1.a,b"
    results: list[SubCaseResult] = []

    results.append(
        SubCaseResult(scenario_id, clause_id, "9.0 Mb/s (하한, 포함)", expected=True, actual=ref.is_valid_initial_rate(9.0))
    )
    results.append(
        SubCaseResult(scenario_id, clause_id, "8.99 Mb/s (하한 미만)", expected=False, actual=ref.is_valid_initial_rate(8.99))
    )
    results.append(
        SubCaseResult(scenario_id, clause_id, "10.0 Mb/s (정상)", expected=True, actual=ref.is_valid_initial_rate(10.0))
    )
    results.append(
        SubCaseResult(scenario_id, clause_id, "11.0 Mb/s (상한, 포함)", expected=True, actual=ref.is_valid_initial_rate(11.0))
    )
    results.append(
        SubCaseResult(scenario_id, clause_id, "11.01 Mb/s (상한 초과)", expected=False, actual=ref.is_valid_initial_rate(11.01))
    )

    return results


# ============================================================
# scenario_id=15 — clause_id="5.4.3.2" Control character bit order
# ============================================================

def scenario_015_control_character_bit_order() -> list[SubCaseResult]:
    """
    clause_id="5.4.3.2"

    §5.4.3.2.c-f 원문: FCT=0b00, EOP=0b10, EEP=0b01, ESC=0b11 (control type 값만 명시,
    본문에는 전송 비트 순서 규정 없음).

    이 골든모델은 §5.4.3.1.c("LSB first")와 동일한 관례를 control type 2비트에도
    적용한다고 confidence='assumed'로 가정해 왔으나, diagram-enricher가 Figure 5-12
    (image_id=87)를 재확인한 결과 Figure 5-11(image_id=85)과 동일한 전송방향 화살표가
    4개 행 모두에 실재함을 직접 확인했고, LSB/MSB 라벨·FCT/EOP/EEP/ESC 수치도 본문과
    교차검증됐다 (spec-arbiter 최종 판정, judgment_id=5, 2026-09-07, verdict=A,
    confidence=high — confidence='cited'로 승격 완료). 이 시나리오는
    encode_control_character()가 그 확정된 LSB-first 순서와 정확히 일치하는
    payload_bits를 생성하는지 4개 control type 전부에 대해 회귀 감시한다.
    """
    scenario_id = 15
    clause_id = "5.4.3.2"
    results: list[SubCaseResult] = []

    # Figure 5-12 (image_id=87) 교차검증 결과: FCT=(LSB=0,MSB=0), EOP=(LSB=0,MSB=1),
    # EEP=(LSB=1,MSB=0), ESC=(LSB=1,MSB=1) — payload_bits[0]=LSB, payload_bits[1]=MSB.
    expected_lsb_first = {
        "FCT": [0, 0],
        "EOP": [0, 1],
        "EEP": [1, 0],
        "ESC": [1, 1],
    }
    for control_type, expected_bits in expected_lsb_first.items():
        symbol = ref.encode_control_character(control_type)
        results.append(
            SubCaseResult(
                scenario_id, clause_id, f"{control_type} payload_bits (LSB-first, Figure 5-12 교차검증)",
                expected=expected_bits, actual=symbol["payload_bits"],
                note=f"Figure 5-12(image_id=87) LSB/MSB 라벨 근거 — {control_type}=0b{ref.CONTROL_TYPE_CODE[control_type]:02b}.",
            )
        )
        results.append(
            SubCaseResult(
                scenario_id, clause_id, f"{control_type} dc_flag=1 (§5.4.3.2.b)",
                expected=1, actual=symbol["dc_flag"],
            )
        )

    return results


# ============================================================
# scenario_id=16 — clause_id="5.4.4.d,e" Reset delay lower bound
# ============================================================

def scenario_016_reset_delay_lower_bound() -> list[SubCaseResult]:
    """
    clause_id="5.4.4.d,e"

    §5.4.4.e 원문: "The delay between the reset of the Strobe signal and the Data
    signal shall be between 500 ns ... and the period of the fastest transmit time
    for the particular transmitter which is dependent upon implementation."

    하한(500ns)은 스펙이 숫자로 강제하므로 반드시 검증해야 한다(cited). 상한은 스펙
    자체에 범용 숫자가 없어(DECISION-02) 이 골든모델은 검증하지 않는다 — 그러므로
    "상한 없음"을 회귀 감시하는 서브케이스(매우 큰 delay_ns도 accept)도 포함한다.
    리셋 순서는 §5.4.4.c NOTE 예시 근거로 strobe-first를 기본값 채택(assumed).
    """
    scenario_id = 16
    clause_id = "5.4.4.d,e"
    results: list[SubCaseResult] = []

    # --- 하한 미만 → ValueError ---
    try:
        ref.reset_data_strobe_lines(499.9)
        raised = False
    except ValueError:
        raised = True
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "delay_ns=499.9 (< 500ns 하한) → ValueError",
            expected=True, actual=raised,
            note="§5.4.4.e 하한(500ns) 미만은 스펙 위반 — 반드시 reject.",
        )
    )

    # --- 하한 경계값 정확히 500ns → accept ---
    try:
        ref.reset_data_strobe_lines(500.0)
        raised = False
    except ValueError:
        raised = True
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "delay_ns=500.0 (하한, 포함) → accept",
            expected=False, actual=raised,
            note='스펙 "between 500 ns and ..." — 500ns 자체는 포함되는 경계로 간주.',
        )
    )

    # --- 상한 없음 회귀 감시: 매우 큰 delay도 accept (DECISION-02) ---
    try:
        ref.reset_data_strobe_lines(1_000_000.0)
        raised = False
    except ValueError:
        raised = True
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "delay_ns=1_000_000ns (상한 미검증 회귀 감시)",
            expected=False, actual=raised,
            note=(
                "DECISION-02: 상한은 스펙에 범용 숫자가 없어 이 골든모델은 검증하지 않는다. "
                "이 서브케이스는 '버그 검출'이 아니라 그 설계 선택을 고정하는 회귀 감시용이며, "
                "Phase B에서 RTL 실측 상한이 확보되면 재검토 대상이다."
            ),
        )
    )

    # --- strobe-first 순서 반환 확인 ---
    sequence = ref.reset_data_strobe_lines(500.0)
    results.append(
        SubCaseResult(
            scenario_id, clause_id, "리셋 순서 = strobe-first (§5.4.4.c NOTE 근거, assumed)",
            expected=[("strobe", 0, 0.0), ("data", 0, 500.0)], actual=sequence,
        )
    )

    return results


SCENARIOS = [
    scenario_001_disconnect_boundary,
    scenario_002_byte_to_bits_lsb_first,
    scenario_003_encode_data_character,
    scenario_004_encode_null,
    scenario_005_encode_broadcast_code,
    scenario_006_compute_next_parity,
    scenario_007_first_null_parity,
    scenario_008_check_parity,
    scenario_009_encode_data_strobe,
    scenario_010_serial_encoder,
    scenario_011_null_detector,
    scenario_012_encoding_layer_receive_symbol,
    scenario_013_is_esc_error,
    scenario_014_is_valid_initial_rate,
    scenario_015_control_character_bit_order,
    scenario_016_reset_delay_lower_bound,
]


def main() -> int:
    all_results: list[SubCaseResult] = []
    for scenario_fn in SCENARIOS:
        all_results.extend(scenario_fn())

    for r in all_results:
        print(r.report())

    total = len(all_results)
    passed = sum(1 for r in all_results if r.passed)
    print()
    print(f"{passed}/{total} PASS")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
