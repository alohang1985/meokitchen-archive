#!/usr/bin/env python3
"""관리 명령 (admin-server.js 가 호출). 결과는 JSON 한 줄로 출력한다.
  add --spec "푸꾸옥, 나트랑 - 메오키친" [--direct 1] [--emoji 🍜]
  delete <id>
  list
  migrate
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tracker_store as store


def out(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False))
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--spec", required=True)
    a.add_argument("--direct", default="1")
    a.add_argument("--emoji", default="📍")
    sub.add_parser("delete").add_argument("id")
    sub.add_parser("list")
    sub.add_parser("migrate")
    ns = ap.parse_args()
    try:
        if ns.cmd == "add":
            kws, brands = store.parse_spec(ns.spec)
            t = store.add_tracker(kws, brands, emoji=ns.emoji,
                                  direct=ns.direct.lower() not in ("0", "false", "no", ""))
            out({"ok": True, "tracker": t})
        if ns.cmd == "delete":
            out({"ok": True, "tracker": store.delete_tracker(ns.id)})
        if ns.cmd == "list":
            out({"ok": True, "trackers": store.load_trackers()["trackers"]})
        if ns.cmd == "migrate":
            res = []
            for t in store.load_trackers()["trackers"]:
                changed, total = store.migrate(t)
                res.append({"id": t["id"], "migrated": changed, "total": total})
            out({"ok": True, "result": res})
    except (ValueError, KeyError) as e:
        out({"ok": False, "error": str(e).strip("'\"")}, 2)


if __name__ == "__main__":
    main()
