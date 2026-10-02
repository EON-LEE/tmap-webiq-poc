"""Add bounded exact excerpts and evidence limitations to fetched originals."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ANCHORS = {
    "W1-airport": "9,000",
    "W2-official-parking": "금,토,일요일",
    "W3-grandpark": "반려동물",
    "W4-namsan": "승용차",
    "W5-official-fare": "어른 : 13,000",
    "P1-webiq_optimized-1": "지하 2층",
    "P1-webiq_base-4": "주차",
    "P2-webiq_base-1": "All seats are available",
    "P3-webiq_base-0": "최대 2시간",
    "P3-webiq_optimized-0": "최대 2시간",
    "P3-buffet-operator": "고양시",
    "P3-popolo-operator": "2026.9.1",
    "P4-bing-0": "토요일",
    "P5-bing-0": "월~목",
    "F1-naver": "2026.09.07",
    "F2-nasdaq": '09/04/2026',
    "F3-yahoo": '"close":',
    "F4-http": "매매기준율표",
    "F4-webiq_base-2": "미국 달러는 서울 15:30",
    "F5-tsla": "09/04/2026",
    "N1-bing-0": "여의동로",
    "N2-bing-0": "32%",
    "N3-seoul": "2026 서울무형문화축제",
    "N4-webiq_base-0": "전체 충전요금이 최대 32%",
    "N5-webiq_base-2": "9월 24~27일",
    "B1-botanic": "평시(3~10월)",
    "B2-notice": "할인차량",
    "B2-webiq_base-2": "시행 예정일",
    "B2-old": "5,000",
    "B3-museum": "승용차(15인승 이하)",
    "B4-official-parking": "서울랜드 동문 주차장",
    "B4-webiq_base-0": "별도로 운영되는",
    "B4-grandpark-current": "일반차\n",
    "B5-official-reservation": "사전 예약한 차량",
}
for path in OUT.glob("*.json"):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "fetched_at" not in data:
        continue
    if "bing.net/th?" in data.get("url", ""):
        data.pop("text", None)
        data.pop("links", None)
        data["media_not_used_for_review"] = True
        data["retained_as_metadata_only"] = True
    excerpts = []
    if data.get("title"):
        excerpts.append(f"{data['title']} — {data.get('author')} ({data.get('lengthSeconds')} seconds)")
        if data.get("shortDescription"):
            excerpts.append(data["shortDescription"][:280])
    anchor = ANCHORS.get(path.stem)
    text = data.get("text", "")
    if anchor and anchor in text:
        index = text.index(anchor)
        excerpts.append(text[max(0, index-55):index+len(anchor)+230])
    data["short_review_excerpts"] = excerpts
    data["validity_note"] = (
        "Original retrieved at fetched_at. Excerpts support only identified claims, not every statement on the page. "
        "Historical/implementation/currentness limitations and source conflicts are recorded per question in accuracy_review.json. "
        "HTTP 200 is not itself factual verification. Video metadata is not playback or chapter verification."
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
