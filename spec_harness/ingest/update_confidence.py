#!/usr/bin/env python3
"""
spec_harness/ingest/update_confidence.py

golden_model_confidence 테이블의 특정 함수 confidence/todo_note를 갱신.

사용법:
  .venv/bin/python3 spec_harness/ingest/update_confidence.py \\
    --function is_disconnect --confidence assumed \\
    --todo-note "5.4.8.c는 727ns~1us 범위만 규정..."

  # confidence를 안 바꾸고 todo_note만 갱신하려면 --confidence 생략
  .venv/bin/python3 spec_harness/ingest/update_confidence.py \\
    --function reset_data_strobe_lines \\
    --todo-note "민감/중요 사안으로 의도적 보류..."
"""

import argparse
from db_utils import get_conn, now_iso, print_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--function", required=True, help="function_name")
    ap.add_argument("--confidence", choices=["cited", "assumed", "todo"], default=None)
    ap.add_argument("--todo-note", default=None)
    args = ap.parse_args()

    if args.confidence is None and args.todo_note is None:
        print("--confidence 또는 --todo-note 중 최소 하나는 지정해야 합니다.")
        return

    conn = get_conn()
    cur = conn.cursor()

    sets = ["last_reviewed_at = ?"]
    params = [now_iso()]
    if args.confidence is not None:
        sets.append("confidence = ?")
        params.append(args.confidence)
    if args.todo_note is not None:
        sets.append("todo_note = ?")
        params.append(args.todo_note)
    params.append(args.function)

    cur.execute(
        f"UPDATE golden_model_confidence SET {', '.join(sets)} WHERE function_name = ?",
        params,
    )
    conn.commit()
    print(f"updated rows: {cur.rowcount}")

    cur.execute(
        "SELECT function_name, confidence, todo_note, last_reviewed_at "
        "FROM golden_model_confidence WHERE function_name = ?",
        (args.function,),
    )
    print_rows(cur, "확인")
    conn.close()


if __name__ == "__main__":
    main()
