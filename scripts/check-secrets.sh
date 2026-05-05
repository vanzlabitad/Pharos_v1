#!/usr/bin/env bash
# Block secrets from being committed or merged.
#
# Patterns:
#   AIza[A-Za-z0-9_-]{35}            — Google API key prefix + body (Gemini,
#                                       primary provider for AI summaries)
#   NEXT_PUBLIC_(GEMINI|GOOGLE)      — any Next.js public env var that would
#                                       ship the Gemini key to the browser
#
# Defensive layer (kept in case the project ever experiments with Claude):
#   sk-ant-[A-Za-z0-9_-]{20,}        — Anthropic API key prefix + body
#   NEXT_PUBLIC_ANTHROPIC            — Anthropic equivalent of the above
#
# Usage:
#   scripts/check-secrets.sh --all                 # scan every tracked file (CI)
#   scripts/check-secrets.sh path/to/file [...]    # scan listed files (hook)
#
# Exits 1 if any forbidden pattern is found. Allowlist below covers files
# that legitimately mention the patterns (docs, this script, the hook).

set -euo pipefail

# ── Forbidden patterns ──────────────────────────────────────────────────────
PATTERN='(AIza[A-Za-z0-9_-]{35}|sk-ant-[A-Za-z0-9_-]{20,}|NEXT_PUBLIC_(GEMINI|GOOGLE|ANTHROPIC))'

# Files that are *allowed* to mention the forbidden patterns (docs, hook,
# this script). One regex per line, anchored to the repo-relative path.
ALLOWLIST_REGEX='^(scripts/check-secrets\.sh|\.env\.example|\.github/workflows/secret-scan\.yml|\.githooks/pre-commit|CLAUDE\.md|docs/.*\.md)$'

# Binary / large file extensions to skip (false-positive risk, slow to scan).
SKIP_EXT_REGEX='\.(png|jpg|jpeg|gif|webp|pdf|woff|woff2|ttf|eot|ico|zip|tar|gz)$'

# ── Build file list ─────────────────────────────────────────────────────────
if [[ "${1:-}" == "--all" ]]; then
    mapfile -t files < <(git ls-files)
elif [[ $# -eq 0 ]]; then
    echo "Usage: $0 --all | <file> [<file> ...]" >&2
    exit 2
else
    files=("$@")
fi

# ── Scan ────────────────────────────────────────────────────────────────────
hits=()
for f in "${files[@]}"; do
    [[ -z "$f" ]] && continue
    [[ ! -f "$f" ]] && continue
    [[ "$f" =~ $ALLOWLIST_REGEX ]] && continue
    [[ "$f" =~ $SKIP_EXT_REGEX ]] && continue

    if matches=$(grep -EHn "$PATTERN" "$f" 2>/dev/null); then
        hits+=("$matches")
    fi
done

# ── Report ──────────────────────────────────────────────────────────────────
if (( ${#hits[@]} > 0 )); then
    echo "ERROR — forbidden secret pattern detected:" >&2
    printf '%s\n' "${hits[@]}" >&2
    echo "" >&2
    echo "Allowed in: scripts/check-secrets.sh, .env.example, CLAUDE.md, docs/*.md," >&2
    echo "            .github/workflows/secret-scan.yml, .githooks/pre-commit" >&2
    echo "" >&2
    echo "If this is a real key: rotate it immediately at the provider console" >&2
    echo "(Gemini: https://aistudio.google.com/app/apikey ;" >&2
    echo " Anthropic: https://console.anthropic.com/settings/keys), then remove from history." >&2
    exit 1
fi

exit 0
