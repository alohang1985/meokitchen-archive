#!/usr/bin/env python3
"""
트래커 엔진 (v2)
trackers.json 의 트래커마다:
 1) 검색어(keywords)별 네이버 블로그·카페 24시간 글 수집 → 검색어별 전체 / 브랜드 언급 집계
 2) direct=true 면 브랜드명 단독 검색도 따로 수집·집계 (검색어 풀과 섞지 않음)
 3) data/<id>.json 누적 저장 → 텔레그램 요약 → GitHub Pages 배포
사용: python3 tracker_engine.py [tracker_id] [--no-notify] [--no-deploy]
"""
import sys, os, time, subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))   # 네이버 스크래퍼 재사용
sys.path.insert(0, BASE)
import vietnam_matjip_search as nv
import tracker_store as store

SITE = "https://alohang1985.github.io/meokitchen-archive/"


def log(*a): print("[engine]", *a, file=sys.stderr, flush=True)


class Lock:
    """같은 트래커를 동시에 수집하면 기록이 덮어써지므로 잠근다."""
    def __init__(self, name, wait=900):
        self.path, self.wait = f"/tmp/tracker-{name}.lock", wait

    def __enter__(self):
        t0 = time.time()
        while True:
            try:
                os.mkdir(self.path); return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > 1800:
                        os.rmdir(self.path); continue
                except OSError:
                    continue
                if time.time() - t0 > self.wait:
                    raise TimeoutError(f"다른 수집이 진행 중: {self.path}")
                time.sleep(3)

    def __exit__(self, *a):
        try: os.rmdir(self.path)
        except OSError: pass


def search(q):
    out = {}
    for src, fn in (("blog", nv.search_naver_blog), ("cafe", nv.search_naver_cafe)):
        try: out[src] = fn(q) or []
        except Exception as e:
            out[src] = []; log(f"{q} {src} 오류: {e}")
    return out


def _url(p): return (p.get("link") or "").strip()


def run_tracker(t, notify=True):
    with Lock(t["id"]):
        return _run(t, notify)


def _run(t, notify):
    tid, label = t["id"], t["label"]
    brand = t.get("brand") or [label]
    pat = store.brand_re(brand)
    st = store.Store(tid, brand)

    per_kw, pool, mentions = {}, set(), {}
    for kw in store.keywords_of(t):
        res = search(kw)
        for src, posts in res.items():
            st.add(posts, src, hit=kw)
        posts = [p for ps in res.values() for p in ps if _url(p)]
        urls = {_url(p) for p in posts}
        found = {_url(p): p for p in posts
                 if pat and pat.search((p.get("title") or "") + " " + (p.get("body") or ""))}
        per_kw[kw] = {"total": len(urls), "mention": len(found)}
        pool |= urls
        for u, p in found.items():
            mentions.setdefault(u, (kw, p.get("title") or "(제목 없음)"))

    direct = None
    if t.get("direct"):
        res = search(brand[0])
        for src, posts in res.items():
            st.add(posts, src, direct=True)
        direct = {}
        for p in (p for ps in res.values() for p in ps):
            if _url(p): direct.setdefault(_url(p), p.get("title") or "(제목 없음)")

    saved = st.commit()
    r = {"id": tid, "pool": len(pool), "mentions": len(mentions), "per_kw": per_kw,
         "direct": None if direct is None else len(direct), "saved": saved}
    log(f"{tid}: 검색 {r['pool']}건 · 언급 {r['mentions']}건 · 단독 {r['direct']} · 누적 {saved}")
    if notify:
        try: nv.send_telegram(message(t, r, mentions, direct, st.day))
        except Exception as e: log("텔레그램 실패:", e)
    return r


def message(t, r, mentions, direct, day):
    label, emoji = t["label"], t.get("emoji", "📍")
    kws = " · ".join(f"{k} {v['total']}" for k, v in r["per_kw"].items())
    lines = [f"{emoji} {label} · {day[5:].replace('-', '/')}",
             f"검색 [{kws}] 중 언급 {r['mentions']}건"]
    if r["direct"] is not None:
        lines.append(f"'{(t.get('brand') or [label])[0]}' 단독 검색 {r['direct']}건")
    if mentions:
        lines += ["", "언급 글"]
        for i, (u, (kw, title)) in enumerate(list(mentions.items())[:10], 1):
            lines += [f"{i}. [{kw}] {title}", f"   {u}"]
    if direct:
        lines += ["", "단독 검색 글"]
        for i, (u, title) in enumerate(list(direct.items())[:5], 1):
            lines += [f"{i}. {title}", f"   {u}"]
    lines += ["", f"📊 {SITE}"]
    msg = "\n".join(lines)
    return msg if len(msg) < 3900 else msg[:3880] + "\n…"


def deploy():
    try:
        r = subprocess.run(["bash", os.path.join(BASE, "publish.sh")], timeout=300, capture_output=True, text=True)
        log("배포:", (r.stdout.strip() or r.stderr.strip())[-300:])
    except Exception as e:
        log("배포 실패(무시):", e)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = args[0] if args else None
    targets = [t for t in store.load_trackers()["trackers"] if only is None or t["id"] == only]
    if not targets:
        log(f"대상 트래커 없음 (only={only})"); return 1
    for t in targets:
        try: run_tracker(t, notify="--no-notify" not in sys.argv)
        except Exception as e: log(f"{t['id']} 실패: {e}")
    if "--no-deploy" not in sys.argv:
        deploy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
