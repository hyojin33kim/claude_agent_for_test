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

## 9. 실행 컨벤션 (신규 — 반드시 준수, 예측 가능한 권한 관리를 위함)

이 프로젝트의 모든 커맨드/서브에이전트 문서(`.claude/commands/*.md`, `.claude/agents/*.md`)에
등장하는 SQL/Python 예시는 **지시일 뿐 실행 형태를 규정하지 않는다.** 실제 Bash 실행 시
아래 고정된 형태만 사용할 것. 형태가 흔들리면 `.claude/settings.json`의 `permissions.allow`
화이트리스트가 매번 어긋나 불필요한 승인 요청이 반복된다.

### SQL 조회/갱신
항상 아래 형태로 실행 (heredoc, `python3 -c`, `sqlite3` CLI 등 다른 방식 사용 금지):
```bash
.venv/bin/python3 -c "
import sqlite3
conn = sqlite3.connect('spec_harness/spec_harness.db')
cur = conn.cursor()
cur.execute('''<SQL>''')
...
conn.commit()  # 갱신 시에만
"
```
- 인터프리터는 항상 `.venv/bin/python3` (프로젝트 루트 기준 상대경로). `python3`, `.venv/bin/python`(3 없이) 등 변형 금지.
- 코드는 항상 `-c "..."` 인라인 방식. `<<EOF` heredoc, 파일로 저장 후 실행 등 금지.
- 출력이 길어서 저장이 필요하면 반드시 프로젝트 내부 경로에 저장 (`spec_harness/ingest/*.txt` 등). `/tmp` 등 작업 디렉토리 밖에 쓰지 말 것 (읽기 차단됨).

### 회귀 테스트 실행
```bash
.venv/bin/python3 spw_ref_model_test_v5.py
```
파이프(`| tail`, `| head`)가 필요하면 별도 호출로 나눌 것 — 결과를 파일로 저장 후 `cat`/`grep`으로 확인:
```bash
.venv/bin/python3 spw_ref_model_test_v5.py > spec_harness/ingest/last_test_run.log 2>&1
tail -20 spec_harness/ingest/last_test_run.log
```

### RTL 시뮬레이션
```bash
iverilog -g2012 -o spec_harness/ingest/sim_out <파일 목록>
vvp spec_harness/ingest/sim_out
```
`<파일 목록>`은 항상 명시적으로 나열할 것 (glob `*.sv` 금지 — 의도치 않은 파일 포함 방지).

### git 커밋 (다중 라인 trailer 포함)
항상 아래 고정 heredoc 형태만 사용 (이 형태 하나만 화이트리스트에 등록됨):
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
- 같은 작업(SQL 조회, 테스트 실행, 커밋)에 대해 세션마다 다른 bash 문법을 즉흥적으로 선택하지 말 것.
- 위 형태로 표현 불가능한 특수한 경우에만 예외적으로 다른 형태를 쓰고, 그 경우 왜 예외가 필요한지 사람에게 먼저 설명할 것.

## 10. 서브에이전트 사용 규칙
- 골든모델 버그 원인 분석은 반드시 `spec-arbiter` 서브에이전트를 통해 판단 (메인 세션 직접 판단 금지).
- 다이어그램이 관련된 조항은 `clause_images`에서 `vlm_description` 확인 후 참고 (없으면 `diagram-enricher` 먼저 실행).
- 세션 종료 전 `learning-extractor` 서브에이전트로 이번 세션 학습 내용 정리 + `mistake_patterns` 갱신.

