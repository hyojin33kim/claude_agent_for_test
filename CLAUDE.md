# SpaceWire Spec2RTL — Project Rules (Always Loaded)

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

## 8. 서브에이전트 사용 규칙
- 골든모델 버그 원인 분석은 반드시 `spec-arbiter` 서브에이전트를 통해 판단 (메인 세션 직접 판단 금지).
- 다이어그램이 관련된 조항은 `clause_images`에서 `vlm_description` 확인 후 참고 (없으면 `diagram-enricher` 먼저 실행).
- 세션 종료 전 `learning-extractor` 서브에이전트로 이번 세션 학습 내용 정리 + `mistake_patterns` 갱신.

## 9. 작업 파일 위치 규칙
- 조회 결과 덤프, 진단용 스크립트 등 임시 산출물은 항상 `spec_harness/ingest/` 안에 만들 것. `/tmp` 등 프로젝트 밖 경로 사용 금지 — 다음 세션이 추적/정리할 수 없음.
