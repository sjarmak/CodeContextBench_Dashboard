#!/bin/bash
# scripts/compound/toggle.sh
# Toggle the nightly compound loop on/off
#
# Usage:
#   ./toggle.sh          # Show current status
#   ./toggle.sh on       # Enable the nightly loop
#   ./toggle.sh off      # Disable the nightly loop

LABEL_REVIEW="com.compound.codecontextbench.review"
LABEL_COMPOUND="com.compound.codecontextbench.compound"
PLIST_REVIEW="/Users/sjarmak/Library/LaunchAgents/$LABEL_REVIEW.plist"
PLIST_COMPOUND="/Users/sjarmak/Library/LaunchAgents/$LABEL_COMPOUND.plist"

is_loaded() {
  launchctl list 2>/dev/null | grep -q "$1"
}

show_status() {
  echo "Compound Engineering Loop: CodeContextBench"
  echo "─────────────────────────────────────────"
  if is_loaded "$LABEL_REVIEW"; then
    echo "  Review (22:30):    ON"
  else
    echo "  Review (22:30):    OFF"
  fi
  if is_loaded "$LABEL_COMPOUND"; then
    echo "  Compound (23:00): ON"
  else
    echo "  Compound (23:00): OFF"
  fi
}

case "${1:-status}" in
  on)
    echo "Enabling nightly loop for CodeContextBench..."
    launchctl load "$PLIST_REVIEW" 2>/dev/null && echo "  Review: loaded" || echo "  Review: already loaded"
    launchctl load "$PLIST_COMPOUND" 2>/dev/null && echo "  Compound: loaded" || echo "  Compound: already loaded"
    echo ""
    show_status
    ;;
  off)
    echo "Disabling nightly loop for CodeContextBench..."
    launchctl unload "$PLIST_REVIEW" 2>/dev/null && echo "  Review: unloaded" || echo "  Review: already unloaded"
    launchctl unload "$PLIST_COMPOUND" 2>/dev/null && echo "  Compound: unloaded" || echo "  Compound: already unloaded"
    echo ""
    show_status
    ;;
  status|"")
    show_status
    ;;
  *)
    echo "Usage: ./toggle.sh [on|off|status]"
    exit 1
    ;;
esac
