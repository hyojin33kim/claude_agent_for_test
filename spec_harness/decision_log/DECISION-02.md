---
decision_id: DECISION-02
clause_id: "§5.4.4.d,e"
phase: A
status: open
raised_by: spec-arbiter
date: 2026-09-07
---

## 쟁점
골든모델 `reset_data_strobe_lines()`가 미구현(NotImplementedError) 상태였음. 구현하려면
(1) ErrorReset 진입 시 Strobe/Data 리셋 순서, (2) 리셋 사이 지연(delay)의 상한을 확정해야
하는데, 둘 다 스펙이 단일 값을 강제하지 않는 구현 재량/개방형 범위임.

## 스펙 상태
§5.4.4.c NOTE: "예를 들어, 송신 정지 후 Strobe를 먼저 리셋한 뒤 Data를 리셋하면 동시 전이를
막을 수 있다" — 예시일 뿐 순서를 강제하지 않음.
§5.4.4.d: "...the data and strobe signals shall be reset with a delay between the reset of
the strobe followed by data signal **or** reset of the data followed by strobe signal." —
두 순서 모두 명시적으로 허용("or").
§5.4.4.e: "The delay ... shall be between 500 ns (the period of slowest permitted transmit
bit rate, 2 Mbps) and the period of the fastest transmit time for the particular
transmitter which is dependent upon implementation." — 하한(500ns)은 숫자로 명시, 상한은
"특정 송신기의 구현에 따라 다름"이라고만 되어 있어 스펙 문서 자체에 범용 상한 숫자가
없음.
spec-arbiter 판정(2026-09-07, `arbiter_judgments.judgment_id=2`): 판정 B(스펙 모호/구현
재량), confidence=high. §5.5.7.2(ErrorReset 상태 진입 조건)도 재조회했으나 순서/상한에
대한 추가 규정 없음.

## 가능한 해석
1. **순서**: (a) strobe-first 고정 채택 (§5.4.4.c NOTE 예시 근거) — 현재 채택.
   (b) `order` 파라미터로 호출자가 선택하게 함 — 유연하지만 골든모델 API가 복잡해짐.
2. **상한**: (a) 검증하지 않음(하한 500ns만 검증) — 스펙 근거 없는 상한을 창작하지 않음.
   (b) 호출자가 `max_delay_ns`를 필수 파라미터로 넘겨 검증 — RTL 대조 시점(Phase B)에 실측
   치를 넣을 수 있어 정확하지만, 지금은 이 값이 없어 API에 억지로 자리만 만드는 셈.
   (c) 임의 상한(예: 1µs)을 하드코딩 — 스펙 근거 없어 CLAUDE.md §1 위반, 채택 안 함.

## 현재 채택
2026-09-07, 사람 결정:
- **순서**: 해석 1(a) — `reset_data_strobe_lines()`는 strobe-first를 기본값(유일한 동작)으로
  구현. `golden_model_confidence.reset_data_strobe_lines`는 `confidence='assumed'`로 기록.
- **상한**: 해석 2(a) — 하한(`delay_ns >= 500`)만 검증하고 상한은 검증하지 않음. 상한을
  임의로 창작하지 않는다는 CLAUDE.md §1 원칙을 그대로 따름.
- Phase B에서 실제 RTL의 트랜시버 최대 전송 비트레이트가 확정되면, 그 값을 근거로 상한
  검증을 추가할지, 순서를 파라미터화할지 재검토한다.

## 영향 범위
- golden model: `spw_ref_model.py::reset_data_strobe_lines`.
- `verification_status`(5.4.4, Phase A)는 `ambiguous=1` 유지 — 하한 검증까지는 확정이나
  상한 정책은 Phase B 확인 전까지 미결이므로.
- Phase B 진입 시 RTL 실측치 확보 후 이 DECISION을 닫을지 재논의.
