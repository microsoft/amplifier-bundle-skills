#!/usr/bin/env bash
# launch_lane.sh <lane> <worktree> <goal-file> <tmux-name> <log> [wall_s] [max_turns]
#
#   goal-file  path RELATIVE TO THE WORKTREE. It must be committed to the base
#              commit before `git worktree add`, so every worktree contains it.
#   wall_s     wall-clock bound, default 7200. 0 disables.
#   max_turns  turn bound passed to /goal, default 0 (unlimited, per ADR-0005).
#
# Prints one manifest TSV row on success:  lane  worktree  tmux  log  session_id
#
# Four structural properties, each fixing a measured failure:
#
# 1. NO USER PROSE IN THE SHELL STRING. The tmux command carries only a
#    fixed-shape path, validated for metacharacters. Launch notes go INSIDE the
#    goal file. A lone apostrophe in a launch note silently truncated a real
#    launch; this makes that unrepresentable rather than warned about.
# 2. LOGGING SURVIVES. `tee` runs inside the wrapper, so the log that the
#    manifest, the session-ID harvest and crash recovery all depend on exists.
# 3. BOUNDED, AND THE WHOLE TREE DIES. `timeout` bounds wall-clock; an EXIT trap
#    signals the entire process group, so a bounded-out lane does not leave
#    orphaned children behind (plain `timeout` signals only its direct child).
#    `--max-turns` bounds turns -- note it is parsed by /goal, NOT by
#    `amplifier run`, so it goes INSIDE the prompt string.
# 4. FAILS LOUD on no session ID rather than writing a blank into the manifest,
#    which is the crash anchor and gets trusted during recovery.

set -uo pipefail

LANE="${1:?lane}"; WT="${2:?worktree}"; GOAL="${3:?goal-file (relative to worktree)}"
TMUXNAME="${4:?tmux-name}"; LOG="${5:?log}"; WALL="${6:-7200}"; MAXTURNS="${7:-0}"

[ -d "$WT" ] || { echo "FATAL $LANE: worktree missing: $WT" >&2; exit 2; }
[ -f "$WT/$GOAL" ] || {
  echo "FATAL $LANE: goal file not in worktree: $WT/$GOAL" >&2
  echo "  Goal files must be COMMITTED to the base commit before 'git worktree add'." >&2
  exit 2; }

case "$GOAL" in
  *[\'\"\ \$\`\\]*) echo "FATAL $LANE: goal path has shell metachars: $GOAL" >&2; exit 2 ;;
esac
case "$MAXTURNS" in ''|*[!0-9]*) echo "FATAL $LANE: max_turns must be a non-negative integer: $MAXTURNS" >&2; exit 2 ;; esac

if tmux has-session -t "$TMUXNAME" 2>/dev/null; then
  echo "SKIP $LANE: tmux session '$TMUXNAME' already live (not clobbering)"
  exit 3
fi

# /goal parses a LEADING --max-turns; 0 means unlimited, so omit it entirely.
if [ "$MAXTURNS" -gt 0 ]; then PROMPT="/goal --max-turns ${MAXTURNS} @${GOAL}"
else                           PROMPT="/goal @${GOAL}"; fi

# Wrapper file: keeps quoting out of the tmux command line, and owns the
# process-group cleanup that plain `timeout` does not do.
WRAP="$(mktemp "/tmp/gb-wrap-${LANE}-XXXXXX.sh")"
{
  echo '#!/usr/bin/env bash'
  echo 'trap '\''kill -- -$$ 2>/dev/null'\'' EXIT'
  if [ "$WALL" -gt 0 ]; then
    printf 'timeout --signal=TERM --kill-after=60s %ss amplifier run %q 2>&1 | tee %q\n' \
           "$WALL" "$PROMPT" "$LOG"
  else
    printf 'amplifier run %q 2>&1 | tee %q\n' "$PROMPT" "$LOG"
  fi
  printf 'echo "LANE_EXIT=${PIPESTATUS[0]} $(date -Is)" >> %q\n' "$LOG"
} > "$WRAP"
chmod +x "$WRAP"

tmux new-session -d -s "$TMUXNAME" -c "$WT" "setsid $WRAP"

# --- harvest the session ID, FAIL LOUD if it never appears -------------------
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

printf '%s\t%s\t%s\t%s\t%s\n' "$LANE" "$WT" "$TMUXNAME" "$LOG" "$SID"
