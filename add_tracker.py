#!/usr/bin/env python3
"""
새 트래커 추가 + 즉시 수집 + 배포.
사용:
  python3 add_tracker.py "<label>" "<brand1,brand2>" "<query1,query2>" [id] [emoji]
예:
  python3 add_tracker.py "투어픽" "투어픽,tourpik" "푸꾸옥,나트랑"
  python3 add_tracker.py "메오키친" "메오키친" "푸꾸옥 맛집,나트랑 맛집" meokitchen 🍜
"""
import sys, os, re
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import tracker_store as store
import tracker_engine as engine


def slug(label, existing):
    s = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    if not s:
        s = f"t{len(existing)+1}"
    base = s; i = 2
    while any(t["id"] == s for t in existing):
        s = f"{base}-{i}"; i += 1
    return s


def main():
    if len(sys.argv) < 4:
        print('사용법: add_tracker.py "<label>" "<brand,...>" "<query,...>" [id] [emoji]')
        sys.exit(1)
    label = sys.argv[1].strip()
    brand = [b.strip() for b in sys.argv[2].split(",") if b.strip()]
    queries = [q.strip() for q in sys.argv[3].split(",") if q.strip()]
    emoji = sys.argv[5] if len(sys.argv) > 5 else "📍"
    cfg = store.load_trackers()
    tid = sys.argv[4].strip() if len(sys.argv) > 4 and sys.argv[4].strip() else slug(label, cfg["trackers"])

    if any(t["id"] == tid for t in cfg["trackers"]):
        print(f"이미 존재: {tid}"); sys.exit(2)

    store.add_tracker(tid, label, brand, queries, emoji)
    print(f"✅ 트래커 추가됨: id={tid}, label={label}, brand={brand}, queries={queries}")

    # 즉시 1회 수집 + 배포
    t = store.get_tracker(tid)
    engine.run_tracker(t, notify=False)
    engine.deploy()
    print(f"✅ 첫 수집 + 배포 완료 → https://alohang1985.github.io/meokitchen-archive/")


if __name__ == "__main__":
    main()
