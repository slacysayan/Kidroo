#!/usr/bin/env bash
# SKILLS.sh — bootstrap installer for Kidroo.
#
# Installs all system-level dependencies, language toolchains, and package
# managers required by the repo, then:
#   (1) registers the in-repo dev-agent skill tree under `.agents/skills/`
#   (2) installs the external vendor-authored skills pinned in `.skills/manifest.json`
#       via `npx skills add` (https://skills.sh)
#
# Idempotent: safe to re-run. Each step is skipped if already satisfied.
#
# Usage:
#   ./SKILLS.sh                      # full install (deps + both skill trees)
#   ./SKILLS.sh --doctor             # verify an existing install, no changes
#   ./SKILLS.sh --skills-only        # skip system deps, just register both skill trees
#   ./SKILLS.sh --skills-install     # install only the `.skills/manifest.json` entries
#   ./SKILLS.sh --skills-update      # run `npx skills check && npx skills update`
#   ./SKILLS.sh --skills-find <q>    # search skills.sh for skills to add

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

MODE="install"
FIND_QUERY=""
while (( $# )); do
  case "$1" in
    --doctor)         MODE="doctor"         ;;
    --skills-only)    MODE="skills-only"    ;;
    --skills-install) MODE="skills-install" ;;
    --skills-update)  MODE="skills-update"  ;;
    --skills-find)    MODE="skills-find"; shift; FIND_QUERY="${1:-}" ;;
    -h|--help)        sed -n '2,20p' "$0"; exit 0 ;;
    *)                printf "Unknown flag: %s\n" "$1" >&2; exit 2 ;;
  esac
  shift
done

# ─── styling ──────────────────────────────────────────────────────────────
BOLD="$(printf '\033[1m')"; DIM="$(printf '\033[2m')"; RESET="$(printf '\033[0m')"
GREEN="$(printf '\033[32m')"; YELLOW="$(printf '\033[33m')"; RED="$(printf '\033[31m')"
CYAN="$(printf '\033[36m')"
step()    { printf "%s▶%s %s\n" "$BOLD" "$RESET" "$*"; }
ok()      { printf "  %s✓%s %s\n" "$GREEN" "$RESET" "$*"; }
warn()    { printf "  %s!%s %s\n" "$YELLOW" "$RESET" "$*"; }
info()    { printf "  %s·%s %s\n" "$CYAN" "$RESET" "$*"; }
fail()    { printf "  %s✗%s %s\n" "$RED" "$RESET" "$*"; exit 1; }
have()    { command -v "$1" >/dev/null 2>&1; }

# ─── helpers ──────────────────────────────────────────────────────────────

# Ensure we have a node/npx binary; if not, try to enable one from fnm.
ensure_npx() {
  if ! have npx; then
    if [[ -d "$HOME/.local/share/fnm" ]]; then
      export PATH="$HOME/.local/share/fnm:$PATH"
      eval "$(fnm env --use-on-cd 2>/dev/null || true)"
    fi
  fi
  have npx || fail "npx not found — install Node 20 first (run ./SKILLS.sh without flags)"
}

# Install every entry in .skills/manifest.json via `npx skills add`.
install_manifest_skills() {
  ensure_npx
  local manifest="$ROOT/.skills/manifest.json"
  [[ -f "$manifest" ]] || { warn ".skills/manifest.json missing — nothing to install"; return 0; }

  if ! have jq; then
    if have apt-get; then sudo apt-get install -y --no-install-recommends jq
    elif have brew;    then brew install jq
    else warn "jq not found and cannot be auto-installed; install it and re-run"; return 1
    fi
  fi

  local count=0
  local failed=0
  while IFS=$'\t' read -r source skill group why; do
    [[ -z "$skill" || -z "$source" ]] && continue
    count=$((count+1))
    info "[$group] $skill  —  $why"
    if npx --yes skills add "$source" --skill "$skill" >/tmp/skills-install.log 2>&1; then
      ok "installed: $skill"
    else
      warn "failed to install $skill (source=$source). Log: /tmp/skills-install.log"
      failed=$((failed+1))
    fi
  done < <(jq -r '.skills[] | [.source, .skill, .group, .why] | @tsv' "$manifest")

  if (( failed == 0 )); then
    ok "all $count manifest skills installed"
  else
    warn "$failed / $count skills failed — check /tmp/skills-install.log"
  fi
}

