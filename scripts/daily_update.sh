#!/bin/bash
# 每日定時自動更新抽獎資料庫腳本 (macOS / Linux)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] 開始執行每日抽獎活動自動更新 ===" >> "$PROJECT_DIR/crawler.log"

# 切換到專案目錄並執行爬蟲
cd "$PROJECT_DIR" || exit 1
/usr/bin/python3 "$PROJECT_DIR/scripts/crawler.py" >> "$PROJECT_DIR/crawler.log" 2>&1

echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] 更新完成！ ===" >> "$PROJECT_DIR/crawler.log"
