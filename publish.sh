#!/bin/bash
# 아카이브를 GitHub Pages로 배포 (변경 있을 때만). 수집·추가·삭제가 겹쳐도 한 번에 하나씩.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")" || exit 1

LOCK=/tmp/meokitchen-archive-publish.lock
got=0
for _ in $(seq 1 90); do
  if mkdir "$LOCK" 2>/dev/null; then got=1; break; fi
  # 10분 넘은 잠금은 비정상 종료로 보고 해제
  age=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || date +%s) ))
  [ "$age" -gt 600 ] && rmdir "$LOCK" 2>/dev/null
  sleep 2
done
[ "$got" = 1 ] || { echo "배포 잠금 대기 초과"; exit 1; }
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

if [ -z "$(git status --porcelain)" ]; then
  echo "변경 없음 — 배포 생략"
  exit 0
fi

git add -A
git commit -q -m "아카이브 갱신 ($(date '+%Y-%m-%d %H:%M'))"
git push -q origin main && echo "배포 완료"
