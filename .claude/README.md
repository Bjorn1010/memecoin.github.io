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

## 2. 21st.dev — plugin (MCP + skills)

Finds, generates and reviews UI against the 21st.dev component library. Installed as
the **plugin**, not as a bare MCP server, because the plugin bundles seven skills
(`21st-ui-build`, `21st-ui-explore`, `21st-ui-review`, `21st-registry`, `21st-ai`,
`21st-cli-use`, `21st-design-sync`) alongside the same remote server. Cost is about
1.5k tokens always-on.

There is deliberately **no `.mcp.json` in this repo**: the plugin ships its own, and the
key comes from the environment so it never goes near version control.

```bash
# once per machine
claude plugin marketplace add 21st-dev/claude-code-plugin
claude plugin install 21st@21st
```

Then supply the key. Put it in `~/.claude/settings.json` (user scope, outside any repo,
never committed):

```json
{
  "env": { "API_KEY_21ST": "your-key-here" }
}
```

Prefer this over `export API_KEY_21ST=…` in a shell profile. `~/.bashrc` returns early
for non-interactive shells, so the variable is missing exactly when a tool launches
Claude Code for you and the server reports `Needs authentication` even though the
profile "has" it. The `env` block is read regardless of how the process was started.

The variable name matters. The plugin's `.mcp.json` reads `${API_KEY_21ST}`
specifically — not `TWENTY_FIRST_API_KEY`, which the older standalone setup used. With
it unset the server installs fine and then reports `Needs authentication`, which looks
like a broken install but is only a missing variable.

Get a key at <https://21st.dev/mcp>. Keys issued for the old `@21st-dev/magic` npm
server were reset upstream, so an old one will not work.

Verify with `claude mcp list` — `plugin:21st:21st` should report `Connected`.

### Do not register it twice

`claude mcp add --transport http 21st …` also works, but it stores the key literally in
`~/.claude.json` and is scoped to the directory you ran it in, so it reports `Connected`
inside this repo and `Needs authentication` anywhere else. Running both leaves two
servers pointed at the same endpoint. Pick the plugin and the environment variable.

### Do not commit the key

Never paste it into `.mcp.json`, `.env`, or any file inside this repo. If a key is ever
exposed — pasted into a chat, a screenshot, a log, a commit — revoke it at
<https://21st.dev/mcp> and issue a new one. Rotating is free; a leaked key is not.

### MCP tools load at session start

A server registered mid-session shows as connected but its tools are not exposed until
the next session. Skills from the plugin behave the same way. If `21st` tools are not
available right after installing, that is expected — restart Claude Code.
