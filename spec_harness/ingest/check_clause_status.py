#!/usr/bin/env python3
"""
spec_harness/ingest/check_clause_status.py

특정 조항 prefix에 대한 검증 상태 / confidence / 판정 캐시를 한 번에 조회.

사용법:
  .venv/bin/python3 spec_harness/ingest/check_clause_status.py --prefix 5.4.8
  .venv/bin/python3 spec_harness/ingest/check_clause_status.py --prefix 5.5 --phase B
"""

import argparse
from db_utils import get_conn, print_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True, help="clause_id prefix, 예: 5.4.8 또는 5.5")
    ap.add_argument("--phase", default=None, choices=["A", "B"], help="생략하면 A/B 모두 조회")
    args = ap.parse_args()

    conn = get_conn()
    cur = conn.cursor()
    like = f"{args.prefix}%"

    if args.phase:
        cur.execute(
            "SELECT clause_id, phase, status, ambiguous, covered_by_scenarios "
            "FROM verification_status WHERE clause_id LIKE ? AND phase = ? ORDER BY clause_id",
            (like, args.phase),
        )
    else:
        cur.execute(
            "SELECT clause_id, phase, status, ambiguous, covered_by_scenarios "
            "FROM verification_status WHERE clause_id LIKE ? ORDER BY clause_id, phase",
            (like,),
        )
    print_rows(cur, f"verification_status ({args.prefix}%)")

    cur.execute(
        "SELECT function_name, spec_citation, confidence, todo_note "
        "FROM golden_model_confidence WHERE spec_citation LIKE ? ORDER BY spec_citation",
        (like,),
    )
    print_rows(cur, f"golden_model_confidence ({args.prefix}%)")

    cur.execute(
        "SELECT judgment_id, clause_id, phase, verdict, confidence, reused_count, created_at "
        "FROM arbiter_judgments WHERE clause_id LIKE ? ORDER BY created_at DESC",
        (like,),
    )
    print_rows(cur, f"arbiter_judgments ({args.prefix}%)")

    conn.close()


if __name__ == "__main__":
    main()
