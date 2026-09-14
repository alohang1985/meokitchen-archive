#!/usr/bin/env python3
"""
트래커 저장 모듈 (v2)

DB   : data/<tracker_id>.json — 수집한 글을 URL 기준으로 누적 (영구 보존, GitHub에도 함께 백업)
설정 : trackers.json

집계 기준
- 검색어 풀 : keywords(예: 푸꾸옥·나트랑) 검색에서 걸린 글. 글마다 hits=[걸린 검색어들]
- 언급      : 풀 안에서 brand 표기가 제목·본문에 들어간 글 (mentions_brand)
- 단독 검색 : brand 이름만으로 검색해 걸린 글 (direct=True). 풀 통계와 섞지 않고 따로 집계
"""
import json, os, re, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
TRACKERS_FILE = os.path.join(BASE, "trackers.json")
DELETED_DIR = os.path.join(os.path.dirname(BASE), "meokitchen-archive-deleted")
SCHEMA = 2

POS_KEYWORDS = ["맛있","추천","좋아","좋았","좋음","최고","필수","꿀맛","인생","깔끔","친절","훌륭","만족","완벽","강추","맛집","재방문","또 가","또가"]
NEG_KEYWORDS = ["웨이팅","대기","줄서","줄 서","별로","실망","아쉬운","아쉬웠","비싸","오래 기다","불만","혼잡","복잡","기다려야","재방문 없","노쇼","최악","불친절"]


def classify_sentiment(text):
    t = text or ""
    pos = [k for k in POS_KEYWORDS if k in t]
    neg = [k for k in NEG_KEYWORDS if k in t]
    if len(neg) > len(pos): s = "neg"
    elif pos: s = "pos"
    else: s = "neutral"
    return s, pos, neg


def _now(): return datetime.datetime.now().isoformat(timespec="seconds")
def _today(): return datetime.date.today()


def crawl_date():
    """일별 집계 기준일. 자정~6시 실행은 방금 끝난 '어제 하루' 수집으로 본다."""
    now = datetime.datetime.now()
    if now.hour < 6:
        return (now.date() - datetime.timedelta(days=1)).isoformat()
    return now.date().isoformat()


def _parse_post_date(time_text):
    if not time_text: return _today().isoformat()
    t = time_text.strip(); today = _today()
    if re.search(r"(방금|분\s*전|시간\s*전|초\s*전)", t): return today.isoformat()
    if "어제" in t: return (today - datetime.timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\s*일\s*전", t)
    if m: return (today - datetime.timedelta(days=int(m.group(1)))).isoformat()
    m = re.search(r"(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})", t)
    if m:
        try: return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError: pass
    return today.isoformat()


def _summary(body, n=90):
    if not body: return ""
    s = re.sub(r"\s+", " ", body).strip()
    return s[:n] + ("…" if len(s) > n else "")


def brand_re(brand_list):
    """한글 브랜드는 글자 사이 띄어쓰기를 허용 (메오키친 = 메오 키친)."""
    parts = []
    for b in brand_list or []:
        b = (b or "").strip()
        if not b: continue
        if re.search(r"[가-힣]", b):
            parts.append(r"\s*".join(re.escape(c) for c in b if not c.isspace()))
        else:
            parts.append(r"\s*".join(re.escape(w) for w in b.split()))
    return re.compile("|".join(parts), re.IGNORECASE) if parts else None


def split_list(s):
    return [x.strip() for x in re.split(r"[,，、;]", s or "") if x.strip()]


def parse_spec(spec):
    """'푸꾸옥, 나트랑 - 메오키친' → (['푸꾸옥','나트랑'], ['메오키친'])"""
    s = (spec or "").strip()
    m = re.match(r"^(.*?)\s+[-–—|/]\s+(.*)$", s) or re.match(r"^(.*?)[-–—|/](.*)$", s)
    if not m:
        raise ValueError("‘검색어 - 브랜드’ 형식으로 입력해주세요 (예: 마우스 - 로지텍)")
    kws, brands = split_list(m.group(1)), split_list(m.group(2))
    if not kws: raise ValueError("하이픈 앞에 검색어를 입력해주세요")
    if not brands: raise ValueError("하이픈 뒤에 브랜드를 입력해주세요")
    return kws, brands


def keywords_of(t):
    raw = t.get("keywords") or [q.replace(" 맛집", "") for q in t.get("queries", [])]
    out = []
    for k in raw:
        k = (k or "").strip()
        if k and k not in out: out.append(k)
    return out


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


def _new_id(label, taken):
    s = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")
    if not s:
        s = "t" + datetime.datetime.now().strftime("%y%m%d%H%M%S")
    base, i = s, 2
    while s in taken:
        s = f"{base}-{i}"; i += 1
    return s


def add_tracker(keywords, brands, label=None, emoji="📍", direct=True):
    keywords = [k.strip() for k in (keywords or []) if k and k.strip()]
    brands = [b.strip() for b in (brands or []) if b and b.strip()]
    if not keywords: raise ValueError("검색어가 없습니다")
    if not brands: raise ValueError("브랜드가 없습니다")
    cfg = load_trackers()
    label = (label or brands[0]).strip()
    for t in cfg["trackers"]:
        if t["label"] == label and keywords_of(t) == keywords:
            raise ValueError(f"이미 있는 트래커입니다: {label}")
    t = {"id": _new_id(label, {x["id"] for x in cfg["trackers"]}), "label": label,
         "emoji": emoji or "📍", "brand": brands, "keywords": keywords,
         "direct": bool(direct), "created_at": _now()}
    cfg["trackers"].append(t)
    save_trackers(cfg)
    return t


def delete_tracker(tid):
    cfg = load_trackers()
    t = next((x for x in cfg["trackers"] if x["id"] == tid), None)
    if not t: raise KeyError(f"없는 트래커: {tid}")
    cfg["trackers"] = [x for x in cfg["trackers"] if x["id"] != tid]
    save_trackers(cfg)
    src = _data_file(tid)
    if os.path.exists(src):   # 기록은 지우지 않고 저장소 밖에 보관 (복구 가능)
        os.makedirs(DELETED_DIR, exist_ok=True)
        os.replace(src, os.path.join(DELETED_DIR, f"{tid}-{datetime.datetime.now():%Y%m%d%H%M%S}.json"))
    return t


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
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, _data_file(tid))


