---
description: Phase B - RTL을 성숙한 골든모델 기준으로 한 사이클 고도화한다. RTL 수정은 항상 사람 승인 후 적용.
---

Phase B 루프를 한 사이클 실행합니다. **RTL 파일은 자동 수정하지 않습니다.**

1. `spec-gap-finder` 서브에이전트 호출 (phase='B'), 대상은 `status='golden_model_validated'`이면서 아직 `rtl_validated`가 아닌 조항.
2. 사람에게 목록 제시, 대상 조항 1개 선택받음.
3. `testcase-writer` 서브에이전트 호출 (phase='B') → RTL 테스트벤치 작성.
4. iverilog 시뮬레이션 실행 (CLAUDE.md §9 실행 컨벤션 준수 — 출력 경로는 항상 `spec_harness/ingest/` 아래):
   ```bash
   iverilog -g2012 -o spec_harness/ingest/sim_out <관련 .sv 파일들, 명시적으로 나열>
   vvp spec_harness/ingest/sim_out
   ```
5. 골든모델 동일 시나리오 출력과 비교.
6. 일치 → `verification_status`를 `rtl_validated`로 갱신, 종료.
7. 불일치 → `spec-arbiter` 서브에이전트 호출 (phase='B').
   - 판정 A (RTL 결함) → 수정 diff만 제시. `ask_user_input`으로 승인 요청. 승인 시에만 적용.
   - 판정 B (골든모델 재검토 필요) → Phase A 회귀 필요 보고, 이번 사이클 중단.
   - 판정 C (하드웨어 제약상 불가피) → DECISION 레코드, trade-off 설명, 사람 최종 판단.
8. RTL 수정 적용 시 관련 `tb_*.sv` 전체 회귀 재실행.
9. Vivado 타이밍/리소스 체크는 사람에게 수동 실행 요청 (자동 실행 안 함).
10. 커밋 trailer에 Phase: B 명시.
