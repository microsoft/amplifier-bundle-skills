---
name: one-line-installer-patterns
description: >
  Use when designing a curl-piped install script for a project that cannot use
  uv tool install or npm publish — multi-service stacks (Docker Compose),
  raw TS/React apps, tools that bootstrap system dependencies, or installs
  for non-technical audiences. Documents the security trade-off, the community
  convention used by rustup, bun, deno, fly, ollama, and supabase, and the
  cases where this pattern is the wrong answer.
---

# One-Line Installer Patterns

## When this pattern is the right tool

A `curl … | bash` install script is the right answer in a narrow set of cases. Outside that set, simpler distribution mechanisms exist and should be used.

**Use this pattern when:**

- The project is multi-language (Python + Node + Docker) and `uv tool install` cannot do the job alone
- The project requires system prerequisites that must be detected and clearly directed (Docker, Node via fnm/volta, jq, etc.)
- The intended audience is non-technical and cannot be expected to run more than one command
- The "real" install is `docker compose up`, but the user needs a clean way to land the compose file, generate an `.env`, and start the stack

**Don't use this pattern when:**

- The project is a Python CLI → use `uv tool install git+...` and see `cli-packaging-patterns`
- The project is a Node CLI → publish to npm, document `npx <tool>` or `pnpm dlx <tool>`
- The project produces a single static binary → ship via GitHub releases, document `curl -L .../tool -o ~/.local/bin/tool && chmod +x ~/.local/bin/tool`. This is the modern Go/Rust default.
- The project is a pure containerized app → ship a `docker-compose.yml`. The "install command" is `docker compose up -d`. Plausible, n8n, and Outline all do this.

A `curl | bash` script is a thin wrapper around one of the four real distribution mechanisms above. It is not its own distribution mechanism.

## The security trade-off, stated honestly

Piping a remote script to a shell executes whatever the server returns at the moment of invocation. The user has no opportunity to inspect what runs. The trust model is roughly equivalent to running any other unverified binary from the internet — not worse, but not better.

There is also a documented attack class: a malicious server can detect a `curl | bash` invocation by stalling the response and serve different content than it would to a `curl > install.sh && less install.sh` inspection. See https://www.idontplaydarts.com/2016/04/detecting-curl-pipe-bash-server-side/ — this is real and demonstrated, not theoretical.

**Required mitigations:**

- Serve over HTTPS only. Reject `http://`.
- Host the script in the same git repo as the code it installs, so the script is reviewable in version control.
- Document the review-first variant alongside the one-liner. Treat the one-liner as the lazy path, not the only path.
- Pin a version (git tag or release ref) in the URL when possible, instead of chasing `main`.
- For sensitive deployments, ship signed releases (cosign or GPG) and have the script verify signatures before extracting any artifact.

**What this pattern cannot give you:**

- Strong supply-chain guarantees. If the host is compromised, every install is compromised. There is no offline review.
- Reproducibility across time. The script the user sees today may not be the script they see tomorrow. Version-pin or accept the drift.

## The community convention for the one-liner

```bash
curl -fsSL https://example.com/install.sh | bash
```

This shape is used by rustup, bun, deno, fly, ollama, pnpm, supabase, and most others. Conform to it.

- `curl -fsSL`: fail on HTTP error (`-f`), silent progress (`-s`), show errors (`-S`), follow redirects (`-L`)
- `| bash` — not `| sh`. Almost no production installer is strict POSIX sh. Bash 3.2 (the macOS default) is the realistic floor. Documenting `| bash` is honest about what the script actually requires.

For arguments, use the rustup convention:

```bash
curl -fsSL https://.../install.sh | bash -s -- --version 1.2.3 --no-modify-path
```

The `bash -s --` form is broadly understood and supported.

For the review-first variant, document this prominently in the README — not as a footnote:

```bash
curl -fsSL https://.../install.sh -o install.sh
less install.sh
bash install.sh
```

## What the installer should do, in order

```
1. set -euo pipefail; trap cleanup EXIT
2. Detect: OS, arch, libc (glibc vs musl), shell, existing install
3. Parse flags and env vars
4. Print the install plan; require Enter unless --yes or non-interactive
5. Detect prerequisites; abort with clear remediation if missing
   (do NOT bootstrap someone else's package manager)
6. Fetch the artifact (tagged release tarball preferred, git clone fallback)
7. Verify (sha256sum or signature)
8. Extract to ~/.local/share/<tool>/<version>
9. Symlink ~/.local/bin/<tool> → the real binary
10. Detect shell rc and offer (with consent) to add to PATH
11. Print "what's next" — a literal command the user can copy
12. Exit 0
```

## What the installer should NOT do

