#!/bin/bash
# 01:30 점검 — 00:05 자정 수집이 빠졌으면(오늘 날짜로 데이터가 안 바뀌었으면) 한 번 더 돌린다.
# 파이썬이 막혀도 판단할 수 있게 파일 수정일로만 확인한다.
cd "$(dirname "$0")" || exit 1
today=$(date +%Y-%m-%d)
last=$(stat -f %Sm -t %Y-%m-%d data/meokitchen.json 2>/dev/null)
if [ "$last" != "$today" ]; then
  echo "$(date '+%F %T') 자정 수집 누락 (마지막 $last) → 재실행"
  launchctl kickstart gui/$(id -u)/com.openclaw.tracker-engine
else
  echo "$(date '+%F %T') 정상 (오늘 수집됨)"
fi