update_manifest_skills() {
  ensure_npx
  step "Checking for skill updates"
  npx --yes skills check || true
  step "Updating skills"
  npx --yes skills update || true
  ok "skills updated (where available)"
}

find_skills() {
  ensure_npx
  [[ -n "$FIND_QUERY" ]] || fail "pass a query, e.g. ./SKILLS.sh --skills-find supabase"
  step "Searching skills.sh for: $FIND_QUERY"
  npx --yes skills find "$FIND_QUERY"
}

register_local_skills() {
  step "Registering in-repo dev-agent skills (.agents/skills/)"
  if [[ -d .agents/skills ]]; then
    local count=0
    while IFS= read -r f; do
      ok "skill: $(dirname "$f" | sed 's|^\.agents/skills/||')"
      count=$((count+1))
    done < <(find .agents/skills -name SKILL.md -type f | sort)
    [[ $count -eq 0 ]] && warn "no SKILL.md files found"
  else
    warn ".agents/skills/ not present"
  fi
}

# ─── mode short-circuits ──────────────────────────────────────────────────

case "$MODE" in
  skills-install) install_manifest_skills; exit 0 ;;
  skills-update)  update_manifest_skills;  exit 0 ;;
  skills-find)    find_skills;             exit 0 ;;
  skills-only)    register_local_skills; install_manifest_skills; exit 0 ;;
esac

# ─── preflight ────────────────────────────────────────────────────────────
step "Preflight"
OS="$(uname -s)"
case "$OS" in
  Linux)  ok "OS: Linux"  ;;
  Darwin) ok "OS: macOS"  ;;
  *) fail "Unsupported OS: $OS" ;;
esac

# ─── system deps ──────────────────────────────────────────────────────────
step "System dependencies"
if [[ "$OS" == "Linux" ]] && have apt-get; then
  if [[ "$MODE" == "install" ]]; then
    sudo apt-get update -qq
    sudo apt-get install -y --no-install-recommends \
      git curl ca-certificates build-essential jq \
      ffmpeg python3 python3-venv python3-pip
    ok "apt packages installed"
  else
    for p in git curl ffmpeg python3 jq; do
      have "$p" && ok "$p" || warn "$p missing"
    done
  fi
fi

# ─── uv (Python package manager) ─────────────────────────────────────────
step "uv (Python package manager)"
if ! have uv; then
  [[ "$MODE" == "doctor" ]] && warn "uv missing" || {
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    ok "uv installed"
  }
else
  ok "uv $(uv --version 2>/dev/null | awk '{print $2}')"
fi

# ─── Python toolchain ─────────────────────────────────────────────────────
step "Python 3.11 + project deps"
if have uv; then
  if [[ "$MODE" == "install" ]]; then
    uv python install 3.11 >/dev/null 2>&1 || true
    [[ -f pyproject.toml ]] && { uv sync --frozen 2>/dev/null || uv sync; ok "uv sync"; }
  else
    uv python list 2>/dev/null | grep -q 3.11 && ok "Python 3.11" || warn "Python 3.11 not installed"
  fi
fi

# ─── Node.js via fnm ──────────────────────────────────────────────────────
step "Node.js 20 + pnpm"
if ! have node; then
  [[ "$MODE" == "doctor" ]] && warn "node missing" || {
    curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell
    export PATH="$HOME/.local/share/fnm:$PATH"
    eval "$(fnm env --use-on-cd)"
    fnm install 20
    fnm default 20
    ok "Node $(node -v)"
  }
else
  ok "Node $(node -v)"
