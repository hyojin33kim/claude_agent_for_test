#!/usr/bin/env python3
"""
spec_harness/ingest/docling_ingest.py

ECSS 스펙 PDF를 Docling 표준 파이프라인으로 파싱하여 spec_harness.db에 적재한다.
이미지 추출까지만 이 스크립트가 담당하고, VLM을 통한 이미지 "해석"은
별도 스크립트인 vlm_enrich.py에서 수행한다.
(Docling 문서 확인 사항: VLM 파이프라인은 명시적 이미지 참조가 없으면 이미지를
 추출하지 못하므로, 레이아웃 감지/이미지 추출은 표준 파이프라인으로 먼저 하고
 VLM은 보강 단계로 분리하는 것이 권장 흐름)

실행 전 설치 필요:
    pip install docling --break-system-packages
"""

import sqlite3
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "spec_harness.db"
PDF_PATH = Path(__file__).parent.parent.parent / ".docs" / "ECSS-E-ST-50-12C-Rev.1(15May2019).pdf"
IMAGE_OUT_DIR = Path(__file__).parent / "extracted_images"

# 조항 번호 패턴 (예: "1 Scope", "3.2.1 allocated output port", "6.5.2.2.4 Effect On Receipt")
# Docling 마크다운 export는 조항 헤더를 ATX 헤더(`## <번호> <제목>`)로 내보내므로
# 반드시 선행 '#+ ' 를 매칭해야 함 (실 PDF로 검증: 이 접두사 없이는 0건 매칭됨).
# 최상위 챕터(예: "1 Scope")는 점(.) 없이 숫자 하나뿐이므로 {0,5}로 허용.
CLAUSE_ID_PATTERN = re.compile(r"^#+\s+(\d+(?:\.\d+){0,5})\s+(.+)$")
# 인라인 참조 패턴 (예: "see 8.5.2.3", "as defined in clause 6.1")
REFERENCE_PATTERN = re.compile(
    r"(?:see|as defined in|per|refer to)\s+(?:clause\s+)?(\d+(?:\.\d+){1,5})",
    re.IGNORECASE,
)


def get_parent_clause_id(clause_id: str) -> str | None:
    parts = clause_id.split(".")
    if len(parts) <= 1:
        return None
    return ".".join(parts[:-1])


def ingest():
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat

    IMAGE_OUT_DIR.mkdir(parents=True, exist_ok=True)

    pipeline_options = PdfPipelineOptions()
    pipeline_options.generate_picture_images = True  # 이미지 원본 추출 (VLM 해석은 별도)
    pipeline_options.images_scale = 2.0

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )

    print(f"[ingest] Docling 변환 시작: {PDF_PATH}")
    result = converter.convert(str(PDF_PATH))
    doc = result.document

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    # clauses는 INSERT OR REPLACE로 자체 dedup되지만, clause_references/clause_images는
    # 그렇지 않으므로 재적재 전 전체 삭제 후 다시 채운다 (재실행 시 중복 방지).
    cur.execute("DELETE FROM clause_references")
    cur.execute("DELETE FROM clause_images")

    clause_count = 0
    reference_count = 0
    image_count = 0

    # --- 텍스트/조항 파싱 ---
    # 실제 구조는 Docling 버전에 따라 doc.texts / doc.body 순회 방식이 다를 수 있어
    # 여기서는 마크다운 export 후 라인 단위로 조항 헤더를 탐지하는 단순한 방식으로 시작.
    # 정교화는 실제 PDF로 1차 테스트 후 조정 필요.
    markdown = doc.export_to_markdown()
    current_clause = None
    buffer = []

    def flush():
        nonlocal clause_count
        if current_clause is None:
            return
        clause_id, title = current_clause
        text_full = "\n".join(buffer).strip()
        cur.execute(
            """INSERT OR REPLACE INTO clauses
               (clause_id, title, text_full, page_ref, parent_clause_id, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (clause_id, title, text_full, None, get_parent_clause_id(clause_id), now),
        )
        clause_count += 1

        # 인라인 참조 추출
        nonlocal reference_count
        for match in REFERENCE_PATTERN.finditer(text_full):
            to_clause = match.group(1)
            if to_clause != clause_id:
                cur.execute(
                    """INSERT INTO clause_references (from_clause, to_clause, relation_type)
                       VALUES (?, ?, ?)""",
                    (clause_id, to_clause, "see_also"),
                )
                reference_count += 1

    for line in markdown.splitlines():
        m = CLAUSE_ID_PATTERN.match(line)
        if m:
            flush()
            current_clause = (m.group(1), m.group(2).strip())
            buffer = []
        else:
            buffer.append(line)
    flush()

    # --- 이미지 추출 ---
    for idx, picture in enumerate(getattr(doc, "pictures", [])):
        image_path = IMAGE_OUT_DIR / f"image_{idx:04d}.png"
        try:
            pil_img = picture.get_image(doc)
            if pil_img is not None:
                pil_img.save(image_path)
                # 이미지가 속한 조항을 정확히 매핑하는 로직은 Docling의 provenance 정보
                # (picture.prov) 활용해 보정 필요 — 여기서는 최소 골격만 작성
                cur.execute(
                    """INSERT INTO clause_images (clause_id, image_path, image_type, vlm_description)
                       VALUES (?, ?, ?, NULL)""",
                    (None, str(image_path), "unknown"),
                )
                image_count += 1
        except Exception as e:
            print(f"[ingest][warn] 이미지 {idx} 추출 실패: {e}", file=sys.stderr)

    conn.commit()
    conn.close()

    print(f"[ingest] 완료 — 조항 {clause_count}개, 참조관계 {reference_count}개, 이미지 {image_count}개")


if __name__ == "__main__":
    ingest()