- **Bootstrap Node, Python, or another language toolchain.** Detect and direct. Tell the user to install Node via fnm/volta/nvm, Python via uv/pyenv. Bootstrapping someone else's package manager from your installer creates conflicts with whatever version manager the user already runs.
- **Touch `/usr/local` without sudo and explicit consent.** Default to `$HOME`. Never use sudo silently.
- **Run a configuration wizard.** Print the next command for the user to run. Wizards inside install scripts are rare in the broader community and consistently more brittle than wizards inside the tool itself. Auth flows must be invoked by the user after install — stdin is the curl pipe, not the user.
- **Overwrite an existing install without confirmation.** Detect, then act.
- **Pipe a remote tarball directly into `tar` without verification.** Download to disk, verify a checksum, then extract.

## Post-install: what command to actually point users to

This is a place where the Amplifier ecosystem's `<tool> init` convention diverges from the broader community. Survey of major CLIs:

| Tool | First-run command | Pattern |
|------|-------------------|---------|
| rustup | (none — install configures) | Install IS the config |
| bun | (none — just works) | Lazy / sensible defaults |
| deno | (none — just works) | Lazy / sensible defaults |
| ollama | `ollama pull <model>` | Use is the config |
| pnpm | (none) | Lazy |
| nvm | `nvm install <ver>` | Use is the config |
| volta | `volta install node` | Use is the config |
| **gh** | `gh auth login` | Auth subcommand |
| **vercel** | `vercel login` | Auth subcommand |
| **heroku** | `heroku login` | Auth subcommand |
| **flyctl** | `fly auth login` | Auth subcommand |
| **supabase** | `supabase login` | Auth subcommand |
| **1Password** | `op signin` | Auth subcommand |
| tailscale | `tailscale up` | Connect-as-config |
| AWS CLI | `aws configure` | `configure` subcommand |
| ngrok | `ngrok config add-authtoken …` | Granular config |
| gcloud | `gcloud init` | `init` = tool config (rare) |
| doctl | `doctl auth init` | `init` scoped to auth |
| terraform | `terraform init` | `init` = per-project setup |
| firebase | `firebase init` | `init` = per-project setup |
| git | `git init` | `init` = create new repo |
| npm | `npm init` | `init` = create package |
| cargo | `cargo init` | `init` = create project |

**Three observations:**

1. `init` overwhelmingly means "create a new project/workspace in the current directory" (git, npm, cargo, terraform, firebase). Using `init` for "configure the tool itself" has essentially one major precedent: `gcloud init`. The Amplifier ecosystem follows this minority convention.

2. Most modern CLIs have **no first-run setup command at all**. They prompt lazily, work with sensible defaults, or split auth into a clearly-named `login` subcommand.

3. For credentials specifically, `<tool> login` or `<tool> auth login` is the dominant pattern.

**Practical recommendation:**

| Tool needs | Recommended subcommand | Examples |
|------------|------------------------|----------|
| Auth/credentials only | `<tool> login` or `<tool> auth login` | gh, vercel, heroku, fly, supabase |
| Tool-wide config (region, defaults) | `<tool> configure` | aws |
| Per-project setup | `<tool> init` | terraform, firebase, npm, cargo |
| Sensible defaults; prompt when needed | (no subcommand) | bun, deno, rustup, pnpm |

If you are building a tool the broader community will use, prefer `login` / `configure` / no-command unless you actually mean "scaffold a new project here." `init` for tool-wide configuration is internally consistent for the Amplifier ecosystem (see `cli-packaging-patterns`) but is not what an outside engineer will expect.

The installer prints the next command. It does not execute it.

## Hard requirements

| Requirement | Why |
|-------------|-----|
| `set -euo pipefail` at top | Failures fail loudly. Without `pipefail`, `false \| true` succeeds silently. |
| Bash 3.2 compatible (macOS floor) | Old bash ships on macOS. `[[` and arrays work; `${var,,}` lowercase substitution does not. |
| `command -v` checks before every external call | curl, tar, git, sha256sum may be absent on minimal images |
| Default install to `$HOME` | No sudo unless necessary, with explicit consent |
| Idempotent re-run | Same inputs produce same final state. Partial work is rolled back on failure. |
| `mktemp -d` + `trap cleanup EXIT` | No tmpdir litter on failure |
| `printf` not `echo -e` | `echo` flags are not portable across shells |
| Detect WSL specifically | Browser open, service files, and clipboard differ from Linux |
| Print install location and uninstall command at end | The first question the user will have is "how do I undo this" |
| Pin version of fetched artifacts | `latest` breaks reproducibility across reruns |
| Verify checksum or signature before extracting | Tampering during transit is the threat model |
| Log to a file by default; summarize on stdout | `set -x` output is overwhelming and may include tokens in URLs |

## Real installers worth reading

Read these in order. Each is short and battle-tested. Reading the script source is more useful than reading any documentation about it.

