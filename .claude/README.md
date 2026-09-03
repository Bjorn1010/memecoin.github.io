# Claude Code setup for this repo

Two things are wired up here: the **UI/UX Pro Max** skill (vendored, works out of the
box) and the **Magic MCP** server from 21st.dev (needs an API key from you).

## 1. UI/UX Pro Max skill

Installed at `.claude/skills/ui-ux-pro-max/` — vendored from
[nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
v2.13.0, which is what `npx ui-ux-pro-max-cli init --ai claude` writes.

It is a project skill, so it loads automatically for anyone working in this repo — no
per-machine install step. Claude picks it up when a task involves UI structure, visual
design, interaction patterns, or UX review. Relevant here for the `mayhem-bot/web`
dashboard (React + Tailwind + Recharts).

The skill is offline: a Python 3 stdlib search over local CSV/JSON data. No network
calls, no installs.

```bash
cd .claude/skills/ui-ux-pro-max

# search a domain
python3 scripts/search.py "trading dashboard" --domain style -n 3
python3 scripts/search.py "crypto" --domain color

# stack-specific guidance
python3 scripts/search.py "data table" --stack react

# generate a full design system
python3 scripts/search.py "memecoin paper-trading dashboard" \
  --design-system --project-name "Mayhem Bot"
```

Domains: `style`, `color`, `chart`, `landing`, `product`, `ux`, `typography`, `icons`,
`gsap`, `react`, `web`, `google-fonts`.

### Updating

Re-vendor from upstream when you want a newer version:

```bash
npx ui-ux-pro-max-cli@latest init --ai claude
```

Run it from the repo root — it writes to `.claude/skills/ui-ux-pro-max/`, the same path,
so the update lands as a reviewable diff.

## 2. 21st.dev MCP (Magic)

Generates UI components from natural language and pulls from the 21st.dev component
library. There is deliberately **no `.mcp.json` in this repo** — the server is
registered per-developer so the API key never goes near version control.

Register it once on your own machine, from the repo root:

```bash
claude mcp add --transport http 21st https://21st.dev/api/mcp \
  --header "x-api-key: YOUR_21ST_API_KEY"
```

That writes to `~/.claude.json`, outside the repo. Get a key at <https://21st.dev/mcp>;
keys issued for the old `@21st-dev/magic` npm server were reset upstream, so an old one
will not work.

Verify with `claude mcp list` or `/mcp` — `21st` should report `Connected`.

### Do not commit the key

Never paste the key into `.mcp.json`, `.env`, or any other file inside this repo. If a
key is ever exposed — pasted into a chat, a screenshot, a log, a commit — revoke it at
<https://21st.dev/mcp> and issue a new one. Rotating is free; a leaked key is not.

An alternative is a committed `.mcp.json` that reads `${TWENTY_FIRST_API_KEY}` from the
environment, which shares the server definition across a team without sharing the
secret. That is worth adding if more people start working on this repo; for a single
developer the `claude mcp add` route above is simpler and has one less moving part.
