---
decision_id: DECISION-01
clause_id: "§5.4.8.c"
phase: A
status: open
raised_by: spec-arbiter
date: 2026-09-07
---

## 쟁점
골든모델 `is_disconnect()` (spw_ref_model.py)가 disconnect 판정에 단일 threshold=727ns(하한값)를 채택하고 있으나, 이 값이 스펙에 명시적으로 규정된 값인지 아니면 구현자의 자의적 선택인지 확인되지 않은 상태였음. 또한 현재 구현은 상한(1µs)을 넘어서도 미발생 시 이를 결함으로 판정하는 로직이 없음(stateless, 단순 `elapsed > threshold_ns` 비교).

## 스펙 상태
§5.4.8.c 원문: "A disconnect shall occur when the length of time since the last transition on either the Data or Strobe line is longer than 727 ns (8 cycles of 10 MHz clock + 10 %) and 1 µs maximum (9 cycles of 10 MHz clock - 10 %)."
→ 하한(727ns 초과)과 상한(1µs 이내) 두 경계값만 규정. 이 범위 내 정확히 언제 disconnect를 트리거해야 하는지에 대한 단일 값 지정 없음. clause_references로 연결된 §5.4.3.3, §5.4.10.1도 disconnect의 존재/재시작 조건만 언급할 뿐 수치 기준을 보강하지 않음. 관련 clause_images 없음.
spec-arbiter 판정(2026-09-07, arbiter_judgments.judgment_id=1): 판정 B(스펙 모호), confidence=high.

## 가능한 해석
1. 해석 A (현재 채택): 하한(727ns)을 트리거 시점으로 사용 — 가장 이른 시점에 disconnect를 검출하는 보수적 선택. 실제 구현체(RTL)와 대조 필요.
2. 해석 B: 상한(1µs)을 트리거 시점으로 사용 — 스펙이 허용하는 범위를 최대한 활용, 노이즈로 인한 오탐(false disconnect) 가능성 최소화.
3. 해석 C: stateful 모델로 전환 — "727ns~1µs 범위 내 어느 시점에 트리거해도 규정 준수"를 정확히 반영하려면, 현재처럼 매 호출 시 순간 비교하는 대신 실제 구현체(RTL)의 트리거 시점을 golden model이 그대로 미러링하도록 파라미터화. Phase B에서 RTL과 대조 시 이 값을 RTL 실측치로 교체.

## 현재 채택
해석 C 채택 (2026-09-07, 사람 결정): 실제 구현체(RTL) 대조 전까지 확정하지 않고 보류.
- 그때까지 golden model 코드는 수정하지 않고 현행 727ns(하한) 값을 그대로 유지 (`confidence='assumed'` 유지).
- Phase B에서 RTL의 실제 disconnect 트리거 시점을 실측한 뒤, 그 값으로 `is_disconnect`의 `threshold_ns` 기본값을 맞추고 `spec_citation`/`confidence`를 재검토한다.
- 상한(1µs) 초과 미검출 stateless 한계도 이때 함께 재검토 대상.
- 이 DECISION은 Phase B에서 RTL 실측치가 확보될 때까지 `status: open` 유지.

## 영향 범위
- golden model: `spw_ref_model.py::is_disconnect`, `golden_model_confidence`(function_name='is_disconnect')는 `confidence='assumed'` 유지.
- 별도 이슈: 상한(1µs) 초과 시 "이미 발생했어야 함" 불변식은 현재 stateless 구조상 검증 불가 — 이것이 DECISION 범위에 포함되는지, 별도 DECISION으로 분리할지도 함께 결정 필요.
- Phase B 진입 시 RTL 실측 threshold 값이 이 결정에 직접 영향받음.