class Store:
    """한 번 불러와서 여러 검색 결과를 모은 뒤 commit()에서 한 번만 저장한다."""

    def __init__(self, tid, brand_list):
        self.tid = tid
        self.pat = brand_re(brand_list)
        self.data = _load_data(tid)
        self.by_url = {p["url"]: p for p in self.data["posts"]}
        self.now, self.day = _now(), crawl_date()

    def add(self, posts, source, hit=None, direct=False):
        added = 0
        for p in posts or []:
            url = (p.get("link") or "").strip()
            if not url: continue
            title = (p.get("title") or "").strip()
            body = p.get("body", "") or ""
            text = title + " " + body
            found = bool(self.pat and self.pat.search(text))
            rec = self.by_url.get(url)
            if rec is None:
                s, pos, neg = classify_sentiment(text)
                rec = {"url": url, "title": title, "source": source, "hits": [], "direct": False,
                       "time_text": p.get("time", ""), "post_date": _parse_post_date(p.get("time", "")),
                       "crawl_date": self.day, "summary": _summary(body), "mentions_brand": found,
                       "sentiment": s, "pos_tags": pos, "neg_tags": neg,
                       "first_seen": self.now, "last_seen": self.now}
                self.data["posts"].append(rec); self.by_url[url] = rec; added += 1
            else:
                rec["last_seen"] = self.now
                rec.setdefault("hits", [])
                if found: rec["mentions_brand"] = True
            if hit and hit not in rec["hits"]: rec["hits"].append(hit)
            if direct: rec["direct"] = True
        return added

    def commit(self):
        self.data["updated_at"] = self.now
        self.data["schema"] = SCHEMA
        _write_data(self.tid, self.data)
        return len(self.data["posts"])


def migrate(t):
    """v1 → v2: region 을 hits/direct 로 변환. 브랜드명이 region 인 글 = 예전 단독 검색 결과."""
    data = _load_data(t["id"])
    names = {n.strip().lower() for n in (t.get("brand") or []) + [t.get("label", "")] if n}
    changed = 0
    for p in data["posts"]:
        if "hits" in p: continue
        r = (p.get("region") or "").strip()
        if r.lower() in names:
            p["hits"], p["direct"] = [], True
        else:
            p["hits"], p["direct"] = ([r] if r else []), False
        p.pop("region", None)
        changed += 1
    if changed or data.get("schema") != SCHEMA:
        data["schema"] = SCHEMA
        _write_data(t["id"], data)
    return changed, len(data["posts"])
