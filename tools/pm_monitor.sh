#!/bin/bash
# PM Monitoring Script
# Polls task status files and triggers Orchestrator when tasks complete
# Created: 2025-12-23
# Associated Task: E4 - Add PM monitoring protocol

POLLING_INTERVAL=60  # seconds
STATE_FILE="LogBook/pm/STATE.md"
DETECTIONS_LOG="LogBook/pm/detections.log"

echo "🔍 PM Monitoring started (polling every ${POLLING_INTERVAL}s)"

while true; do
  # Check all task status files
  for status_file in LogBook/progress/tasks/*/status.yaml; do
    if [ -f "$status_file" ]; then
      brick_dir=$(dirname "$status_file")
      task_id=$(basename "$brick_dir")
      status=$(grep "^status:" "$status_file" | awk '{print $2}')

      if [ "$status" == "COMPLETE_READY_FOR_REVIEW" ]; then
        timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        echo "✅ [$timestamp] Detected: $task_id ready for review"

        # Log detection
        echo "[$timestamp] Detected: $task_id COMPLETE_READY_FOR_REVIEW" >> "$DETECTIONS_LOG"

        # Update PM state (if STATE.md exists)
        # Note: `sed -i.bak` is portable across GNU/BSD sed (macOS + Linux).
        # The .bak file is always created, so rm it immediately.
        if [ -f "$STATE_FILE" ]; then
          sed -i.bak "s/  - $task_id: IN_PROGRESS/  - $task_id: PENDING_REVIEW/" "$STATE_FILE"
          rm -f "$STATE_FILE.bak"
        fi

        # Invoke Orchestrator
        echo "🔄 Invoking Orchestrator for $task_id..."

        # Try to invoke the orchestrator via available methods
        ORCHESTRATOR_INVOKED=false

        # Method 1: Use critic_orchestrator.py if available
        if [ -f "tools/critic_orchestrator.py" ]; then
          python3 tools/critic_orchestrator.py --task "$task_id" --action evaluate 2>&1 | tee -a "$DETECTIONS_LOG"
          ORCHESTRATOR_INVOKED=true
        # Method 2: Use GitHub workflow dispatch
        elif command -v gh &> /dev/null; then
          gh workflow run critic-orchestrator.yml -f task_id="$task_id" 2>&1 || true
          ORCHESTRATOR_INVOKED=true
        # Method 3: Write request file for async processing
        else
          REQUEST_DIR="LogBook/critic/requests"
          mkdir -p "$REQUEST_DIR"
          REQUEST_FILE="${REQUEST_DIR}/${task_id}-$(date +%s).yaml"
          cat > "$REQUEST_FILE" << EOF
task_id: $task_id
requested_at: $timestamp
requested_by: pm_monitor
action: evaluate
status: pending
EOF
          echo "📝 Created orchestrator request: $REQUEST_FILE"
          ORCHESTRATOR_INVOKED=true
        fi

        # Log the invocation
        echo "[$timestamp] Invoked: Critic-Orchestrator for $task_id (method: ${ORCHESTRATOR_INVOKED})" >> "$DETECTIONS_LOG"

        # Mark as processed (change status to UNDER_REVIEW to avoid re-detection)
        sed -i.bak "s/status: COMPLETE_READY_FOR_REVIEW/status: UNDER_REVIEW/" "$status_file"
        rm -f "$status_file.bak"

        echo "✅ [$timestamp] $task_id status updated to UNDER_REVIEW"
      fi
    fi
  done

  # Update last check timestamp (if STATE.md exists)
  if [ -f "$STATE_FILE" ]; then
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    sed -i.bak "s/last_check:.*/last_check: \"$timestamp\"/" "$STATE_FILE"
    rm -f "$STATE_FILE.bak"
  fi

  # Sleep before next poll
  sleep $POLLING_INTERVAL
done
