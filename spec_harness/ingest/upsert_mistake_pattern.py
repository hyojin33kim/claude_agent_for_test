#!/usr/bin/env python3
"""
spec_harness/ingest/upsert_mistake_pattern.py

mistake_patterns에 새 패턴을 등록하거나, 기존 태그가 있으면 occurrence_count만 증가.

사용법 (신규):
  .venv/bin/python3 spec_harness/ingest/upsert_mistake_pattern.py \\
    --tag "범위규정-단일값혼동" \\
    --description "스펙에 정확한 계산식이 있으면 무조건 단일값 강제로 오인..." \\
    --prevention-rule "판정 전 반드시 문장 형태 확인: ~보다 크고 ~보다 작다는 범위 규정..."

사용법 (기존 태그 재발 — description/rule 생략 가능):
  .venv/bin/python3 spec_harness/ingest/upsert_mistake_pattern.py --tag "신호semantics-미검증"
"""

import argparse
from db_utils import get_conn, now_iso, print_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--description", default=None)
    ap.add_argument("--prevention-rule", default=None)
    args = ap.parse_args()

    conn = get_conn()
    cur = conn.cursor()
    now = now_iso()

    cur.execute("SELECT pattern_id, occurrence_count FROM mistake_patterns WHERE pattern_tag = ?", (args.tag,))
    existing = cur.fetchone()

    if existing:
        pattern_id, count = existing
        cur.execute(
            "UPDATE mistake_patterns SET occurrence_count = ?, last_occurred_at = ? WHERE pattern_id = ?",
            (count + 1, now, pattern_id),
        )
        print(f"기존 패턴 재발 처리: pattern_id={pattern_id}, occurrence_count={count + 1}")
    else:
        if not args.description or not args.prevention_rule:
            print("신규 패턴 등록에는 --description 과 --prevention-rule 이 모두 필요합니다.")
            conn.close()
            return
        cur.execute(
            """INSERT INTO mistake_patterns
               (pattern_tag, description, occurrence_count, prevention_rule, status, last_occurred_at)
               VALUES (?, ?, 1, ?, 'active', ?)""",
            (args.tag, args.description, args.prevention_rule, now),
        )
        print(f"신규 패턴 등록: pattern_id={cur.lastrowid}")

    conn.commit()
    cur.execute("SELECT * FROM mistake_patterns WHERE pattern_tag = ?", (args.tag,))
    print_rows(cur, "확인")
    conn.close()


if __name__ == "__main__":
    main()
