# Bot group-chat patches (unofficial app mods)

⚠️ **Unofficial, use at your own risk.** These are in-place patches to the ZCode
desktop app bundle (`Resources/app.asar`) — not a plugin. Not affiliated with
the ZCode project.

## What you get

**Telegram group chats (default)** — by default ZCode bots refuse groups. After
patching:

- the bot answers in group chats (DMs keep working unchanged)
- **every group member** can drive the group's bot — no per-user binding needed,
  so your friends can code with it too
- `/bind` in a group answers "No bind needed here." instead of a refusal
  (binding stays private-only on purpose: pairing codes must never leak in groups)
- slash commands with Telegram's `@botname` suffix parse correctly
  (in groups, Telegram sends `/new@yourbot`; that used to be an unknown command)

**Discord upgrades (`--discord`)** — if your bundle carries the community Discord
adapter, this also upgrades it to reply as rich embeds, register native slash
commands, handle interactions with ephemeral acks, filter its own echo, add a
token input to the bot settings dialog, and let numbered replies select options.

## Quick start

```bash
# 1. quit ZCode completely (the patch targets files on disk; bots runtime loads at launch)
# 2. patch
python3 app-patches/patch-zcode-bots.py            # telegram groups
python3 app-patches/patch-zcode-bots.py --discord  # + discord upgrades
# 3. reopen ZCode
```

Linux users: pass the bundle path explicitly, e.g.
`python3 app-patches/patch-zcode-bots.py --app ~/.config/ZCode/app.asar`

## Safety model

- **Equal-length in-place edits only** — the asar header is never touched, which
  is exactly what macOS validates (`ElectronAsarIntegrity`), so the app keeps
  launching normally
- A backup is written before the first change
- After writing, every patched bundle is extracted and syntax-checked
- Fully idempotent — safe to re-run

## Rollback

```bash
python3 app-patches/patch-zcode-bots.py --restore
```

## Version compatibility

The patches are **byte-exact against macOS ZCode 3.14.3.7762**. On a different
version the minified code may differ; the script detects this and aborts loudly
instead of corrupting anything (it will print which snippet didn't match).
App auto-updates replace `app.asar` and revert the patches — just re-run the
script after an update.

## Group usage tips

- Telegram group **privacy mode** (BotFather → /mybots → Bot Settings → Group
  Privacy) controls delivery: ON (default) = the bot sees only commands,
  @mentions and replies; turn it OFF and re-add the bot if you want it to
  answer every message
- any group member can drive the bot once it's in the group — keep groups to
  people you trust (the bot executes on your machine)
