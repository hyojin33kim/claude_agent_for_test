"""
spec_harness/ingest/db_utils.py

모든 spec_harness 스크립트가 공유하는 DB 접속 헬퍼.
경로는 항상 프로젝트 루트 기준 상대경로(spec_harness/spec_harness.db)로 고정.
"""

import sqlite3
import datetime
from pathlib import Path

DB_PATH = "spec_harness/spec_harness.db"


def get_conn():
    if not Path(DB_PATH).exists():
        raise FileNotFoundError(
            f"{DB_PATH} 를 찾을 수 없습니다. 프로젝트 루트(claude_agent)에서 실행했는지 확인하세요."
        )
    return sqlite3.connect(DB_PATH)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def print_rows(cur, label=None):
    if label:
        print(f"--- {label} ---")
    cols = [d[0] for d in cur.description] if cur.description else []
    if cols:
        print(cols)
    for row in cur.fetchall():
        print(row)
