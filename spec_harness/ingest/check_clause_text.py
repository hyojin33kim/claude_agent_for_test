#!/usr/bin/env python3
"""
spec_harness/ingest/check_clause_text.py

특정 clause_id(들)의 스펙 원문 전체를 조회. spec-arbiter가 판정 전 재조회할 때 사용.
clause_references로 연결된 조항까지 함께 가져오는 옵션 포함.

사용법:
  .venv/bin/python3 spec_harness/ingest/check_clause_text.py --clause-id 5.4.8
  .venv/bin/python3 spec_harness/ingest/check_clause_text.py --clause-id 5.4.3.2 --with-refs
  .venv/bin/python3 spec_harness/ingest/check_clause_text.py --clause-ids 5.4.3.2,5.4.3.1,5.4.3
"""

import argparse
from db_utils import get_conn


def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--clause-id", help="단일 clause_id")
    group.add_argument("--clause-ids", help="콤마로 구분된 여러 clause_id")
    ap.add_argument("--with-refs", action="store_true",
                     help="clause_references로 연결된 조항까지 함께 조회")
    args = ap.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    if args.clause_id:
        ids = [args.clause_id]
    else:
        ids = [c.strip() for c in args.clause_ids.split(",")]

    for cid in ids:
        cur.execute("SELECT clause_id, title, text_full, parent_clause_id FROM clauses WHERE clause_id = ?", (cid,))
        row = cur.fetchone()
        if row:
            print(f"=== {row[0]} : {row[1]} (parent={row[3]}) ===")
            print(row[2])
            print()
        else:
            print(f"=== {cid} : NOT FOUND ===\n")

        if args.with_refs:
            cur.execute(
                "SELECT to_clause, relation_type FROM clause_references WHERE from_clause = ?",
                (cid,),
            )
            refs = cur.fetchall()
            if refs:
                print(f"--- {cid}의 참조 조항 ---")
                for to_clause, rel in refs:
                    cur.execute("SELECT title, text_full FROM clauses WHERE clause_id = ?", (to_clause,))
                    r = cur.fetchone()
                    if r:
                        print(f"  [{rel}] {to_clause} : {r[0]}")
                        print(f"  {r[1][:500]}...")
                    print()

    conn.close()


if __name__ == "__main__":
    main()
