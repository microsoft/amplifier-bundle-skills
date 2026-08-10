#!/usr/bin/env bash
# batch_status.sh <manifest.tsv> [base_sha]
#
# One line per lane. This is the instrument the monitor reads.
# Cost: stat-only liveness, ~8ms per lane. File size is irrelevant --
# a 750MB events.jsonl costs the same as an empty one.
#
# Manifest is TSV, one row per lane, comment lines start with '#':
#   lane <TAB> worktree <TAB> branch <TAB> tmux <TAB> goal <TAB> log <TAB> session_id
#
# SHOW_LAST=1  also print the last 3 top-level turns per lane.
#
# --- signals, and why these and not the obvious ones -------------------------
# LIVENESS  = newest events.jsonl mtime anywhere in the lane's workspace.
#   NOT transcript.jsonl mtime. transcript.jsonl only advances on completed
#   ROOT-LEVEL tool calls, so a lane delegating to a sub-agent for 20 minutes
#   has a completely frozen transcript. Measured: 4 live sessions sampled 124s
#   apart showed ZERO transcript movement, including one blocked inside a single
#   delegate call. events.jsonl mtime tracked wall clock (+76s/+80s over 78s).
# PROGRESS  = assistant turns counted from the transcript.
#   NOT metadata.turn_count -- it is corrupt. Observed: turn_count=1 on a
#   session with 21 assistant turns; turn_count=40 on one with 348.
# PUSHED    = git ls-remote.
#   NOT @{upstream} -- `git push origin <branch>` sets no tracking config, so a
#   pushed branch reads as never-pushed.
# TERMINAL  = DONE.json written by the lane as its final act.
#   Pane death alone cannot distinguish "goal satisfied" from "killed".
#
# Requires GNU find (-printf), jq, git, tmux.
# -----------------------------------------------------------------------------

set -uo pipefail

MAN="${1:?usage: batch_status.sh <manifest.tsv> [base_sha]}"
BASE_SHA="${2:-}"
STATE="${GOAL_BATCH_STATE:-/tmp/goal-batch-state}"
WARM="${GOAL_BATCH_WARM:-120}"    # idle < WARM -> WORKING
COLD="${GOAL_BATCH_COLD:-900}"    # idle < COLD -> SLOW, else STALLED
CI_BASE="${AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH:-$HOME/.amplifier/projects}"

mkdir -p "$STATE"
NOW=$(date +%s)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

printf '%-14s %-19s %-8s %-10s %-8s %-6s %-7s %s\n' \
  LANE VERDICT IDLE TURNS COMMITS DIRTY PUSHED BRANCH

while IFS=$'\t' read -r lane wt branch tmuxname goal log sid; do
  case "${lane:-}" in ''|'#'*) continue ;; esac

  done_json=no
  [ -f "$wt/DONE.json" ] && done_json=yes

  # --- liveness (stat only, never a read) ------------------------------------
  slug="$(printf '%s' "$wt" | tr '/' '-')"
  ws="$CI_BASE/$slug/sessions"
  newest=$(find "$ws" -maxdepth 2 -name events.jsonl -printf '%T@\n' 2>/dev/null \
           | sort -rn | head -1)
  newest="${newest%%.*}"
  if [ -n "${newest:-}" ]; then idle=$(( NOW - newest )); idle_s="${idle}s"
  else                          idle=-1;                 idle_s="n/a"; fi

  # --- progress --------------------------------------------------------------
  turns='-'
  tr_file="$ws/${sid:-__none__}/transcript.jsonl"
  if [ -f "$tr_file" ]; then
    n=$(jq -r 'select(.role=="assistant")|1' "$tr_file" 2>/dev/null | wc -l | tr -d ' ')
    prev=$(cat "$STATE/${sid}.turns" 2>/dev/null || echo 0)
    printf '%s' "$n" > "$STATE/${sid}.turns"
    turns="${n}+$(( n - prev ))"
  fi

  # --- git facts -------------------------------------------------------------
  if [ -d "$wt" ]; then
    dirty=$(git -C "$wt" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    if [ -n "$BASE_SHA" ]; then
      commits=$(git -C "$wt" rev-list --count "${BASE_SHA}..HEAD" 2>/dev/null || echo '-')
    else
      commits=$(git -C "$wt" rev-list --count HEAD 2>/dev/null || echo '-')
    fi
    pushed=$(timeout 20 git -C "$wt" ls-remote --heads origin "$branch" 2>/dev/null | grep -c .)
  else
    dirty='-'; commits='-'; pushed='-'
  fi

  alive=no
  tmux has-session -t "$tmuxname" 2>/dev/null && alive=yes

  # --- verdict (precedence matters; liveness only applies while alive) --------
  if   [ ! -d "$wt" ];                                                    then v=WORKTREE-MISSING
  elif [ "$done_json" = yes ] && [ "$dirty" != 0 ];                       then v=LANDED-DIRTY
  elif [ "$done_json" = yes ] && [ "$pushed" = 0 ];                       then v=LANDED-NOT-PUSHED
  elif [ "$done_json" = yes ];                                            then v=LANDED
  elif [ "$alive" = yes ] && [ "$idle" -lt 0 ];                           then v=STARTING
  elif [ "$alive" = yes ] && [ "$idle" -lt "$WARM" ];                     then v=WORKING
  elif [ "$alive" = yes ] && [ "$idle" -lt "$COLD" ];                     then v=SLOW
  elif [ "$alive" = yes ];                                                then v=STALLED
  elif [ "$idle" -lt 0 ];                                                 then v=NOT-STARTED
  else                                                                         v=DIED
  fi

  printf '%-14s %-19s %-8s %-10s %-8s %-6s %-7s %s\n' \
    "$lane" "$v" "$idle_s" "$turns" "$commits" "$dirty" "$pushed" "$branch"

  if [ "${SHOW_LAST:-0}" = 1 ] && [ -f "$tr_file" ]; then
    "$HERE/lane_turns.sh" "$tr_file" 3 200 | sed 's/^/    /'
  fi
done < "$MAN"
