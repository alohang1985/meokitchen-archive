#!/usr/bin/env python3
"""터미널용 트래커 추가 + 첫 수집 + 배포.
사용: python3 add_tracker.py "마우스 - 로지텍" [--no-direct]
     python3 add_tracker.py "푸꾸옥, 나트랑 - 메오키친, meo kitchen"
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tracker_store as store
import tracker_engine as engine


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__); return 1
    kws, brands = store.parse_spec(args[0])
    t = store.add_tracker(kws, brands, direct="--no-direct" not in sys.argv)
    print(f"✅ 추가: {t['label']} (id={t['id']}) · 검색어 {kws} · 브랜드 {brands}")
    engine.run_tracker(t, notify=False)
    engine.deploy()
    print("✅ 첫 수집 + 배포 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
