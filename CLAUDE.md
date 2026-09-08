# SpaceWire Spec2RTL — Project Rules (Always Loaded)

## -1. 언어 규칙
모든 응답(질문, 확인 요청, 진행 상황 보고, 커밋 메시지 설명 등)은 한글로 작성할 것.
코드, 파일 경로, 커맨드, SQL, 기술 용어(예: clause_id, confidence, phase)는 원문(영문) 그대로 유지.
사용자가 명시적으로 다른 언어를 요청하지 않는 한 예외 없음.

## 0. 세션 시작 시 필수 절차
1. `spec_harness/spec_harness.db` 쿼리하여 현재 Phase(A/B) 진행률, 미검증 조항, 최근 mistake_patterns 확인
2. `git log --oneline -15` 로 최근 변경 확인
3. **절대 "완료"/"N/N PASS" 주장을 문서만 보고 믿지 말 것.** 반드시 관련 테스트를 재실행하여 확인 후 응답할 것.

## 1. 최상위 원칙
- **진실의 원천 우선순위**: Phase A에서는 ECSS 스펙 원문 > 골든모델. Phase B에서는 골든모델 > RTL. 이 순서를 뒤집지 말 것.
- **스펙 근거 없는 수정 금지**: 골든모델 수정 시 구체적 조항 번호 인용 필수.
- **모호성은 버그가 아니다**: 스펙에 명시적 근거 없으면 DECISION으로 분류, 사람 에스컬레이션.

## 2. 골든모델 초안 작성 규칙 (신규 — 반드시 준수)
- 모든 함수/주요 분기에 `# Spec: §X.X.X` 주석 필수.
- **확신 없는 부분은 절대 그럴듯하게 채우지 말 것.** 아래처럼 명시적으로 드러낼 것:
  ```python
  raise NotImplementedError("TODO: §8.5.3.1 동시성 케이스 미해석 - 확인 필요")
  ```
- 작성한 모든 함수는 `golden_model_confidence` 테이블에 즉시 기록:
  - `confidence='cited'`: 스펙 조항을 직접 인용해 작성
  - `confidence='assumed'`: 스펙에 명시 없어 합리적으로 추정해 작성 (반드시 `todo_note`에 추정 근거 기록)
  - `confidence='todo'`: 미구현 (NotImplementedError 상태)
- **초안은 작성 직후 `verification_status`에 모든 관련 조항을 `status='untested'`로 기록.** "이미 만들었으니 검증됨"으로 착각 금지 — 초안 생성과 검증은 완전히 분리된 단계.

## 3. 스펙 조회 규칙 (전체 재독 + 캐시 재사용)
- 조항 판정이 필요하면 `arbiter_judgments` 테이블에서 동일/유사 질문의 기존 판정을 먼저 조회.
- 기존 판정의 `confidence='high'`면 재사용 가능. `medium`/`low`면 반드시 재조회.
- 재조회 시 대상 조항뿐 아니라 `clause_references`로 연결된 조항까지 함께 확인 (문맥 손실 방지).
- 새 판정은 confidence를 반드시 부여하고 캐시에 저장. confidence='low'인 판정은 자동으로 사람 에스컬레이션.

## 4. Errata vs Decision 분류
- 코드 실행으로 발견된 버그 → ERRATA
- 리뷰 중 발견된 설계 공백/스펙 모호성 → DECISION 레코드 (`spec_harness/decision_log/`)

## 5. 시행착오 학습 규칙 (신규 — 핵심)
- 같은 실수가 2회 이상 반복되면 (동일 `pattern_tag`), 반드시 `mistake_patterns` 테이블에 일반화된 규칙으로 기록.
- 세션 종료 시 `learning-extractor` 서브에이전트가 이번 세션에서 발견된 새 패턴을 기록하고, 기존 패턴과 중복이면 `occurrence_count`만 증가.
- **세션 시작 시 `mistake_patterns`의 `status='active'`인 항목을 반드시 먼저 확인**하고 이번 세션에서 같은 실수를 반복하지 않도록 주의.
- 패턴이 3회 이상 재발하면 (`occurrence_count >= 3`), 프롬프트/훅/스키마 레벨의 구조적 방지책을 추가할 것을 사람에게 제안.

## 6. RTL 수정 규칙 (Phase B)
- RTL 수정은 항상 diff 제안 후 사람 승인. 자동 적용 금지.
- 최종 확인은 Vivado 타이밍/리소스 체크로, 사람이 직접 판단.

## 7. 커밋 규칙
```
fix(golden-model): <요약>

Spec-citation: ECSS-E-ST-50-12C §<조항번호>
Feedback: "<사람이 준 피드백 원문 요약>"
Root-cause: <원인>
Phase: A|B
```
post-commit hook이 이 trailer를 파싱해 `refinement_events` 테이블에 자동 INSERT (commit_sha UNIQUE 제약으로 중복 방지).

## 9. 실행 컨벤션 (개정 — 즉석 인라인 코드 금지, 고정 스크립트 사용 필수)

