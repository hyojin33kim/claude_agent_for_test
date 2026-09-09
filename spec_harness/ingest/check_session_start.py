#!/usr/bin/env python3
"""
spec_harness/ingest/check_session_start.py

세션 시작 시 필요한 정보를 한 번에 조회:
- Phase A/B 검증 현황 요약
- 활성 mistake_patterns
- 최근 session_summary
- open_items (미인용/모호/미결 decision)
- 미커밋 인프라 파일 경과시간 경고 (신규)
사람 확인 없이 매번 동일한 조회만 수행하는 고정 스크립트.
"""

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from db_utils import get_conn, print_rows

# 인프라 성격 파일 경로 접두사 — 이 안에서 미커밋 상태가 오래 지속되면 경고
INFRA_PREFIXES = (
    "spec_harness/ingest/",
    "CLAUDE.md",
    ".claude/agents/",
    ".claude/commands/",
    ".claude/settings.json",
)
STALE_THRESHOLD_HOURS = 2


def check_uncommitted_infra():
    """미커밋 인프라 파일 중 STALE_THRESHOLD_HOURS 이상 경과한 것을 경고.

    2026-09-08 사고 재발 방지용: 고정 스크립트 9개 + CLAUDE.md 개정이
    검증 완료 후 15시간 넘게 커밋되지 않아 워크트리마다 소실됐던 문제.
    """
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    print("\n--- 미커밋 인프라 파일 경과시간 확인 ---")

    if result.returncode != 0:
        print(f"(git status 실행 실패, 확인 불가: {result.stderr.strip()})")
        return

    now = datetime.now(timezone.utc)
    stale = []

    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        # porcelain 형식: "XY 경로" (앞 2글자 상태코드 + 공백 + 경로)
        path_str = line[3:].strip()
        # 리네임 표시("old -> new") 대응: 화살표 뒤쪽 경로만 사용
        if " -> " in path_str:
            path_str = path_str.split(" -> ", 1)[1]

        if not path_str.startswith(INFRA_PREFIXES):
            continue

        fpath = repo_root / path_str
        if not fpath.exists():
            continue  # 삭제된 파일은 스킵

        mtime = datetime.fromtimestamp(fpath.stat().st_mtime, tz=timezone.utc)
        elapsed_hours = (now - mtime).total_seconds() / 3600
        if elapsed_hours >= STALE_THRESHOLD_HOURS:
            stale.append((path_str, round(elapsed_hours, 1)))

    if not stale:
        print("(경고 없음 — 모든 인프라 파일이 커밋됐거나 최근 변경분)")
    else:
        print(f"⚠ {len(stale)}개 파일이 {STALE_THRESHOLD_HOURS}시간 이상 미커밋 상태:")
        for path_str, hours in sorted(stale, key=lambda x: -x[1]):
            print(f"  - {path_str} ({hours}시간 경과)")
        print("→ 커밋 여부를 지금 확인할 것 (git add/commit 또는 의도적 보류 사유 확인)")


def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT phase, status, COUNT(*) FROM verification_status GROUP BY phase, status"
    )
    print_rows(cur, "verification_status (phase/status 별 개수)")

    cur.execute(
        "SELECT pattern_tag, occurrence_count, prevention_rule FROM mistake_patterns "
        "WHERE status = 'active' ORDER BY occurrence_count DESC"
    )
    print_rows(cur, "mistake_patterns (active)")

    cur.execute(
        "SELECT session_id, ended_at, next_session_priority FROM session_summaries "
        "ORDER BY session_id DESC LIMIT 1"
    )
    print_rows(cur, "직전 session_summary")

    cur.execute("SELECT * FROM open_items")
    print_rows(cur, "open_items (confidence!='cited' 함수 + ambiguous 조항 + 연결된 decisions)")

    conn.close()

    check_uncommitted_infra()


if __name__ == "__main__":
    main()
