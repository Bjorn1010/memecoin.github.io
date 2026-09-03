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

## 2. Magic MCP (21st.dev)

Configured in `.mcp.json` at the repo root. It generates UI components from natural
language and pulls from the 21st.dev component library.

The config reads the key from the environment, so **no secret is committed**:

```json
{
  "mcpServers": {
    "magic": {
      "type": "http",
      "url": "https://21st.dev/api/mcp",
      "headers": { "x-api-key": "${TWENTY_FIRST_API_KEY}" }
    }
  }
}
```

### To activate it

1. Get an API key at <https://21st.dev/mcp>. Keys issued for the old `@21st-dev/magic`
   server were reset — generate a fresh one.
2. Export it in the shell you launch Claude Code from:

   ```bash
   export TWENTY_FIRST_API_KEY="your-key-here"
   ```

   Put it in your shell profile (`~/.zshrc`, `~/.bashrc`) to make it stick. Do not put
   it in a file inside this repo.
3. Restart Claude Code. Approve the project MCP server when prompted (project-scoped
   servers from `.mcp.json` need a one-time approval per machine).
4. Verify with `/mcp` — `magic` should show as connected.

Until the key is set the server will fail to connect. That is expected and harmless;
everything else in the repo works without it.

Note: unlike the skill, this one is per-developer. `.mcp.json` is committed so the
server definition is shared, but each person supplies their own key.
