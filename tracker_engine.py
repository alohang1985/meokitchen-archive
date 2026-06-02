#!/usr/bin/env python3
"""
범용 트래커 엔진.
trackers.json 의 모든(또는 지정) 트래커를 돌면서:
 - 각 query를 네이버 블로그/카페에서 검색 (기존 스크래퍼 재사용)
 - 결과를 data/<id>.json 에 누적 저장 (브랜드 언급 여부 판정)
 - 텔레그램으로 요약 발송
 - 마지막에 GitHub Pages 배포
사용: python3 tracker_engine.py [tracker_id]   (id 생략 시 전체)
"""
import sys, os, subprocess, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(BASE)
sys.path.insert(0, WS)      # 네이버 스크래퍼 재사용
sys.path.insert(0, BASE)
import vietnam_matjip_search as nv   # search_naver_blog/cafe, send_telegram
import tracker_store as store


def run_tracker(t, notify=True):
    tid, brand, label = t["id"], t["brand"], t["label"]
    emoji = t.get("emoji", "📍")
    found = 0; mentions = []
    for q in t["queries"]:
        region = q.replace(" 맛집", "").strip()
        try: blog = nv.search_naver_blog(q)
        except Exception as e: blog = []; print(f"[engine] {q} blog 오류: {e}", file=sys.stderr)
        try: cafe = nv.search_naver_cafe(q)
        except Exception as e: cafe = []; print(f"[engine] {q} cafe 오류: {e}", file=sys.stderr)
        store.save_posts(tid, brand, blog, "blog", region=region)
        store.save_posts(tid, brand, cafe, "cafe", region=region)
        found += len(blog) + len(cafe)
        pat = store._brand_re(brand)
        for p in blog + cafe:
            txt = (p.get("title","") + " " + p.get("body","")) if p else ""
            if pat and pat.search(txt):
                mentions.append((p.get("title","(제목없음)"), p.get("link",""), region))

    if notify:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if mentions:
            lines = [f'{emoji} "{label}" 언급 {len(mentions)}건 발견! ({today})',
                     f'(전체 맛집글 {found}개 중)', ""]
            for i,(title,link,region) in enumerate(mentions[:15],1):
                lines.append(f"{i}. [{region}] {title}")
                lines.append(f"   🔗 {link}")
            lines.append("")
            lines.append(f"📊 아카이브: https://alohang1985.github.io/meokitchen-archive/")
            nv.send_telegram("\n".join(lines))
        else:
            nv.send_telegram(f'{emoji} "{label}" — 24시간 내 언급 없음 (전체 맛집글 {found}개 수집) ({today})')
    print(f"[engine] {tid}: 수집 {found}개, 언급 {len(mentions)}건", file=sys.stderr)
    return {"found": found, "mentions": len(mentions)}


def deploy():
    try:
        r = subprocess.run(["bash", os.path.join(BASE, "publish.sh")], timeout=120, capture_output=True, text=True)
        print(f"[engine] 배포: {r.stdout.strip() or r.stderr.strip()}", file=sys.stderr)
    except Exception as e:
        print(f"[engine] 배포 실패(무시): {e}", file=sys.stderr)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = store.load_trackers()
    targets = [t for t in cfg["trackers"] if (only is None or t["id"] == only)]
    if not targets:
        print(f"[engine] 대상 트래커 없음 (only={only})", file=sys.stderr); return
    for t in targets:
        try: run_tracker(t)
        except Exception as e: print(f"[engine] {t['id']} 실패: {e}", file=sys.stderr)
    deploy()


if __name__ == "__main__":
    main()
