#!/usr/bin/env python3
"""
범용 트래커 저장 모듈.
각 트래커별로 data/<tracker_id>.json 에 포스팅을 누적 저장(URL 기준 중복 제외).
trackers.json 에 트래커 목록(설정)을 관리.
"""
import json, os, re, sys, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
TRACKERS_FILE = os.path.join(BASE, "trackers.json")

POS_KEYWORDS = ["맛있","추천","좋아","좋았","좋음","최고","필수","꿀맛","인생","깔끔","친절","훌륭","만족","완벽","강추","맛집","재방문","또 가","또가"]
NEG_KEYWORDS = ["웨이팅","대기","줄서","줄 서","별로","실망","아쉬운","아쉬웠","비싸","오래 기다","불만","혼잡","복잡","기다려야","재방문 없","노쇼","최악","불친절"]


def classify_sentiment(text):
    t = text or ""
    pos = [k for k in POS_KEYWORDS if k in t]
    neg = [k for k in NEG_KEYWORDS if k in t]
    if len(neg) > len(pos): s = "neg"
    elif len(pos) > 0: s = "pos"
    else: s = "neutral"
    return s, pos, neg


def _now(): return datetime.datetime.now().isoformat(timespec="seconds")
def _today(): return datetime.date.today()


def _parse_post_date(time_text):
    if not time_text: return _today().isoformat()
    t = time_text.strip(); today = _today()
    if re.search(r"(방금|분\s*전|시간\s*전|초\s*전)", t): return today.isoformat()
    if "어제" in t: return (today - datetime.timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\s*일\s*전", t)
    if m: return (today - datetime.timedelta(days=int(m.group(1)))).isoformat()
    m = re.search(r"(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})", t)
    if m:
        try: return datetime.date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
        except ValueError: pass
    return today.isoformat()


def _summary(body, n=90):
    if not body: return ""
    s = re.sub(r"\s+"," ",body).strip()
    return s[:n] + ("…" if len(s) > n else "")


def _brand_re(brand_list):
    parts = [re.escape(b).replace(r"\ ", r"\s*") for b in brand_list if b]
    return re.compile("|".join(parts), re.IGNORECASE) if parts else None


# ---------- trackers.json ----------
def load_trackers():
    try:
        with open(TRACKERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"updated_at": None, "trackers": []}


def save_trackers(cfg):
    cfg["updated_at"] = _now()
    tmp = TRACKERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TRACKERS_FILE)


def get_tracker(tid):
    return next((t for t in load_trackers()["trackers"] if t["id"] == tid), None)


def add_tracker(tid, label, brand_list, queries, emoji="📍"):
    cfg = load_trackers()
    if any(t["id"] == tid for t in cfg["trackers"]):
        raise ValueError(f"이미 존재하는 트래커: {tid}")
    cfg["trackers"].append({"id": tid, "label": label, "emoji": emoji,
                            "brand": brand_list, "queries": queries})
    save_trackers(cfg)
    return cfg


# ---------- per-tracker data ----------
def _data_file(tid): return os.path.join(DATA_DIR, f"{tid}.json")


def _load_data(tid):
    try:
        with open(_data_file(tid), "r", encoding="utf-8") as f:
            d = json.load(f)
            if isinstance(d, dict) and isinstance(d.get("posts"), list): return d
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {"tracker": tid, "updated_at": None, "posts": []}


def _write_data(tid, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _data_file(tid) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _data_file(tid))


def save_posts(tracker_id, brand_list, posts, source, region=None):
    """posts: [{title,link,time,body}]. 반환: 신규 추가 개수."""
    data = _load_data(tracker_id)
    by_url = {p["url"]: p for p in data["posts"]}
    pat = _brand_re(brand_list)
    now = _now(); added = 0
    for p in posts or []:
        url = (p.get("link") or "").strip()
        if not url: continue
        title = (p.get("title") or "").strip(); body = p.get("body","") or ""
        combined = title + " " + body
        mentions = bool(pat.search(combined)) if pat else False
        if url in by_url:
            ex = by_url[url]; ex["last_seen"] = now
            ex["mentions_brand"] = ex.get("mentions_brand") or mentions
            continue
        s, pos, neg = classify_sentiment(combined)
        rec = {"url": url, "title": title, "source": source, "region": region,
               "time_text": p.get("time",""), "post_date": _parse_post_date(p.get("time","")),
               "crawl_date": _today().isoformat(),   # 이 글을 처음 수집한 날 (불변) — 일별 집계 기준
               "summary": _summary(body), "mentions_brand": mentions,
               "sentiment": s, "pos_tags": pos, "neg_tags": neg,
               "first_seen": now, "last_seen": now}
        data["posts"].append(rec); by_url[url] = rec; added += 1
    data["updated_at"] = now
    _write_data(tracker_id, data)
    print(f"[store] {tracker_id}/{source}/{region}: +{added} (총 {len(data['posts'])})", file=sys.stderr)
    return added
