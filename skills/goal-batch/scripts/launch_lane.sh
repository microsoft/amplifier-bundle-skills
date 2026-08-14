#!/usr/bin/env bash
# launch_lane.sh <batch> <lane> <worktree> <goal-rel-path> <manifest> [wall_s] [max_turns]
#
#   batch/lane     name the batch and the lane. tmux session and log path are
#                  DERIVED from them -- gb__<batch>__<lane> and
#                  /tmp/gb-<batch>-<lane>.log -- so the naming convention that
#                  the orphan sweep and pane-viewer match strings depend on
#                  cannot drift.
#   goal-rel-path  path RELATIVE TO THE WORKTREE. Must be committed to the base
#                  commit before `git worktree add`, so every worktree has it.
#   manifest       the batch manifest. THIS SCRIPT OWNS IT: it writes the header
#                  on first call and appends one row per lane. Nothing else
#                  should ever write it by hand.
#   wall_s         wall-clock bound, default 7200. 0 disables.
#   max_turns      turn bound passed to /goal, default 0 (unlimited, ADR-0005).
#                  NOTE: --max-turns is parsed by /goal, NOT by `amplifier run`,
#                  so it rides inside the prompt string.
#
# MANIFEST SCHEMA (8 columns, tab-separated) -- batch_status.sh reads exactly this:
#   lane  worktree  branch  tmux  goal  log  session_id  pid
#
# v2 changes, each bought with a measured failure in real team use:
#  - Owns the manifest end-to-end. v1 emitted 5 columns while batch_status.sh
#    read 7; the two never agreed, and every real user hand-wrote the manifest
#    to work around it.
#  - Records the lane PID. tmux servers have died mid-batch in three separate
#    runs; PID liveness keeps the status probe working when tmux is gone.
#  - Purges any inherited DONE.json before launch. A DONE.json carried in
#    through the base commit reads as an already-finished lane.
#  - `setsid --wait`. Bare `setsid` launched ZERO of five lanes on another
#    operator's machine while working fine here.

set -uo pipefail

BATCH="${1:?batch name}"; LANE="${2:?lane name}"; WT="${3:?worktree}"
GOAL="${4:?goal path relative to worktree}"; MANIFEST="${5:?manifest path}"
WALL="${6:-7200}"; MAXTURNS="${7:-0}"

TMUXNAME="gb__${BATCH}__${LANE}"
LOG="/tmp/gb-${BATCH}-${LANE}.log"
PIDFILE="/tmp/gb-${BATCH}-${LANE}.pid"

# --- preflight: fail loud, never launch degraded ------------------------------
[ -d "$WT" ] || { echo "FATAL $LANE: worktree missing: $WT" >&2; exit 2; }
[ -f "$WT/$GOAL" ] || {
  echo "FATAL $LANE: goal file not in worktree: $WT/$GOAL" >&2
  echo "  Goal files must be COMMITTED to the base commit before 'git worktree add'." >&2
  exit 2; }
case "$GOAL" in *[\'\"\ \$\`\\]*)
  echo "FATAL $LANE: goal path has shell metachars: $GOAL" >&2; exit 2 ;; esac
case "$BATCH$LANE" in *[!a-zA-Z0-9-]*)
  echo "FATAL: batch/lane must be [a-zA-Z0-9-] only (got '$BATCH'/'$LANE')" >&2; exit 2 ;; esac
case "$MAXTURNS" in ''|*[!0-9]*)
  echo "FATAL $LANE: max_turns must be a non-negative integer: $MAXTURNS" >&2; exit 2 ;; esac

if tmux has-session -t "$TMUXNAME" 2>/dev/null; then
  echo "SKIP $LANE: tmux session '$TMUXNAME' already live (not clobbering)"
  exit 3
fi

# The lane runs under a non-login shell inside tmux. `amplifier` living only on a
# login-shell PATH is the difference between a clean abort here and a 60-second
# wait for a Session ID that can never arrive.
AMP="$(command -v amplifier || true)"
if [ -z "$AMP" ]; then
  AMP="$(bash -lc 'command -v amplifier' 2>/dev/null || true)"
  [ -n "$AMP" ] || { echo "FATAL $LANE: 'amplifier' not on PATH (checked plain and login shell)." >&2; exit 2; }
  echo "NOTE $LANE: amplifier only on the login PATH; pinning $AMP" >&2
fi

BRANCH=$(git -C "$WT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')

# A DONE.json inherited from the base commit means "finished" to every reader.
rm -f "$WT/DONE.json" "$PIDFILE"

# /goal parses a LEADING --max-turns; 0 means unlimited, so omit it entirely.
if [ "$MAXTURNS" -gt 0 ]; then PROMPT="/goal --max-turns ${MAXTURNS} @${GOAL}"
else                           PROMPT="/goal @${GOAL}"; fi

# Wrapper keeps quoting off the tmux command line and owns process-group cleanup
# that plain `timeout` does not do (it signals only its direct child).
WRAP="$(mktemp "/tmp/gb-wrap-${BATCH}-${LANE}-XXXXXX.sh")"
{
  echo '#!/usr/bin/env bash'
  printf 'echo $$ > %q\n' "$PIDFILE"
  echo 'trap '\''kill -- -$$ 2>/dev/null'\'' EXIT'
  if [ "$WALL" -gt 0 ]; then
    printf 'timeout --signal=TERM --kill-after=60s %ss %q run %q 2>&1 | tee %q\n' \
           "$WALL" "$AMP" "$PROMPT" "$LOG"
  else
    printf '%q run %q 2>&1 | tee %q\n' "$AMP" "$PROMPT" "$LOG"
  fi
  printf 'echo "LANE_EXIT=${PIPESTATUS[0]} $(date -Is)" >> %q\n' "$LOG"
} > "$WRAP"
chmod +x "$WRAP"

tmux new-session -d -s "$TMUXNAME" -c "$WT" "setsid --wait $WRAP"

# --- harvest the session ID; FAIL LOUD if it never appears --------------------
# The manifest is the crash anchor. A blank ID in it is worse than no manifest,
# because recovery will trust it.
SID=""
for _ in $(seq 1 24); do            # up to ~60s for a cold start
  sleep 2.5
  SID=$(grep -am1 'Session ID:' "$LOG" 2>/dev/null | sed 's/.*Session ID: *//' | tr -d '\r')
  [ -n "$SID" ] && break
  tmux has-session -t "$TMUXNAME" 2>/dev/null || break   # died during startup
done

if [ -z "$SID" ]; then
  alive=$(tmux has-session -t "$TMUXNAME" 2>/dev/null && echo yes || echo no)
  echo "FATAL $LANE: no Session ID after 60s (session alive=$alive). Log tail:" >&2
  tail -5 "$LOG" 2>/dev/null >&2
  exit 4
fi

PID=$(cat "$PIDFILE" 2>/dev/null || echo '-')

# --- write the manifest (header once, then one row per lane) ------------------
if [ ! -s "$MANIFEST" ]; then
  mkdir -p "$(dirname "$MANIFEST")"
  {
    printf '# lane\tworktree\tbranch\ttmux\tgoal\tlog\tsession_id\tpid\n'
    printf '# batch=%s launched_at=%s wall_s=%s max_turns=%s\n' \
           "$BATCH" "$(date +%s)" "$WALL" "$MAXTURNS"
  } > "$MANIFEST"
fi
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
  "$LANE" "$WT" "$BRANCH" "$TMUXNAME" "$GOAL" "$LOG" "$SID" "$PID" | tee -a "$MANIFEST"
