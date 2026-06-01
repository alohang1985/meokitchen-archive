#!/bin/bash
# 메오키친 아카이브를 GitHub Pages로 배포 (변경 있을 때만 커밋/푸시)
set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")"

if [ -z "$(git status --porcelain data/archive.json)" ]; then
  echo "변경 없음 — 배포 생략"
  exit 0
fi

COUNT=$(python3 -c "import json;print(len(json.load(open('data/archive.json'))['posts']))" 2>/dev/null || echo "?")
git add -A
git commit -q -m "데이터 갱신: 총 ${COUNT}개 포스팅 ($(date +%Y-%m-%d))"
git push -q origin main
echo "배포 완료 — 총 ${COUNT}개 포스팅"
