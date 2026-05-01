#!/bin/bash
# ============================================================
# Hecatech AI Agent System — Auto Import Script
# Chạy script này sau khi n8n đã được cài và đang chạy
# Usage: bash import_all.sh
# ============================================================

export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 20

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================"
echo " Hecatech AI Agent — Import Workflows"
echo "========================================"
echo ""

# Import theo đúng thứ tự: sub-workflows trước, MAIN cuối cùng
WORKFLOWS=(
  "SUB_ceo_briefing.json"
  "SUB_project_warnings.json"
  "SUB_ads_optimizer.json"
  "SUB_review_management.json"
  "SUB_competitive_intel.json"
  "SUB_content_production.json"
  "WEBHOOK_lark_interactive.json"
  "MAIN_orchestrator.json"
)

for wf in "${WORKFLOWS[@]}"; do
  echo "→ Importing: $wf"
  n8n import:workflow --input="$DIR/$wf"
  if [ $? -eq 0 ]; then
    echo "  ✅ Done: $wf"
  else
    echo "  ❌ Failed: $wf"
  fi
  echo ""
done

echo "========================================"
echo "✅ Import hoàn tất!"
echo ""
echo "BƯỚC TIẾP THEO:"
echo "1. Mở http://localhost:5678"
echo "2. Vào Credentials → thêm Google Sheets OAuth2"
echo "3. Vào Settings → Variables → điền đủ các biến"
echo "4. Vào từng SUB workflow → copy Workflow ID → điền vào Variables"
echo "5. Bật Active cho MAIN_orchestrator và WEBHOOK_lark_interactive"
echo "========================================"
