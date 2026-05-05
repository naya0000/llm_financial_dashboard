#!/bin/bash
#
# 個人理財助理 — Uninstaller
#
# Usage: ./uninstall.sh [--remove-reports] [--keep-permissions]
#

set -e

SKILLS_DIR="$HOME/.claude/skills"
CONFIG_FILE="$HOME/.claude/stock-analysis.conf"
SETTINGS_FILE="$HOME/.claude/settings.json"
REMOVE_REPORTS=false
KEEP_PERMISSIONS=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --remove-reports)
      REMOVE_REPORTS=true
      shift
      ;;
    --keep-permissions)
      KEEP_PERMISSIONS=true
      shift
      ;;
    --help|-h)
      echo "Usage: ./uninstall.sh [--remove-reports] [--keep-permissions]"
      echo ""
      echo "Options:"
      echo "  --remove-reports    Also delete ~/stock-reports/"
      echo "  --keep-permissions  Don't remove plugin permissions from settings.json"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

SKILLS=(
  "stock-orchestrator"
  "stock-data-fetcher"
  "stock-data-validator"
  "stock-financial-analyst"
  "stock-technical-analyst"
  "stock-quant-analyst"
  "stock-industry-macro"
  "stock-news-sentiment"
  "stock-institutional-flow"
  "stock-integrator"
  "stock-dashboard"
  "shared"
)

echo ""
echo "🗑  Uninstalling 個人理財助理..."
echo ""

# Remove skill directories
for skill in "${SKILLS[@]}"; do
  if [ -d "$SKILLS_DIR/$skill" ]; then
    rm -rf "$SKILLS_DIR/$skill"
    echo "   ✓ Removed $skill"
  fi
done

# Remove config
if [ -f "$CONFIG_FILE" ]; then
  rm "$CONFIG_FILE"
  echo "   ✓ Removed config file"
fi

# Remove plugin permissions from settings.json
if [ "$KEEP_PERMISSIONS" = false ] && [ -f "$SETTINGS_FILE" ]; then
  echo ""
  echo "🔐 Removing plugin permissions from settings.json..."
  python3 << 'PYEOF'
import json, os

settings_file = os.path.expanduser("~/.claude/settings.json")
MARKER = "# __stock-analysis-plugin__"

try:
    with open(settings_file, "r", encoding="utf-8") as f:
        settings = json.load(f)
except (json.JSONDecodeError, IOError, FileNotFoundError):
    print("   ⏭  No settings.json found, nothing to clean")
    exit(0)

perms = settings.get("permissions", {})
allow_list = perms.get("allow", [])
additional_dirs = perms.get("additionalDirectories", [])

# Count before
before = len(allow_list)

# Remove tagged permissions
allow_list = [p for p in allow_list if not p.endswith(MARKER)]

# Remove output directory
output_dir = os.path.expanduser("~/stock-reports")
additional_dirs = [d for d in additional_dirs if d != output_dir]

removed = before - len(allow_list)

perms["allow"] = allow_list
perms["additionalDirectories"] = additional_dirs
settings["permissions"] = perms

with open(settings_file, "w", encoding="utf-8") as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"   ✓ Removed {removed} plugin permissions")
PYEOF
else
  if [ "$KEEP_PERMISSIONS" = true ]; then
    echo ""
    echo "   ⏭  Permissions kept in settings.json (--keep-permissions)"
  fi
fi

# Optionally remove reports
if [ "$REMOVE_REPORTS" = true ]; then
  OUTPUT_DIR="$HOME/stock-reports"
  if [ -d "$OUTPUT_DIR" ]; then
    rm -rf "$OUTPUT_DIR"
    echo "   ✓ Removed reports at $OUTPUT_DIR"
  fi
else
  echo ""
  echo "   ℹ  Reports in ~/stock-reports/ were kept."
  echo "      Use --remove-reports to delete them too."
fi

echo ""
echo "  ✅ Uninstall complete."
echo ""
