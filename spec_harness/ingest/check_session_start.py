#!/usr/bin/env python3
"""
spec_harness/ingest/check_session_start.py

세션 시작 시 필요한 정보를 한 번에 조회:
- Phase A/B 검증 현황 요약
- 활성 mistake_patterns
- 최근 session_summary
사람 확인 없이 매번 동일한 조회만 수행하는 고정 스크립트.
"""

from db_utils import get_conn, print_rows


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


if __name__ == "__main__":
    main()
