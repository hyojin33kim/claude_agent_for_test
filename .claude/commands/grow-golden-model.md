---
description: Phase A - 골든모델을 스펙과 대조하며 한 사이클 성숙시킨다.
---

Phase A 루프를 한 사이클 실행합니다.

1. `spec-gap-finder` 서브에이전트 호출 (phase='A') → 우선순위 조항 3~5개 수신.
   - 이때 함께 확인: `golden_model_confidence`에서 이 조항 관련 함수 중 `confidence != 'cited'`인 것이 있는지 (assumed/todo부터 우선 검증하는 게 효율적)
   ```sql
   SELECT * FROM golden_model_confidence WHERE spec_citation LIKE ? AND confidence != 'cited';
   ```
2. **`spec-gap-finder`가 매긴 우선순위 1순위 조항을 기본으로 자동 선택**하고, 무엇을 왜 골랐는지 사람에게 보고만 함 (승인 대기 없이 바로 3번 진행). 사람이 다른 조항을 명시적으로 지정하면 그걸 우선.
3. `testcase-writer` 서브에이전트 호출 → 새 시나리오 작성.
4. 전체 회귀 실행:
   ```
   python3 spw_ref_model_test_v5.py
   ```
5. 전부 PASS → `verification_status`를 `golden_model_validated`로 갱신, 관련 `golden_model_confidence`가 `assumed`/`todo`였다면 `cited`로 승격, 보고 후 종료.
6. FAIL 발생 → `spec-arbiter` 서브에이전트 호출 (phase='A').
   - 판정 A (골든모델 결함) → 수정 → 4번으로 돌아가 전체 회귀 재실행 → 전부 PASS 확인 후 커밋
   - 판정 B (스펙 모호) 또는 confidence='low' → **사람 응답을 기다리지 않음.** DECISION 레코드를 `status='open'`으로 생성해 큐에 적재, `verification_status.ambiguous=1` 마킹, 보고 후 이번 사이클 정상 종료. (Phase A는 소프트웨어 골든모델 단계라 되돌릴 수 없는 부작용이 없으므로 블로킹 에스컬레이션 대신 큐잉 — 사람은 열린 DECISION 목록을 나중에 몰아서 검토. Phase B는 이 완화가 적용되지 않음 — `spec-arbiter.md` 참고.)
   - 판정 C (테스트 오류) → 3번으로 복귀
7. 커밋 trailer에 Spec-citation, Feedback, Root-cause, Phase: A 필수 포함.
8. 정지 조건 체크:
   ```sql
   SELECT COUNT(*) FROM verification_status WHERE phase='A' AND status != 'untested';
   SELECT COUNT(*) FROM verification_status WHERE phase='A';
   ```
   비율 90% 이상 + 최근 10 사이클 연속 무변경이면 Phase B 전환을 사람에게 제안.