- **deno install.sh** — https://github.com/denoland/deno_install/blob/main/install.sh — the smallest serious installer. arch detection, version pinning, GitHub release fetching. Read first. Under 100 lines.
- **bun install** — https://bun.sh/install (script source: https://github.com/oven-sh/bun/blob/main/src/cli/install.sh) — clean output, shell rc detection, GitHub releases. Roughly 200 lines.
- **rustup-init.sh** — https://github.com/rust-lang/rustup/blob/master/rustup-init.sh — gold standard for OS/arch/libc detection, `--default-toolchain` flag passthrough, the `bash -s -- --no-modify-path` convention. Read this before designing your flag set. Roughly 700 lines.
- **ollama install.sh** — https://ollama.com/install.sh (source: https://github.com/ollama/ollama/blob/main/scripts/install.sh) — multi-step install, GPU detection, systemd service registration, Docker fallback. Closest reference for the multi-service / system-bootstrap case.
- **fly.io install** — https://fly.io/install.sh — clean prompts, prints `flyctl auth login` as the next step rather than running it. Good model for the "print the next command" convention.
- **supabase install.sh** — wraps Docker Compose; demonstrates the "install.sh as Docker bootstrap" pattern for the multi-service case. The script's job is to install Docker if needed, clone, generate `.env`, and `docker compose up`. That's the whole job.
- **coolify install.sh** — `curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash` — the most ambitious installer in this list. Full multi-service, Docker bootstrap, env generation, reverse proxy setup. Useful as a study in failure modes; not a model to copy uncritically. Coolify has full-time maintainers for this.

## Known failure modes

- **The script is downloaded but not piped.** Some users `curl > install.sh; bash install.sh`. The script must work in both modes. Don't depend on `tty` for input — provide flags.
- **Re-running on a different version's working tree.** If the previous install left files in non-default locations, the new install won't find them. Document the upgrade path. Many tools recommend `<tool> self update` rather than re-running the installer.
- **Shell rc detection misses fish/nushell.** bash and zsh are easy. fish needs `set -gx PATH …` syntax. Either support them explicitly or print manual instructions and skip rc modification.
- **Corporate proxies.** `curl -fsSL` honors `HTTPS_PROXY` but custom CAs need `CURL_CA_BUNDLE` or `--cacert`. Add a clear error message when curl fails with a TLS error — don't let users guess.
- **The script gets cached by a CDN.** Set `Cache-Control: no-store` on the script if hosting yourself. Versioned URLs help.
- **A subcommand the script invokes prompts on stdin.** stdin is the curl pipe, not the user. Auth flows that need a paste-in token must be invoked AFTER the install completes, by the user, not from inside the script.
- **`set -e` does not catch errors in pipelines unless `pipefail` is set.** Without `set -o pipefail`, `false | true` succeeds. Common silent footgun.
- **Trapping signals doesn't help if you've already partially modified the user's shell rc.** Make rc modifications late, write a backup first.
- **`tar` flags differ between BSD tar (macOS) and GNU tar.** `tar --strip-components` works on both; `tar --transform` is GNU-only.
- **`uname -m` returns different strings on the same arch.** `aarch64` on Linux, `arm64` on macOS. Normalize before matching.

## Multi-service projects: the hard truth

A `curl | bash` installer for a multi-service project (Postgres + a backend + a frontend + a worker) is almost always a thin wrapper over Docker Compose. The honest answer for that case is to ship a `docker-compose.yml` and document `docker compose up -d`. The install script's only real jobs are:

1. Install Docker if missing (refuse if it can't be installed cleanly)
2. `git clone` the repo or fetch a release tarball
3. Generate an `.env` file from a template
4. Run `docker compose up -d`
5. Print the URL to visit

That's the whole job. Anything more elaborate becomes maintenance debt.

If you are not using Docker for a multi-service install, you are accepting responsibility for cross-platform service management — systemd, launchd, Windows services, fish vs zsh, glibc vs musl, GPU detection. This is a real, ongoing cost. Coolify and Plausible have full-time maintainers for installers at this scope. Most projects do not.

## Cross-references

- **`cli-packaging-patterns`** — Use that skill if your tool is a pure Python CLI. `uv tool install` is the right answer for that case; this skill is unnecessary overhead.
- **`container-orchestration-patterns`** — Use that skill if your installer is really wrapping a Docker Compose stack. The compose file is the install spec; the installer is just a Docker bootstrap.
- **`http-service-patterns`** and **`auth-tls-patterns`** — For the post-install configuration step. The installer should not implement auth or TLS bootstrap itself; it should hand off to a `<tool> login` or `<tool> configure` subcommand that those skills cover.
- **`config-state-patterns`** — For where to store the config the user creates after install (config vs state vs secrets locations).

## Final note

A curl-piped installer is the right answer for a narrow set of cases: cross-language, system-bootstrapping, non-technical audience, multi-service Docker stacks. For everything else, one of `uv tool install`, `npx`, a Docker Compose file, or a static binary download is simpler, safer, and more maintainable.

Position: write an `install.sh` only after you have ruled out those four alternatives, and only after you have read the deno installer end to end. The community convention is consistent enough that deviations from it should be deliberate, not accidental.