**핵심 원칙**: `python3 -c "즉석에서 생성한 코드"` 형태는 매번 코드 내용이 달라지기 때문에,
auto mode의 분류기가 사전에 안전을 판단할 수 없어 매번 사람 확인을 요구하게 된다.
이는 auto mode 설정 문제가 아니라 "즉석 생성 코드"라는 방식 자체의 구조적 한계다.
따라서 **반복되는 DB 조회/갱신은 절대 `-c` 인라인으로 새로 짜지 말고, 아래 고정 스크립트를
인자만 바꿔서 호출**한다. 코드 내용이 고정되어 있어야 `permissions.allow`가 정적으로
매칭 가능해지고, 실제로 auto mode의 이점을 누릴 수 있다.

### 고정 스크립트 목록 (`spec_harness/ingest/`)

| 스크립트 | 용도 |
|---|---|
| `check_session_start.py` | 세션 시작 시 검증현황/실수패턴/직전요약/open_items 조회 |
| `check_clause_status.py --prefix <p> [--phase A\|B]` | 특정 조항 범위의 검증상태/confidence/판정캐시 조회 |
| `check_clause_text.py --clause-id <id> [--with-refs]` | 조항 원문 재조회 (spec-arbiter용) |
| `insert_arbiter_judgment.py --clause-id .. --phase .. --verdict .. --confidence .. --question-summary .. --spec-evidence ..` | 판정 결과 저장 |
| `update_confidence.py --function .. [--confidence ..] [--todo-note ..]` | golden_model_confidence 갱신 |
| `update_verification_status.py --clause-id .. --phase .. [--status ..] [--ambiguous] [--scenarios ..]` | verification_status 갱신 |
| `upsert_mistake_pattern.py --tag .. [--description .. --prevention-rule ..]` | 실수 패턴 등록/재발 처리 |
| `insert_session_summary.py --started-at .. --phase .. [--clauses-touched ..] [--new-errata ..] [--new-decisions ..] [--new-mistake-patterns ..] --next-session-priority ..` | 세션 종료 요약 기록 |

호출 형태는 항상 이렇게 고정:
```bash
.venv/bin/python3 spec_harness/ingest/<스크립트명>.py --인자 값 --인자 값
```

### 위 스크립트로 표현 안 되는 새로운 조회가 필요할 때
1. 먼저 기존 스크립트에 옵션을 추가해서 대응 가능한지 검토
2. 정말 새로운 스크립트가 필요하면, 새 `.py` 파일을 `spec_harness/ingest/`에 만들고
   (`db_utils.py`의 `get_conn()`, `now_iso()`, `print_rows()` 재사용) `.claude/settings.json`의
   `permissions.allow`에 그 파일 경로 패턴을 등록. **`-c` 인라인으로 임시 처리하고 넘어가지 말 것.**
3. 스키마 변경(CREATE TABLE 등)처럼 정말 1회성인 작업만 예외적으로 `-c` 인라인 허용,
   이 경우 반드시 사람에게 "왜 예외가 필요한지" 먼저 설명.

### 회귀 테스트 실행
```bash
.venv/bin/python3 spw_ref_model_test_v5.py > spec_harness/ingest/last_test_run.log 2>&1
tail -20 spec_harness/ingest/last_test_run.log
```

### RTL 시뮬레이션
```bash
iverilog -g2012 -o spec_harness/ingest/sim_out <파일 목록>
vvp spec_harness/ingest/sim_out
```
`<파일 목록>`은 항상 명시적으로 나열할 것 (glob `*.sv` 금지).

### git 커밋 (다중 라인 trailer 포함)
```bash
git add <파일>
git commit -m "$(cat <<'EOF'
<제목>

Spec-citation: ECSS-E-ST-50-12C §<조항>
Feedback: "<요약>"
Root-cause: <원인>
Phase: A|B
EOF
)"
```

### 금지 사항
- DB 조회/갱신을 `-c` 인라인으로 즉석 작성하지 말 것 (위 고정 스크립트 우선 사용)
- 같은 작업에 대해 세션마다 다른 bash 문법을 즉흥적으로 선택하지 말 것.

### 이 컨벤션 자체가 지켜지지 않을 때 (신규 — 드리프트 재발 방지)
- 이 §9와 `spec_harness/ingest/*.py` 고정 스크립트는 **반드시 git에 커밋된 상태를 정본으로 삼는다.**
  워크트리로 격리해 작업하는 구조상, 커밋되지 않은 변경은 새 워크트리에 반영되지 않고 매번 사라진다.
  (2026-09-07~08 실제로 이 스크립트 9개가 미커밋 상태로 방치되어 워크트리마다 사라지는 문제 발생 — `mistake_patterns.설정파일-디스크드리프트-미확인` 참고.)
- 이 섹션이나 고정 스크립트를 새로 만들거나 고쳤다면, **그 세션 안에서 바로 커밋(및 가능하면 push)까지 완료**할 것.
  "다음에 커밋하겠다"고 미루지 말 것 — 다음 세션은 새 워크트리에서 시작되므로 미커밋 변경을 볼 수 없다.

## 10. 서브에이전트 사용 규칙
- 골든모델 버그 원인 분석은 반드시 `spec-arbiter` 서브에이전트를 통해 판단 (메인 세션 직접 판단 금지).
- 다이어그램이 관련된 조항은 `clause_images`에서 `vlm_description` 확인 후 참고 (없으면 `diagram-enricher` 먼저 실행).
- 세션 종료 전 `learning-extractor` 서브에이전트로 이번 세션 학습 내용 정리 + `mistake_patterns` 갱신.

