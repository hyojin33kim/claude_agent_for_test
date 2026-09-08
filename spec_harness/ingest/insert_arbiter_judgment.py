#!/usr/bin/env python3
"""
spec_harness/ingest/insert_arbiter_judgment.py

spec-arbiter의 판정 결과를 arbiter_judgments 테이블에 저장.
코드 자체는 고정, 판정 내용만 인자로 받음 -> auto mode 화이트리스트 가능.

사용법:
  .venv/bin/python3 spec_harness/ingest/insert_arbiter_judgment.py \\
    --clause-id "5.4.8.c" --phase A --verdict B --confidence high \\
    --question-summary "is_disconnect 727ns threshold 승격 여부 판정" \\
    --spec-evidence "5.4.8.c: 727ns~1us 범위 규정, 단일값 미지정..."
"""

import argparse
import hashlib
from db_utils import get_conn, now_iso, print_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clause-id", required=True)
    ap.add_argument("--phase", required=True, choices=["A", "B"])
    ap.add_argument("--verdict", required=True, choices=["A", "B", "C"])
    ap.add_argument("--confidence", required=True, choices=["high", "medium", "low"])
    ap.add_argument("--question-summary", required=True)
    ap.add_argument("--spec-evidence", required=True)
    args = ap.parse_args()

    question_hash = hashlib.md5(
        (args.clause_id + args.phase + args.question_summary).encode("utf-8")
    ).hexdigest()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO arbiter_judgments
           (clause_id, phase, question_hash, question_summary, verdict, confidence,
            spec_evidence, reused_count, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
        (args.clause_id, args.phase, question_hash, args.question_summary,
         args.verdict, args.confidence, args.spec_evidence, now_iso()),
    )
    conn.commit()
    print(f"inserted judgment_id: {cur.lastrowid}")

    cur.execute(
        "SELECT judgment_id, clause_id, phase, verdict, confidence FROM arbiter_judgments "
        "WHERE clause_id = ? ORDER BY created_at DESC",
        (args.clause_id,),
    )
    print_rows(cur, "확인")
    conn.close()


if __name__ == "__main__":
    main()
