---
description: 특정 모듈/조항 범위에 대한 골든모델 초안을 작성한다. 스펙 인용 강제, 확신 없는 부분은 TODO로 명시, 함수 단위 신뢰도를 즉시 DB에 기록한다.
---

**이 커맨드는 "검증 완료"를 만드는 게 아니라 "검증 시작점"을 만드는 것입니다.** 작성한 초안은 자동으로 0% 검증 상태로 등록됩니다.

아래 SQL 조회/삽입은 전부 CLAUDE.md §9 실행 컨벤션(`.venv/bin/python3 -c "..."` 고정 형태)으로 실행할 것.

1. 대상 모듈(예: Router)의 범위에 해당하는 조항들을 조회:
   ```sql
   SELECT clause_id, title, text_full FROM clauses WHERE clause_id LIKE '<대상 챕터 prefix>%';
   ```
2. 각 조항에 대해 `clause_references`로 연결된 관련 조항까지 함께 조회 (문맥 확보).
3. 관련 `clause_images`가 있으면 `vlm_description` 확인. NULL이면 사람에게 `diagram-enricher` 먼저 실행할지 확인.
4. 다음 규칙을 지키며 골든모델 Python 코드 작성:
   - **모든 함수/주요 분기에 `# Spec: §X.X.X` 주석 필수.** 인용할 조항이 없으면 그 자체가 위험 신호이므로 작성을 멈추고 사람에게 확인.
   - 스펙에 명시된 대로 구현 가능한 부분: 그대로 구현, `confidence='cited'`
   - 스펙에 없어 합리적 추정이 필요한 부분: 구현하되 `confidence='assumed'`로 표시하고 `todo_note`에 추정 근거를 반드시 남길 것
   - 확신이 서지 않아 구현을 미루는 부분: **절대 그럴듯하게 채우지 말고**
     ```python
     raise NotImplementedError("TODO: §X.X.X <구체적으로 뭐가 불확실한지> - 확인 필요")
     ```
     로 명시. `confidence='todo'`
5. 작성한 모든 함수를 즉시 DB에 기록:
   ```sql
   INSERT INTO golden_model_confidence
   (function_name, file_path, spec_citation, confidence, todo_note, created_at)
   VALUES (?, ?, ?, ?, ?, datetime('now'));
   ```
6. 작성 완료 후, 이번에 다룬 모든 clause_id에 대해 **Phase A verification_status를 명시적으로 `untested`로 재확인** (이미 untested였겠지만, 실수로 다른 상태였다면 여기서 되돌림):
   ```sql
   UPDATE verification_status SET status = 'untested', last_verified_at = NULL
   WHERE phase = 'A' AND clause_id IN (...);
   ```
7. 사람에게 요약 보고:
   ```
   ## 골든모델 초안 작성 완료 (검증 0%)

   **cited 함수**: N개
   **assumed 함수**: N개 — 목록과 추정 근거
   **todo 함수**: N개 — 목록과 무엇이 불확실한지

   다음 단계로 /grow-golden-model 을 실행하여 이 초안을 실제로 검증하세요.
   ```
8. **절대 이 초안을 "완료"라고 표현하지 말 것.** "초안 작성 완료, 검증 필요"라고만 표현.
