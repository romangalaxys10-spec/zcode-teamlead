#!/usr/bin/env python3
"""Patch ZCode bot runtime: re-enable GROUP CHATS (supervisor-compatible).
Lost in the v3.14.3 app update; reimplemented for the repack patch line.
- telegram actor: in groups, providerUserId = chat id (replies land in the group)
- findAuthorizedBot/findBoundUser: group members match the bot by botId
  (binding stays strict in private chats)
- Bt(): drop the privateChatOnly wall
- splitCommand: strip Telegram's @BotName suffix from commands in groups
Security: anyone in the group can drive the bot (it executes on this machine) —
keep groups to trusted people. Idempotent; asserts anchors before patching."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"

REPLACEMENTS = [
    (
        # Yae readTelegramPrivateMessage: route group replies to the group chat
        'actor:{provider:"telegram",botId:e,providerUserId:a,',
        'actor:{provider:"telegram",botId:e,providerUserId:c==="group"&&r&&(typeof r.id=="number"||typeof r.id=="string")?String(r.id):a,',
    ),
    (
        # findAuthorizedBot: in groups, match the bot by botId (not just bound owner id)
        'e.bots.find(n=>n.enabled&&n.provider===t.provider&&n.providerUserId===t.providerUserId)??null',
        'e.bots.find(n=>n.enabled&&n.provider===t.provider&&(n.providerUserId===t.providerUserId||t.chatType!=="private"&&n.id===t.botId))??null',
    ),
    (
        # findBoundUser: group members act as the bound user (owner permissions apply)
        'function WZ(e,t){return t.provider==="weixin"||e.providerUserId===t.providerUserId?e:null}',
        'function WZ(e,t){return t.provider==="weixin"||t.chatType!=="private"||e.providerUserId===t.providerUserId?e:null}',
    ),
    (
        # Bt withAuthorizedContext: remove the group refusal
        'if(h.actor.chatType!=="private")return{ok:!1,reply:[me(h.actor,ne(I,"privateChatOnly"))]};',
        '',
    ),
    (
        # splitCommand: strip @BotName suffix from command names (Telegram groups)
        'let n=t.slice(1),r=n.search(/\\s/u);return r===-1?{name:n.toLowerCase(),rest:""}:{name:n.slice(0,r).toLowerCase(),rest:n.slice(r+1).trim()}',
        'let n=t.slice(1),r=n.search(/\\s/u);let zg_c=r===-1?n:n.slice(0,r);let zg_i=zg_c.indexOf("@");if(zg_i!==-1)zg_c=zg_c.slice(0,zg_i);return r===-1?{name:zg_c.toLowerCase(),rest:""}:{name:zg_c.toLowerCase(),rest:n.slice(r+1).trim()}',
    ),
]


def main():
    src = open(HOST, errors="ignore").read()
    if "ZCODE_GROUPS_V1" in src:
        print("host: groups already patched")
        return 0
    for i, (old, new) in enumerate(REPLACEMENTS, 1):
        n = src.count(old)
        assert n == 1, f"anchor {i} count={n} (expected 1): {old[:70]}"
        src = src.replace(old, new, 1)
        print(f"OK replacement {i}")
    src = src.replace("var ZCODE_SUPERVISOR_V1=1;", "var ZCODE_SUPERVISOR_V1=1;var ZCODE_GROUPS_V1=1;", 1)
    open(HOST, "w").write(src)
    print("groups patch applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
