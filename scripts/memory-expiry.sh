#!/bin/bash
# memory-expiry.sh
DAYS=30
MEMORY_DIR="memory"

find "$MEMORY_DIR" -name "*.md" -mtime +$DAYS | while read f; do
  # Skip if contains TODO
  if ! grep -q "TODO\|待办\|未完成" "$f"; then
    echo "Expiring: $f"
    rm "$f"
  fi
done
