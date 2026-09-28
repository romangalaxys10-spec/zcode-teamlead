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
- **mid-task messages get queued, not bounced**: send a message while the bot is
  busy and it ACKs ("📥 Queued — full report once the current task wraps"), keeps
  retrying in the background (up to ~30 min), and when the running task finishes
  your message is processed and you receive one complete report including it

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

---

## Supervisor mode + native Discord adapter (2026-09-26, `patch-supervisor.py` / `patch-discord-native.py`)

Two additional patches from a second patch line. **Different mechanism than
`patch-zcode-bots.py`**: these do a full asar **repack** (extract → patch →
repack with verified unpacked-set, list parity, sha256 spot-checks) instead of
equal-length in-place edits. Both approaches work; do NOT stack them on the
same guard — they touch overlapping anchors.

### `patch-supervisor.py` — nano-supervisor mode (Telegram/Discord bots)

Turns the bot from a doorman into a dispatcher:

- **never refuses** — a message while a task runs spawns a **fresh parallel
  session** and submits there (ACKs: "🧵 New parallel task started"), instead of
  the "task is still running" bounce
- **real-time updates per task** via the native streaming reply mode
- **/tasks can switch focus while tasks run** (busy guard removed)
- **/new works while busy** (busy guard removed)
- `/stop` stops only the *focused* (newest) task; `/tasks` first to focus an
  older one. FIFO submission order = priority; stop+resubmit to jump the queue.

Key insight: the one-task-per-bot rule was an artificial per-bot guard — the
agent engine runs sessions fully in parallel.

### `patch-discord-native.py` — fills the app's reserved `discord:null` slot

The app ships a Discord entry in the bot-provider picker flagged
`implemented:!1` and a literal `discord:null` in the adapter registry. This
patch adds the missing first-class adapter:

- full provider interface (test / resolveName / send with 1900-char chunking /
  sendTyping / parseCallback) over Discord REST v10
- **Gateway WebSocket runtime** (identify, heartbeat, reconnect backoff,
  intents 34304) with an 8s reconcile tick mirroring the telegram/feishu
  channel runtimes — DMs always answered, guild messages on @mention
- renderer: Discord flipped to implemented + i18n token hints (zh+en)

You bring the bot: discord.com/developers → New Application → Bot → Reset
Token → enable **Message Content Intent** → invite (scopes=bot; Send Messages +
Read Message History) → ZCode Bots → new bot → Discord → paste token.

### Verify tools

- `asar_unpacked_list.py <asar>` — list entries the header marks `unpacked`
- `asar_spotcheck.py <asar> <srcdir> [n]` — sha256-compare n random packed
  files against the source tree (repak verification)

### Relation to `patch-zcode-bots.py`

| | patch-zcode-bots.py | supervisor + discord-native |
|---|---|---|
| method | equal-length in-place edits (asar integrity untouched) | full extract→patch→repack |
| busy messages | ACK + queue, deliver after current task | spawn parallel task immediately |
| discord | upgrades a community adapter (rich embeds, slash commands) | creates the native adapter from `discord:null` |
| pick when | you want queued, serialized reports in groups | you want parallel workers + first-class Discord |

Run one OR the other per guard — not both. Both are idempotent and abort
loudly when anchors don't match your app version. Back up `app.asar` first.


### `patch-groups.py` — re-enable group chats (2026-09-28)

The v3.14.3 app update wiped the original group-chat patch (updates replace
`app.asar`). This re-implements groups for the repack patch line, supervisor-style:

- telegram actor: in groups `providerUserId` becomes the **chat id**, so replies
  land in the group instead of the sender's DM
- `findAuthorizedBot` / `findBoundUser`: group members match the bot by **botId**
  (owner permissions apply to everyone in the group) — private chats keep strict
  per-user binding
- the `privateChatOnly` refusal is removed
- commands with Telegram's `@BotName` suffix parse correctly

Telegram BotFather **Group Privacy** (ON by default) controls whether the bot
sees non-command group messages — turn it OFF and re-add the bot for full
supervisor behavior. With supervisor mode also installed, each group member's
message spawns its own parallel task; /stop only stops the focused one.
Known gap: inline-button presses (callback queries) from group members may
still resolve to the sender's private chat.
