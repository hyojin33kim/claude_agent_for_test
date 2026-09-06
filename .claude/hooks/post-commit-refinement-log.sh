#!/usr/bin/env bash
# post-commit hook: 최근 커밋 메시지의 trailer를 파싱하여
# spec_harness.db의 refinement_events 테이블에 INSERT한다.
# commit_sha에 UNIQUE 제약이 걸려있어 중복 삽입은 SQLite가 자체적으로 막는다
# (기존 sed 기반 파일 dedup보다 견고함).
#
# 항상 exit 0 — soft mode, 커밋 자체를 막지 않는다.

set -uo pipefail

DB_PATH="spec_harness/spec_harness.db"
COMMIT_SHA=$(git rev-parse HEAD 2>/dev/null)
COMMIT_MSG=$(git log -1 --pretty=%B 2>/dev/null)

if [ -z "$COMMIT_SHA" ] || [ ! -f "$DB_PATH" ]; then
  exit 0
fi

extract_trailer() {
  echo "$COMMIT_MSG" | grep -E "^${1}:" | sed -E "s/^${1}:[[:space:]]*//" | head -1
}

SPEC_CITATION=$(extract_trailer "Spec-citation")
FEEDBACK=$(extract_trailer "Feedback")
ROOT_CAUSE=$(extract_trailer "Root-cause")
PHASE=$(extract_trailer "Phase")

if [ -z "$SPEC_CITATION" ] && [ -z "$FEEDBACK" ] && [ -z "$ROOT_CAUSE" ]; then
  exit 0
fi

# Spec-citation 문자열에서 clause_id만 추출 (예: "ECSS-E-ST-50-12C §8.5.2.3" -> "8.5.2.3")
CLAUSE_ID=$(echo "$SPEC_CITATION" | grep -oE '[0-9]+(\.[0-9]+){1,5}' | head -1)

python3 - "$COMMIT_SHA" "$PHASE" "$CLAUSE_ID" "$SPEC_CITATION" "$FEEDBACK" "$ROOT_CAUSE" <<'PYEOF'
import sqlite3
import sys
from datetime import datetime, timezone

commit_sha, phase, clause_id, spec_citation, feedback, root_cause = sys.argv[1:7]
db_path = "spec_harness/spec_harness.db"

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """INSERT OR IGNORE INTO refinement_events
           (timestamp, phase, commit_sha, clause_id, spec_citation, feedback, root_cause)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            phase or None,
            commit_sha,
            clause_id or None,
            spec_citation or None,
            feedback or None,
            root_cause or None,
        ),
    )
    conn.commit()
    if cur.rowcount > 0:
        print(f"[refinement-log] appended entry for commit {commit_sha[:8]}", file=sys.stderr)
    conn.close()
except Exception as e:
    print(f"[refinement-log][warn] failed: {e}", file=sys.stderr)
PYEOF

exit 0
