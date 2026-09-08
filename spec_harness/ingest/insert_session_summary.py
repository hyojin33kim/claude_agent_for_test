#!/usr/bin/env python3
"""
spec_harness/ingest/insert_session_summary.py

session_summaries에 세션 종료 요약을 기록.
learning-extractor 서브에이전트가 세션 종료 시 반복 호출하는 고정 스크립트.

사용법:
  .venv/bin/python3 spec_harness/ingest/insert_session_summary.py \\
    --started-at "2026-09-07T00:00:00Z" \\
    --phase A \\
    --clauses-touched "" \\
    --new-errata "" \\
    --new-decisions "" \\
    --new-mistake-patterns "병렬세션-중복작업-미확인, 설정파일-디스크드리프트-미확인" \\
    --next-session-priority "..."

ended_at은 항상 현재 시각(datetime('now', UTC))으로 자동 기록됨.
"""

import argparse
from db_utils import get_conn, now_iso, print_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--started-at", required=True, help="세션 시작 시각 (ISO 8601)")
    ap.add_argument("--phase", required=True, help="A 또는 B")
    ap.add_argument("--clauses-touched", default="", help="이번 세션에서 다룬 clause_id 목록 (콤마 구분)")
    ap.add_argument("--new-errata", default="", help="신규 ERRATA 요약 (콤마 구분)")
    ap.add_argument("--new-decisions", default="", help="신규 DECISION 요약 (콤마 구분)")
    ap.add_argument("--new-mistake-patterns", default="", help="신규/재발 mistake pattern_tag 목록 (콤마 구분)")
    ap.add_argument("--next-session-priority", required=True, help="다음 세션이 바로 참고할 구체적 제안")
    args = ap.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """INSERT INTO session_summaries
           (started_at, ended_at, phase, clauses_touched, new_errata,
            new_decisions, new_mistake_patterns, next_session_priority)
           VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?)""",
        (
            args.started_at,
            args.phase,
            args.clauses_touched,
            args.new_errata,
            args.new_decisions,
            args.new_mistake_patterns,
            args.next_session_priority,
        ),
    )
    conn.commit()
    session_id = cur.lastrowid
    print(f"session_summaries 기록 완료: session_id={session_id}")

    cur.execute("SELECT * FROM session_summaries WHERE session_id = ?", (session_id,))
    print_rows(cur, "확인")
    conn.close()


if __name__ == "__main__":
    main()
