-- spec_harness/schema.sql
-- SQLite 스키마. 최초 1회 `sqlite3 spec_harness.db < schema.sql` 로 초기화.

PRAGMA foreign_keys = ON;

-- 조항 텍스트 (Docling 파싱 결과)
CREATE TABLE IF NOT EXISTS clauses (
  clause_id TEXT PRIMARY KEY,
  title TEXT,
  text_full TEXT,              -- Docling이 추출한 원문 전체 (재서술 아님, 원문 그대로 — 내부 DB용이라 저작권상 외부 노출 안 함 전제)
  page_ref INTEGER,
  parent_clause_id TEXT,
  ingested_at TEXT
);

-- 조항 간 명시적 참조 관계 ("see §X", "as defined in §Y" 등 인라인 참조)
CREATE TABLE IF NOT EXISTS clause_references (
  from_clause TEXT,
  to_clause TEXT,
  relation_type TEXT,          -- 'see_also' | 'depends_on' | 'overrides' | 'defines_term_used_by'
  FOREIGN KEY (from_clause) REFERENCES clauses(clause_id),
  FOREIGN KEY (to_clause) REFERENCES clauses(clause_id)
);

-- 다이어그램/이미지 (Docling 추출 + VLM 보강 분리 단계)
CREATE TABLE IF NOT EXISTS clause_images (
  image_id INTEGER PRIMARY KEY AUTOINCREMENT,
  clause_id TEXT,
  image_path TEXT,
  image_type TEXT,              -- 'state_diagram' | 'timing_diagram' | 'table' | 'other'
  vlm_description TEXT,         -- NULL이면 아직 VLM 보강 안 됨
  vlm_model_used TEXT,
  bbox TEXT,
  FOREIGN KEY (clause_id) REFERENCES clauses(clause_id)
);

-- 검증 상태 (Phase A/B 진행 상황 트래커 — spec_coverage.yaml 대체)
CREATE TABLE IF NOT EXISTS verification_status (
  clause_id TEXT,
  phase TEXT,                   -- 'A' | 'B'
  status TEXT,                  -- 'untested' | 'golden_model_validated' | 'rtl_validated'
  ambiguous INTEGER DEFAULT 0,  -- 0/1
  last_verified_at TEXT,
  covered_by_scenarios TEXT,    -- JSON 배열 문자열, 예: '["scenario_14","scenario_15"]'
  PRIMARY KEY (clause_id, phase),
  FOREIGN KEY (clause_id) REFERENCES clauses(clause_id)
);

-- spec-arbiter 판정 캐시 ("전체 재독 + 결과 재사용" 구현체)
CREATE TABLE IF NOT EXISTS arbiter_judgments (
  judgment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  clause_id TEXT,
  phase TEXT,
  question_hash TEXT,           -- 판정 질문 내용의 해시. 동일 질문 재판정 감지용
  question_summary TEXT,        -- 사람이 읽을 수 있는 질문 요약
  verdict TEXT,                 -- 'A' | 'B' | 'C'
  confidence TEXT,              -- 'high' | 'medium' | 'low'
  spec_evidence TEXT,           -- 재조회 시 근거로 삼은 원문 재서술 (인용 아님, paraphrase)
  reused_count INTEGER DEFAULT 0,  -- 이 판정이 캐시로 재사용된 횟수 (신뢰도 검증에 활용)
  created_at TEXT,
  FOREIGN KEY (clause_id) REFERENCES clauses(clause_id)
);

-- 피드백→수정 이력 (refinement_log.jsonl 대체, post-commit hook이 INSERT)
CREATE TABLE IF NOT EXISTS refinement_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT,
  phase TEXT,
  commit_sha TEXT UNIQUE,       -- UNIQUE 제약으로 중복 삽입 자체 차단 (기존 sed dedup보다 견고)
  clause_id TEXT,
  spec_citation TEXT,
  feedback TEXT,
  root_cause TEXT,
  fix_summary TEXT,
  errata_or_decision TEXT,
  FOREIGN KEY (clause_id) REFERENCES clauses(clause_id)
);

-- 골든모델 함수 단위 신뢰도 추적 (필수 요구사항 반영)
CREATE TABLE IF NOT EXISTS golden_model_confidence (
  function_name TEXT PRIMARY KEY,
  file_path TEXT,
  spec_citation TEXT,           -- 이 함수가 근거한 조항. NULL이면 인용 없이 작성됨 → 위험 표시
  confidence TEXT,              -- 'cited' | 'assumed' | 'todo'
  todo_note TEXT,
  created_at TEXT,
  last_reviewed_at TEXT
);

-- === 이번 턴 논의로 추가: 시행착오 학습 테이블 ===
-- AI가 반복하는 실수 패턴을 구조화하여 다음 세션/턴에 자동 주입하기 위한 테이블
CREATE TABLE IF NOT EXISTS mistake_patterns (
  pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
  pattern_tag TEXT,             -- 예: '신호semantics-미검증', '스펙모호-임의판정', '캐시미활용-중복재조회'
  description TEXT,             -- 패턴에 대한 일반화된 설명 (특정 사건이 아니라 재사용 가능한 규칙)
  first_seen_event_id INTEGER,  -- refinement_events 또는 arbiter_judgments 참조
  occurrence_count INTEGER DEFAULT 1,
  prevention_rule TEXT,         -- 이 패턴을 막기 위해 프롬프트/훅/스키마에 반영한 내용
  status TEXT,                  -- 'active' | 'mitigated' | 'monitoring'
  last_occurred_at TEXT
);

-- 세션 단위 메타 요약 (learning-extractor가 세션 종료 시 기록)
CREATE TABLE IF NOT EXISTS session_summaries (
  session_id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT,
  ended_at TEXT,
  phase TEXT,
  clauses_touched TEXT,          -- JSON 배열
  new_errata TEXT,               -- JSON 배열
  new_decisions TEXT,            -- JSON 배열
  new_mistake_patterns TEXT,     -- JSON 배열 (mistake_patterns.pattern_id 참조)
  next_session_priority TEXT     -- 다음 세션에게 남기는 우선순위 제안
);

CREATE INDEX IF NOT EXISTS idx_clause_refs_from ON clause_references(from_clause);
CREATE INDEX IF NOT EXISTS idx_verification_status ON verification_status(status, phase);
CREATE INDEX IF NOT EXISTS idx_arbiter_hash ON arbiter_judgments(question_hash);
CREATE INDEX IF NOT EXISTS idx_mistake_tag ON mistake_patterns(pattern_tag);
