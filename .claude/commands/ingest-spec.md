---
description: ECSS 스펙 PDF를 Docling으로 파싱하여 spec_harness.db에 최초 적재한다 (1회성, 이후는 증분 갱신).
---

1. `spec_harness/ingest/docling_ingest.py`를 실행하여:
   - `ECSS-E-ST-50-12C-Rev_1_15May2019_.pdf`를 Docling 표준 파이프라인으로 파싱
   - 조항 텍스트, 계층 구조(parent_clause_id), 페이지 참조를 `clauses` 테이블에 삽입
   - "see §X", "as defined in §Y" 같은 인라인 참조를 파싱하여 `clause_references`에 삽입
   - 이미지/다이어그램은 `generate_picture_images=True`로 추출하여 `clause_images`에 `image_path`만 우선 삽입 (vlm_description은 이 단계에서 NULL로 남김)

2. 적재 후 검증:
   ```
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('spec_harness/spec_harness.db')
   cur = conn.cursor()
   cur.execute('SELECT COUNT(*) FROM clauses')
   print('조항 수:', cur.fetchone()[0])
   cur.execute('SELECT COUNT(*) FROM clause_references')
   print('참조 관계 수:', cur.fetchone()[0])
   cur.execute('SELECT COUNT(*) FROM clause_images')
   print('이미지 수:', cur.fetchone()[0])
   "
   ```

3. 조항 수가 0이거나 비정상적으로 적으면 (예: 목차만 파싱되고 본문이 안 들어간 경우), Docling 파이프라인 옵션을 점검하고 재실행. 자동으로 넘어가지 말 것.

4. 적재 완료 후, 모든 조항에 대해 `verification_status`를 두 Phase 모두 `status='untested'`로 초기화:
   ```sql
   INSERT INTO verification_status (clause_id, phase, status)
   SELECT clause_id, 'A', 'untested' FROM clauses;
   INSERT INTO verification_status (clause_id, phase, status)
   SELECT clause_id, 'B', 'untested' FROM clauses;
   ```

5. 사람에게 적재 결과 요약 보고 (조항 수, 참조 관계 수, 이미지 수, 파싱 실패한 페이지가 있었다면 그 목록).

6. 이어서 `diagram-enricher` 서브에이전트 실행 여부를 사람에게 확인 (이미지가 많으면 VLM 비용이 발생하므로 자동 실행하지 않음).
