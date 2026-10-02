#!/usr/bin/env bash
# ===========================================================================
# SmartSpace AI — Repository Cleanup Script
# Removes cache directories, OS metadata, and stale build/model artifacts.
#
# Usage:
#   chmod +x scripts/cleanup.sh
#   ./scripts/cleanup.sh              # dry-run (list only)
#   ./scripts/cleanup.sh --execute    # actually delete
# ===========================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=true

if [[ "${1:-}" == "--execute" ]]; then
  DRY_RUN=false
  echo "🔥  EXECUTING cleanup (files will be permanently deleted)"
else
  echo "🔍  DRY RUN — showing what would be deleted (pass --execute to delete)"
fi

echo ""
echo "Project root: $PROJECT_ROOT"
echo "─────────────────────────────────────────────────────"

# ---------------------------------------------------------------------------
# 1. Python caches
# ---------------------------------------------------------------------------
echo ""
echo "▸ Python __pycache__ directories:"
find "$PROJECT_ROOT" -type d -name "__pycache__" -not -path "*/.git/*" -not -path "*/node_modules/*" | while read -r dir; do
  echo "    $dir"
  $DRY_RUN || rm -rf "$dir"
done

echo ""
echo "▸ .pyc / .pyo files:"
find "$PROJECT_ROOT" -type f \( -name "*.pyc" -o -name "*.pyo" \) -not -path "*/.git/*" | while read -r f; do
  echo "    $f"
  $DRY_RUN || rm -f "$f"
done

# ---------------------------------------------------------------------------
# 2. Pytest cache
# ---------------------------------------------------------------------------
echo ""
echo "▸ .pytest_cache directories:"
find "$PROJECT_ROOT" -type d -name ".pytest_cache" | while read -r dir; do
  echo "    $dir"
  $DRY_RUN || rm -rf "$dir"
done

# ---------------------------------------------------------------------------
# 3. Node caches
# ---------------------------------------------------------------------------
echo ""
echo "▸ node_modules directories:"
find "$PROJECT_ROOT" -type d -name "node_modules" -not -path "*/.git/*" | while read -r dir; do
  echo "    $dir"
  $DRY_RUN || rm -rf "$dir"
done

echo ""
echo "▸ .pnpm-store:"
if [ -d "$PROJECT_ROOT/.pnpm-store" ]; then
  echo "    $PROJECT_ROOT/.pnpm-store"
  $DRY_RUN || rm -rf "$PROJECT_ROOT/.pnpm-store"
fi

# ---------------------------------------------------------------------------
# 4. OS metadata
# ---------------------------------------------------------------------------
echo ""
echo "▸ .DS_Store / Thumbs.db files:"
find "$PROJECT_ROOT" -type f \( -name ".DS_Store" -o -name "Thumbs.db" -o -name "Desktop.ini" \) -not -path "*/.git/*" | while read -r f; do
  echo "    $f"
  $DRY_RUN || rm -f "$f"
done

# ---------------------------------------------------------------------------
# 5. Stale model checkpoints (keep only the active weights)
#    Active weights are: data/models/yolo_interior.pt and yolo_interior.onnx
# ---------------------------------------------------------------------------
echo ""
echo "▸ Outdated model checkpoints (.onnx / .pt outside data/models/):"
find "$PROJECT_ROOT" -type f \( -name "*.onnx" -o -name "*.pt" \) \
  -not -path "$PROJECT_ROOT/data/models/yolo_interior.pt" \
  -not -path "$PROJECT_ROOT/data/models/yolo_interior.onnx" \
  -not -path "*/.git/*" | while read -r f; do
  echo "    $f"
  $DRY_RUN || rm -f "$f"
done

# ---------------------------------------------------------------------------
# 6. Old log files
# ---------------------------------------------------------------------------
echo ""
echo "▸ Log files (*.log):"
find "$PROJECT_ROOT" -type f -name "*.log" -not -path "*/.git/*" -not -path "*/node_modules/*" | while read -r f; do
  echo "    $f"
  $DRY_RUN || rm -f "$f"
done

# ---------------------------------------------------------------------------
# 7. Temporary / output directories
# ---------------------------------------------------------------------------
echo ""
echo "▸ tmp/ and output/ directories:"
for dir_name in tmp output; do
  target="$PROJECT_ROOT/$dir_name"
  if [ -d "$target" ]; then
    echo "    $target"
    $DRY_RUN || rm -rf "$target"
  fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "─────────────────────────────────────────────────────"
if $DRY_RUN; then
  echo "✅  Dry run complete. Run with --execute to delete the above files."
else
  echo "✅  Cleanup complete."
fi
