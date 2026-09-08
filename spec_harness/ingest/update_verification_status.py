#!/usr/bin/env python3
"""
spec_harness/ingest/update_verification_status.py

verification_status 테이블의 특정 clause_id/phase 상태를 갱신.

사용법:
  .venv/bin/python3 spec_harness/ingest/update_verification_status.py \\
    --clause-id 5.4.8 --phase A --status golden_model_validated \\
    --scenarios "scenario_001_disconnect_boundary"

  # 스펙 모호로 종결하는 경우
  .venv/bin/python3 spec_harness/ingest/update_verification_status.py \\
    --clause-id 5.4.8 --phase A --ambiguous \\
    --scenarios "scenario_001_disconnect_boundary;DECISION-01"
"""

import argparse
from db_utils import get_conn, now_iso, print_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clause-id", required=True)
    ap.add_argument("--phase", required=True, choices=["A", "B"])
    ap.add_argument("--status", choices=["untested", "golden_model_validated", "rtl_validated"], default=None)
    ap.add_argument("--ambiguous", action="store_true", help="ambiguous=1로 설정")
    ap.add_argument("--scenarios", default=None, help="covered_by_scenarios 문자열")
    args = ap.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    sets = ["last_verified_at = ?"]
    params = [now_iso()]
    if args.status is not None:
        sets.append("status = ?")
        params.append(args.status)
    if args.ambiguous:
        sets.append("ambiguous = 1")
    if args.scenarios is not None:
        sets.append("covered_by_scenarios = ?")
        params.append(args.scenarios)
    params += [args.clause_id, args.phase]

    cur.execute(
        f"UPDATE verification_status SET {', '.join(sets)} WHERE clause_id = ? AND phase = ?",
        params,
    )
    conn.commit()
    print(f"updated rows: {cur.rowcount}")

    cur.execute(
        "SELECT clause_id, phase, status, ambiguous, covered_by_scenarios FROM verification_status "
        "WHERE clause_id = ? AND phase = ?",
        (args.clause_id, args.phase),
    )
    print_rows(cur, "확인")
    conn.close()


if __name__ == "__main__":
    main()
