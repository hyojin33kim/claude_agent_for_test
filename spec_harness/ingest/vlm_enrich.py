#!/usr/bin/env python3
"""
spec_harness/ingest/vlm_enrich.py

docling_ingest.py가 추출해둔 이미지 중 vlm_description이 아직 NULL인 것들에 대해
VLM으로 "이 다이어그램이 무엇을 설명하는지"를 텍스트로 생성하여 DB에 채운다.

이미지 추출(Docling)과 이미지 해석(VLM)을 별도 단계로 분리한 이유:
원격 VLM API는 임베딩된 이미지/base64 데이터를 직접 반환하지 못하므로
이미지 자체는 로컬에서 먼저 뽑아두고, 해석만 VLM에 맡기는 것이 안전하다.

실행 전 환경변수 필요: ANTHROPIC_API_KEY (또는 사용 중인 VLM 제공자 키)
"""

import sqlite3
import base64
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "spec_harness.db"

PROMPT_TEMPLATE = """당신은 SpaceWire(ECSS-E-ST-50-12C) 프로토콜 스펙의 다이어그램을 해석하는 전문가입니다.
아래 이미지는 스펙 문서에서 추출한 다이어그램입니다.

다음을 정확히 서술하세요:
1. 이 다이어그램의 종류 (상태 전이도 / 타이밍 다이어그램 / 블록도 / 표 / 기타)
2. 상태 전이도라면: 모든 상태와 전이 조건을 빠짐없이 나열
3. 타이밍 다이어그램이라면: 신호명과 각 신호의 정확한 레벨/펄스 특성 (특히 "레벨 유지 신호"와 "1클럭 펄스 신호"를 명확히 구분할 것 — 이 구분 오류가 과거 반복적으로 발생한 실수 패턴임)
4. 불확실한 부분이 있으면 추측하지 말고 "불확실: ..." 이라고 명시

텍스트로만 답하세요.
"""


def classify_image_type(description: str) -> str:
    desc_lower = description.lower()
    if "상태 전이" in description or "state" in desc_lower:
        return "state_diagram"
    if "타이밍" in description or "timing" in desc_lower:
        return "timing_diagram"
    if "표" in description[:50] or "table" in desc_lower[:50]:
        return "table"
    return "other"


def enrich():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT image_id, image_path FROM clause_images WHERE vlm_description IS NULL"
    )
    rows = cur.fetchall()
    print(f"[vlm_enrich] 보강 대상 이미지 {len(rows)}개")

    # 실제 API 호출부는 사용 중인 SDK로 교체 (예: anthropic python SDK)
    # 아래는 골격만 — 실제 실행 전 client 초기화 코드 채워넣을 것
    #
    # from anthropic import Anthropic
    # client = Anthropic()

    for image_id, image_path in rows:
        if not Path(image_path).exists():
            print(f"[vlm_enrich][warn] 이미지 파일 없음: {image_path}")
            continue

        with open(image_path, "rb") as f:
            image_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

        # response = client.messages.create(
        #     model="claude-sonnet-4-6",
        #     max_tokens=1000,
        #     messages=[{
        #         "role": "user",
        #         "content": [
        #             {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
        #             {"type": "text", "text": PROMPT_TEMPLATE},
        #         ],
        #     }],
        # )
        # description = response.content[0].text
        description = "[TODO: 실제 VLM 호출 결과로 교체]"

        image_type = classify_image_type(description)

        cur.execute(
            """UPDATE clause_images
               SET vlm_description = ?, vlm_model_used = ?, image_type = ?
               WHERE image_id = ?""",
            (description, "claude-sonnet-4-6", image_type, image_id),
        )
        print(f"[vlm_enrich] image_id={image_id} 보강 완료 (type={image_type})")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    enrich()
