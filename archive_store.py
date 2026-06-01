#!/usr/bin/env python3
"""
메오키친 아카이브 저장 모듈.
검색 스크립트가 찾은 포스팅을 archive.json 에 누적 저장한다 (URL 기준 중복 제외).
기존 텔레그램 전송 로직을 깨지 않도록, 호출부는 항상 try/except 로 감쌀 것.
"""
import json
import os
import re
import sys
import datetime

ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ARCHIVE_FILE = os.path.join(ARCHIVE_DIR, "archive.json")

MEOKITCHEN_PAT = re.compile(r"메오\s*키친|meo\s*kitchen", re.IGNORECASE)

POS_KEYWORDS = ["맛있", "추천", "좋아", "좋았", "좋음", "최고", "필수", "꿀맛", "인생",
                "깔끔", "친절", "훌륭", "만족", "완벽", "강추", "맛집", "재방문", "또 가", "또가"]
NEG_KEYWORDS = ["웨이팅", "대기", "줄서", "줄 서", "별로", "실망", "아쉬운", "아쉬웠", "비싸",
                "오래 기다", "불만", "혼잡", "복잡", "기다려야", "재방문 없", "노쇼", "최악", "불친절"]


def classify_sentiment(text):
    """텍스트에서 긍/부정 키워드를 세어 sentiment 와 매칭 태그를 반환."""
    t = text or ""
    pos = [k for k in POS_KEYWORDS if k in t]
    neg = [k for k in NEG_KEYWORDS if k in t]
    if len(neg) > len(pos):
        sentiment = "neg"
    elif len(pos) > 0:
        sentiment = "pos"
    else:
        sentiment = "neutral"
    return sentiment, pos, neg


def _today():
    return datetime.date.today()


def _parse_post_date(time_text):
    """상대시간 텍스트를 best-effort 로 날짜(YYYY-MM-DD)로 변환."""
    if not time_text:
        return _today().isoformat()
    t = time_text.strip()
    today = _today()
    # "방금 전", "N분 전", "N시간 전" -> 오늘
    if re.search(r"(방금|분\s*전|시간\s*전|초\s*전)", t):
        return today.isoformat()
    if "어제" in t:
        return (today - datetime.timedelta(days=1)).isoformat()
    if re.search(r"(N|\d+)\s*일\s*전", t):
        m = re.search(r"(\d+)\s*일\s*전", t)
        days = int(m.group(1)) if m else 1
        return (today - datetime.timedelta(days=days)).isoformat()
    # "2026.06.01." / "2026-06-01" / "2026.6.1"
    m = re.search(r"(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})", t)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    return today.isoformat()


def _summary(body, max_len=90):
    if not body:
        return ""
    s = re.sub(r"\s+", " ", body).strip()
    return s[:max_len] + ("…" if len(s) > max_len else "")


def _load():
    try:
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("posts"), list):
                return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {"updated_at": None, "posts": []}


def _atomic_write(data):
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    tmp = ARCHIVE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ARCHIVE_FILE)


def save_posts(posts, source, search_kind, region=None):
    """
    posts: [{title, link, time, body}, ...]
    source: 'blog' | 'cafe'
    search_kind: 'meokitchen' | 'matjip'
    region: '푸꾸옥' | '나트랑' | None  (matjip 쿼리에서 전달)
    반환: 새로 추가된 개수
    """
    data = _load()
    by_url = {p["url"]: p for p in data["posts"]}
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    added = 0

    for p in posts or []:
        url = (p.get("link") or "").strip()
        if not url:
            continue
        title = (p.get("title") or "").strip()
        body = p.get("body", "") or ""
        combined = title + " " + body
        mentions_meo = bool(MEOKITCHEN_PAT.search(combined)) or search_kind == "meokitchen"
        sentiment, pos_tags, neg_tags = classify_sentiment(combined)

        if url in by_url:
            # 이미 있으면 마지막 확인 시각만 갱신
            existing = by_url[url]
            existing["last_seen"] = now_iso
            # 이전에 못 잡은 메오키친 언급을 이번에 잡았으면 반영
            existing["mentions_meokitchen"] = existing.get("mentions_meokitchen") or mentions_meo
            continue

        record = {
            "url": url,
            "title": title,
            "source": source,                # blog / cafe
            "search_kind": search_kind,       # meokitchen / matjip
            "region": region or ("메오키친" if search_kind == "meokitchen" else None),
            "time_text": p.get("time", ""),
            "post_date": _parse_post_date(p.get("time", "")),
            "summary": _summary(body),
            "mentions_meokitchen": mentions_meo,
            "sentiment": sentiment,           # pos / neg / neutral
            "pos_tags": pos_tags,
            "neg_tags": neg_tags,
            "first_seen": now_iso,
            "last_seen": now_iso,
        }
        data["posts"].append(record)
        by_url[url] = record
        added += 1

    data["updated_at"] = now_iso
    _atomic_write(data)
    print(f"[archive] {search_kind}/{source}: {added}개 신규 저장 (총 {len(data['posts'])}개)", file=sys.stderr)
    return added


def backfill_sentiment():
    """기존 레코드에 감성/태그가 없으면 title+summary 로 채운다 (1회용)."""
    data = _load()
    n = 0
    for p in data["posts"]:
        if "sentiment" not in p:
            s, pos, neg = classify_sentiment((p.get("title", "") + " " + p.get("summary", "")))
            p["sentiment"] = s
            p["pos_tags"] = pos
            p["neg_tags"] = neg
            n += 1
    if n:
        _atomic_write(data)
    print(f"[archive] 백필 완료: {n}개 레코드에 감성 추가")
    return n


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        backfill_sentiment()
    else:
        n = save_posts(
            [{"title": "푸꾸옥 메오키친 다녀옴", "link": "https://blog.naver.com/test/1", "time": "3시간 전", "body": "정말 맛있었어요"}],
            source="blog", search_kind="matjip", region="푸꾸옥",
        )
        print("added:", n)
