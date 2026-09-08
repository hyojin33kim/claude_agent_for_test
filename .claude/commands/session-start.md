---
description: 세션 시작 시 컨텍스트 재구성 — DB 상태 확인, 최근 학습/실수 패턴 확인, 코드 재실행 검증까지 자동화.
---

1. DB에서 현재 상태 파악 (CLAUDE.md §9 SQL 실행 컨벤션 준수):
   ```bash
   .venv/bin/python3 -c "
   import sqlite3
   conn = sqlite3.connect('spec_harness/spec_harness.db')
   cur = conn.cursor()
   cur.execute('SELECT phase, status, COUNT(*) FROM verification_status GROUP BY phase, status')
   print(cur.fetchall())
   cur.execute('SELECT * FROM mistake_patterns WHERE status = \"active\" ORDER BY occurrence_count DESC')
   print(cur.fetchall())
   cur.execute('SELECT * FROM session_summaries ORDER BY session_id DESC LIMIT 1')
   print(cur.fetchone())
   cur.execute('SELECT * FROM open_items')
   print(cur.fetchall())
   "
   ```
   마지막 `open_items` 쿼리는 `confidence != 'cited'`인 함수와 `ambiguous=1`인 조항(및 연결된 `decisions` 레코드)을 한 번에 보여준다 — 사람 판단이 아직 필요한 항목 전체 목록.
2. `git log --oneline -15`로 최근 커밋 확인.
3. **`mistake_patterns`의 active 항목을 반드시 먼저 읽고, 오늘 세션에서 같은 실수를 반복하지 않도록 유의할 것.** 특히 occurrence_count가 높은 패턴은 사람에게도 다시 한번 상기시킬 것.
4. 핵심 파일 재실행하여 문서/DB 주장과 실제 상태 일치 확인 (CLAUDE.md §9 회귀 테스트 실행 컨벤션 준수 — 파이프 대신 파일 리다이렉션):
   ```bash
   .venv/bin/python3 spw_ref_model_test_v5.py > spec_harness/ingest/session_start_test.log 2>&1
   tail -20 spec_harness/ingest/session_start_test.log
   ```
5. 재실행 결과와 DB의 `verification_status`가 다르면, 다르다는 사실을 먼저 보고하고 어느 쪽이 최신 진실인지 확인받는다.
6. 직전 `session_summaries.next_session_priority`를 사람에게 제시하고 오늘 작업 방향 확인받는다.
