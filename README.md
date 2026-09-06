# 출처
  Project : SpaceWire-OneShot-RTL refine
  채팅 세션 : ##Claude 에이전트 -미적용 Skills ·하드 가드레일·오케스트레이션·병렬화

# Spec2RTL Harness v2 (SQLite 기반)

v1(YAML/jsonl 파일 기반)에서 아래 논의를 반영해 개정한 버전입니다.

## v1 → v2 변경 사항

| 항목 | v1 | v2 |
|---|---|---|
| 커버리지/이력 저장소 | `spec_coverage.yaml`, `refinement_log.jsonl` | `spec_harness.db` (SQLite) |
| 조항 간 관계 | 표현 불가 | `clause_references` 테이블 (그래프 순회 가능) |
| 판정 재사용 | 매번 재조회 | `arbiter_judgments` 캐시 테이블 + confidence 등급 |
| 판정 신뢰도 | 없음 | confidence(high/medium/low), low는 자동 에스컬레이션 |
| 다이어그램 | 미고려 | Docling 이미지 추출 + VLM 별도 보강 (`clause_images`) |
| 골든모델 신뢰도 | 없음 | `golden_model_confidence` (함수 단위, cited/assumed/todo) |
| 초안 생성 | 별도 규칙 없음 | `/draft-golden-model` — 0% 검증 상태로 명시적 시작 |
| 반복 실수 학습 | 없음 | `mistake_patterns` 테이블 — 세션 간 자동 전달 |
| 커밋 중복 방지 | sed 기반, 취약 | `commit_sha UNIQUE` 제약, SQLite가 보장 |

## 구조

```
CLAUDE.md
.claude/
  agents/
    spec-gap-finder.md      ← SQLite 쿼리로 미검증 조항 탐색 + mistake_pattern 연계
    testcase-writer.md      ← 새 시나리오 작성 (mistake_pattern 재발 방지 케이스 포함)
    spec-arbiter.md         ← 캐시 우선 조회 + confidence 등급 + 패턴 태깅
    learning-extractor.md   ← 세션 종료 시 mistake_patterns/session_summaries 갱신
    diagram-enricher.md     ← VLM으로 다이어그램 해석 (신호 semantics 오독 방지 특화)
  commands/
    session-start.md        ← mistake_patterns 확인 포함
    draft-golden-model.md   ← 초안 생성 (인용 강제 + confidence 기록 + 0% 등록)
    grow-golden-model.md    ← Phase A 루프
    grow-rtl.md             ← Phase B 루프
    ingest-spec.md          ← PDF → Docling → SQLite 최초 적재
  hooks/
    post-commit-refinement-log.sh   ← trailer → refinement_events INSERT
  settings.json.example
spec_harness/
  schema.sql                ← SQLite 스키마 정의 (실행 완료, 테이블 생성 확인됨)
  spec_harness.db           ← 실제 DB 파일 (스키마 적용됨, 데이터는 비어있음)
  draft_prompt_template.md  ← 초안 생성용 재사용 프롬프트 (커맨드 밖에서도 사용)
  ingest/
    docling_ingest.py       ← PDF 파싱 스켈레톤 (실제 PDF로 테스트 필요)
    vlm_enrich.py            ← VLM 이미지 해석 스켈레톤 (API 호출부 미완성 — 연결 필요)
  decision_log/
    TEMPLATE.md
```

## 핵심 신규 테이블: mistake_patterns (질문에 대한 답)

**"시행착오를 어떻게 저장하고 다음 턴에 활용하는가"**에 대한 구체적 구현입니다.

```sql
CREATE TABLE mistake_patterns (
  pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
  pattern_tag TEXT,             -- 예: '신호semantics-미검증'
  description TEXT,             -- 일반화된 설명
  occurrence_count INTEGER,     -- 재발 횟수
  prevention_rule TEXT,         -- 구체적 행동 지침
  status TEXT,                  -- active | mitigated | monitoring
  last_occurred_at TEXT
);
```

**작동 흐름**:
1. `spec-arbiter`가 판정 중 실수를 발견하면 → 기존 패턴과 일치 확인, 없으면 신규 후보 제안
2. `learning-extractor`가 세션 종료 시 정식으로 INSERT/UPDATE
3. **다음 세션 `/session-start`가 `status='active'`인 패턴을 자동으로 읽어와 사람과 AI 모두에게 상기**
4. `occurrence_count >= 3`이 되면 "프롬프트로는 부족, 구조적 방지책 필요"를 자동 제안
   (예: 신호 semantics 오독이 3번째 재발하면 → diagram-enricher 프롬프트에 이미 넣어둔
   "레벨 신호와 펄스 신호 구분" 경고가 실제로는 효과가 없다는 뜻이므로, 검증 스크립트로
   자동 체크하는 방식으로 격상해야 함을 시사)

이 구조의 핵심은 **"학습 내용이 특정 세션의 대화 기록에 묻히지 않고, 쿼리 가능한 구조화 데이터로 남아 다음 세션이 명시적으로 조회한다"**는 점입니다. CLAUDE.md의 "세션 시작 시 mistake_patterns 확인"이 이걸 매 세션 강제합니다.

## 설치

```bash
cp -r spec2rtl-v2/.claude spec2rtl-v2/spec_harness spec2rtl-v2/CLAUDE.md /home/hyojinkim/work/spec2rtl/
cd /home/hyojinkim/work/spec2rtl/
pip install docling --break-system-packages   # ingest-spec 실행 전 필요
```

`.claude/settings.json.example`을 실제 `settings.json`에 병합.

## 실행 순서

```
/ingest-spec              ← 최초 1회, ECSS PDF를 DB에 적재
/draft-golden-model        ← 모듈별 초안 생성 (0% 검증 상태로 시작)
/grow-golden-model          ← Phase A 반복
/grow-rtl                   ← Phase B 반복 (커버리지 90% 이상 시)
```

매 세션: `/session-start`로 열고, 세션 끝에 `learning-extractor` 서브에이전트 호출.

## 아직 미완성 / 실행하며 채워야 할 부분

1. `docling_ingest.py`의 조항 파싱 정규식이 실제 PDF 목차 형식과 맞는지 미검증 — 1차 실행 후 조정 필요
2. `vlm_enrich.py`의 실제 API 호출부(`client.messages.create`)가 주석 처리되어 있음 — 실제 연결 필요
3. 이미지-조항 매핑(`clause_images.clause_id`) 로직이 Docling의 provenance 정보를 아직 활용 안 함 — 골격만 있음
4. `mistake_patterns`의 최초 데이터는 비어있음 — 기존 대화에서 이미 알려진 패턴(`신호semantics-미검증` 등)을 수동으로 1차 INSERT 해두는 게 콜드스타트에 도움될 것