fi

if ! have pnpm; then
  [[ "$MODE" == "doctor" ]] && warn "pnpm missing" || { npm install -g pnpm@latest; ok "pnpm $(pnpm -v)"; }
else
  ok "pnpm $(pnpm -v)"
fi

if [[ -f package.json && "$MODE" == "install" ]]; then
  pnpm install --frozen-lockfile 2>/dev/null || pnpm install
  ok "pnpm install"
fi

# ─── yt-dlp ───────────────────────────────────────────────────────────────
step "yt-dlp"
if ! have yt-dlp; then
  [[ "$MODE" == "doctor" ]] && warn "yt-dlp missing" || {
    have uv && uv tool install yt-dlp || pip3 install --user yt-dlp
    ok "yt-dlp installed"
  }
else
  ok "yt-dlp $(yt-dlp --version 2>/dev/null)"
fi

# ─── Composio CLI ────────────────────────────────────────────────────────
step "Composio CLI"
if ! have composio; then
  [[ "$MODE" == "doctor" ]] && warn "composio CLI missing (ok — SDK is sufficient)" || {
    have uv && uv tool install composio-core 2>/dev/null || pip3 install --user composio-core
    ok "composio installed"
  }
else
  ok "composio $(composio --version 2>/dev/null | head -1)"
fi

# ─── Supabase CLI ────────────────────────────────────────────────────────
step "Supabase CLI"
if ! have supabase; then
  [[ "$MODE" == "doctor" ]] && warn "supabase CLI missing (ok — migrations can be applied via psql)" || {
    if have npm; then
      npm install -g supabase 2>/dev/null || warn "couldn't install supabase CLI globally — skipping"
    fi
  }
else
  ok "supabase $(supabase --version 2>/dev/null)"
fi

# ─── pre-commit hooks ────────────────────────────────────────────────────
step "pre-commit hooks"
if [[ -f .pre-commit-config.yaml ]]; then
  if ! have pre-commit; then
    have uv && uv tool install pre-commit || pip3 install --user pre-commit
  fi
  pre-commit install --install-hooks 2>/dev/null && ok "pre-commit installed" || warn "pre-commit install skipped"
else
  warn ".pre-commit-config.yaml not present yet — will be added in a later phase"
fi

# ─── register in-repo skills ──────────────────────────────────────────────
register_local_skills

# ─── install external vendor skills (skills.sh) ───────────────────────────
step "Installing external agent skills (.skills/manifest.json via npx skills)"
if [[ "$MODE" == "doctor" ]]; then
  [[ -f .skills/manifest.json ]] && ok ".skills/manifest.json present" || warn ".skills/manifest.json missing"
else
  install_manifest_skills || warn "external skills install had errors — continue bootstrap"
fi

# ─── .env check ───────────────────────────────────────────────────────────
step "Environment"
if [[ ! -f .env ]]; then
  warn ".env not found — copy .env.example to .env and fill in your keys"
else
  ok ".env present"
fi

# ─── summary ──────────────────────────────────────────────────────────────
printf "\n%s✓ Bootstrap complete%s  (mode=%s)\n" "$GREEN$BOLD" "$RESET" "$MODE"
printf "%sNext:%s\n" "$BOLD" "$RESET"
printf "  1. cp .env.example .env  &&  edit secrets\n"
printf "  2. supabase db push  (or psql \$SUPABASE_DB_URL -f supabase/migrations/001_initial_schema.sql)\n"
printf "  3. composio connections create --toolkit YOUTUBE --user-id <channel_name>\n"
printf "  4. pnpm dev  (frontend)  +  uv run fastapi dev apps/api/main.py  (backend)\n"
printf "  %sTip:%s  add a skill later with:\n" "$DIM" "$RESET"
printf "         ./SKILLS.sh --skills-find <query>\n"
printf "         # then append the {source, skill, why, group} tuple to .skills/manifest.json\n"
printf "         ./SKILLS.sh --skills-install\n"
