#!/usr/bin/env python3
"""
patch-zcode-bots.py — unofficial app-bundle patches that unlock bot group-chat
features in the ZCode desktop app.

UNOFFICIAL, USE AT YOUR OWN RISK. Not affiliated with the ZCode project.
Modifies Resources/app.asar INSIDE the installed app. The patches are
byte-exact against macOS ZCode 3.14.3.7762; on other versions the script
aborts loudly instead of guessing.

What you get:
  (default) Telegram group-chat support:
    - bots answer in group chats (they previously refused: "Bots do not
      support group chats yet")
    - every group member can drive the group's bot (no per-user binding)
    - /bind in a group replies "No bind needed here." instead of a refusal
    - commands with Telegram's "@botname" suffix parse correctly
      ("/new@yourbot" used to be an unknown command)
  (--discord) Discord upgrades:
    - replies as rich embeds with smart line-boundary chunking
    - native slash commands (/new /status /workspace /model /stop /help)
      registered on connect, with an ephemeral ack for interactions
    - bot self-echo filter (no feedback loops)
    - bot-settings dialog gains a Discord token input
    - numbered replies to selection pickers select an option

Safety model:
  - all patches are EQUAL-LENGTH in-place byte edits: the asar header is never
    touched, which is what macOS validates (Info.plist ElectronAsarIntegrity)
  - a backup is written next to the original before any change
  - after patching, the modified bundle is extracted and syntax-checked
  - every patch is idempotent (safe to re-run after app updates)

Usage:
  python3 patch-zcode-bots.py                 # telegram group support
  python3 patch-zcode-bots.py --discord       # + discord upgrades
  python3 patch-zcode-bots.py --restore       # roll back from the backup
  python3 patch-zcode-bots.py --app <path>    # custom app.asar path

After patching: fully quit ZCode and reopen (the bots runtime lives in a
long-lived host process; closing the window is not enough).
"""
import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time

DEFAULT_ASAR = "/Applications/ZCode.app/Contents/Resources/app.asar"
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- telegram groups

S1 = b'if(h.actor.chatType!=="private")return{ok:!1,reply:[me(h.actor,ne(I,"privateChatOnly"))]};'
R1 = b'if(h.actor.chatType!=="private");/*tl-patch: group chats allowed*/'
M1 = [b"tl-patch: group chats allowed", b"xs-patch: group chats allowed"]

REGION2 = (
    b'function zZ(e,t){return t.provider==="weixin"?e.bots.find(n=>n.enabled&&n.provider==="weixin"&&n.id===t.botId)??null:'
    b'e.bots.find(n=>n.enabled&&n.provider===t.provider&&n.providerUserId===t.providerUserId)??null}'
    b'i(zZ,"findAuthorizedBot");'
    b'function WZ(e,t){return t.provider==="weixin"||e.providerUserId===t.providerUserId?e:null}'
    b'i(WZ,"findBoundUser");'
)
NEW2 = (
    b'function zZ(e,t){return t.provider==="weixin"?e.bots.find(n=>n.enabled&&n.provider==="weixin"&&n.id===t.botId):'
    b'e.bots.find(n=>n.enabled&&n.provider===t.provider&&(n.providerUserId===t.providerUserId||t.chatType<"p"&&n.id===t.botId))||null}'
    b'function WZ(e,t){return t.provider==="weixin"||t.chatType<"p"||e.providerUserId===t.providerUserId?e:null}'
)
M2 = b't.chatType<"p"&&n.id===t.botId'

S3 = b'if(h.actor.chatType!=="private")return[me(h.actor,ne(I,"bindPrivateOnly"))];'
R3 = b'if(h.actor.chatType!=="private")return[me(h.actor,"No bind needed here.")]; '
M3 = b"No bind needed here."

S4 = (
    b'function Hae(e){let t=e.trim();if(!t.startsWith("/"))return null;'
    b"let n=t.slice(1),r=n.search(/\\s/u);let a=n.split(\"@\")[0].toLowerCase();"
    b'return{name:a,rest:r===-1?"":n.slice(r+1).trim()}}i(Hae,"splitCommand");'
)
R4 = (
    b'function Hae(e){let t=e.trim();if(!t.startsWith("/"))return null;'
    b"let[n,...c]=t.slice(1).split(/\\s/);"
    b'return{name:n.split("@")[0].toLowerCase(),rest:c.join(" ").trim()}}'
    b'i(Hae,"splitCommand");'
)
M4 = b'n.split("@")[0].toLowerCase(),rest:c.join'

# ---------------------------------------------------------------- discord (optional)

D_START = b"function ZCODE_discordAdapter(zc){"
D_END = b"function up(e){let t=e.runStartupBackgroundTasks"
M5 = b"INTERACTION_CREATE"
M6 = b'h.provider==="telegram"||!Ale(P)'
S6 = b'if(h.provider!=="weixin"||!Ale(P))return xe(h),null;'
R6 = b'if(h.provider==="telegram"||!Ale(P))return xe(h);'

R_LOGS = [
    ("[BotsDialog] 生成 Telegram BotFather 二维码失败", "[BotsDialog] botfather qr"),
    ("[BotsDialog] 轮询 Bot 绑定结果失败", "[BotsDialog] bind poll"),
    ("[BotsDialog] 刷新 Bot 运行状态失败", "[BotsDialog] refresh"),
    ("[BotsDialog] 加载 Bots 配置失败", "[BotsDialog] load"),
    ("[BotsDialog] 轮询微信 Bot 激活状态失败", "[BotsDialog] wx poll"),
    ("[BotsDialog] 飞书扫码注册轮询失败", "[BotsDialog] fs poll"),
    ("[BotsDialog] 微信扫码登录轮询失败", "[BotsDialog] wx login"),
    ("[BotsDialog] 保存工作区访问范围失败", "[BotsDialog] save ws"),
    ("[BotsDialog] 创建 Bot 失败", "[BotsDialog] create"),
    ("[BotsDialog] 保存 Bot secret 失败", "[BotsDialog] save secret"),
    ("[BotsDialog] 生成飞书注册二维码失败", "[BotsDialog] fs qr"),
    ("[BotsDialog] 启动飞书扫码注册失败", "[BotsDialog] fs start"),
    ("[BotsDialog] 生成微信登录二维码失败", "[BotsDialog] wx qr"),
    ("[BotsDialog] 启动微信扫码登录失败", "[BotsDialog] wx start"),
    ("[BotsDialog] 复制绑定命令失败", "[BotsDialog] copy"),
    ("[BotsDialog] 移除 Bot secret 失败", "[BotsDialog] remove"),
    ("[BotsDialog] 删除 Bot 失败", "[BotsDialog] delete"),
    ("[App] 查产物出处失败，退回产物 tab", "[App] artifact lookup failed"),
    ("[App] 关闭框选副屏 runtime 失败", "[App] close selection runtime failed"),
    ("[App] 激活 suspended Browser tab 失败", "[App] activate suspended tab failed"),
    ("[App] 关闭 Browser tab 时缺少 main authority", "[App] missing main authority"),
    ("[App] 关闭 Browser tab 的 main authority 失败", "[App] close tab authority failed"),
    ("[GitAutoRefresh] 监听 Git 工作区失败", "[GitAutoRefresh] watch failed"),
]
R_B1 = (
    "else if(e.provider===`discord`&&!C)M=(0,$.jsxs)(`div`,{className:`flex gap-2`,"
    "children:[(0,$.jsx)(Yo,{type:`password`,value:n,onChange:e=>p(e.target.value),className:`min-w-0 flex-1`,disabled:f}),"
    "(0,$.jsxs)(X,{onClick:m,disabled:f||!n.trim(),"
    "children:[f?(0,$.jsx)(Ec,{className:`size-4 animate-spin`}):null,S.formatMessage({id:`bots.saveSecret`})]})]});"
)
M7 = b"e.provider===`discord`&&!C"


def asar_header(asar_path):
    f = open(asar_path, "rb")
    f.seek(4)
    pickle_size = struct.unpack("<I", f.read(4))[0]
    f.seek(8)
    f.read(4)
    f.seek(12)
    hsz2 = struct.unpack("<I", f.read(4))[0]
    hdr = json.loads(f.read(hsz2))
    f.close()
    return hsz2, 8 + pickle_size, hdr  # header size, data base, header dict


def find_file(hdr, rel):
    def walk(node, path):
        if "files" in node:
            for name, ch in node["files"].items():
                r = walk(ch, path + [name])
                if r is not None:
                    return r
        if "size" in node and "/".join(path) == rel:
            return node
        return None

    return walk(hdr, [])


def pad_to(repl, orig):
    assert len(repl) <= len(orig), f"replacement {len(repl)} > original {len(orig)} - snippet too long"
    return repl + b" " * (len(orig) - len(repl))


def apply_snippet(data, s, r, markers, label):
    if isinstance(markers, bytes):
        markers = [markers]
    if any(bytes(data).find(m) != -1 for m in markers):
        print(f"  {label}: already present, skipping")
        return False
    n = bytes(data).count(s)
    if n != 1:
        sys.exit(f"  {label}: target snippet count={n} (expected 1). "
                 "Your ZCode version differs from the tested one - patches must be re-derived, aborting.")
    i = data.find(s)
    data[i:i + len(s)] = pad_to(r, s)
    print(f"  {label}: applied @ {i}")
    return True



# ---------------------------------------------------------------- patch 8: mid-task ack + auto-requeue

S8 = ('if(P.context.mode==="task"&&P.context.activeTaskId&&await mo(P.context))'
      'return[me(h.actor,ne(P.locale,"taskRunning"))];')
R8 = ('if(P.context.mode==="task"&&P.context.activeTaskId&&await mo(P.context)){let q=h.rq||0;'
      'if(q<30)setTimeout(()=>G4({...h,rq:q+1}).catch(()=>{}),6e4);'
      'return[me(h.actor,q?"\\ud83d\\udce5 Still on it \\u2014 the full report (incl. this) lands once the current task wraps.":'
      '"\\ud83d\\udce5 Queued \\u2014 full report (incl. this) once the current task wraps.")]}'
      'return[me(h.actor,ne(P.locale,"taskRunning"))];')
D1 = 'modelSelection:{providerId:Je.providerId,modelId:Je.modelId,...Je.options?{options:{...Je.options}}:{}}'
N1 = 'modelSelection:{...Je}'
D2 = ('Ut.info(void 0,`replaced deleted Bot task bot=${P.bot.id} oldTask=${I} newTask=${Ue.taskId} '
      'workspace=${Kn(We.workspacePath,We.workspaceIdentity)}`),await en(P.bot,me(h.actor,ne(P.locale,'
      '"deletedTaskReplaced"))).catch(At=>{Ut.warn(void 0,`deleted task replacement notice failed bot=${P.bot.id} '
      'task=${Ue.taskId}: ${At instanceof Error?At.message:String(At)}`)})')
N2 = ('Ut.info(void 0,`replaced ${I} -> ${Ue.taskId}`),'
      'await en(P.bot,me(h.actor,ne(P.locale,"deletedTaskReplaced"))).catch(()=>{})')
D3 = 'throw new Error("Bot \\u65E0\\u6CD5\\u4ECE\\u76EE\\u6807 Host \\u89E3\\u6790 Submission \\u6A21\\u578B")'
N3 = 'throw Error("model selection unavailable")'
M8 = b"rq:q+1"


def apply_patch8(data):
    if bytes(data).find(M8) != -1:
        print("  mid-task ack+requeue: already present, skipping")
        return
    s8, d1, d2, d3 = S8.encode(), D1.encode(), D2.encode(), D3.encode()
    for name, s in [("gate", s8), ("donor1", d1), ("donor2", d2), ("donor3", d3)]:
        if bytes(data).count(s) != 1:
            sys.exit(f"  patch 8 {name}: snippet count={bytes(data).count(s)} - version differs, aborting")
    i8, i1 = data.find(s8), data.find(d1)
    i2, i3 = data.find(d2), data.find(d3)
    start, end = min(i8, i1, i2, i3), max(i1 + len(d1), i2 + len(d2), i3 + len(d3))
    span = bytes(data[start:end]).decode("utf-8")
    new_span = span.replace(s8.decode(), R8).replace(d1.decode(), N1).replace(d2.decode(), N2).replace(d3.decode(), N3)
    if len(new_span.encode()) > len(span.encode()):
        sys.exit(f"  patch 8: over budget by {len(new_span.encode()) - len(span.encode())} bytes")
    new_span += " " * (len(span.encode()) - len(new_span.encode()))
    data[start:end] = new_span.encode()
    print(f"  mid-task ack+requeue: applied @ {start}")


def verify_bundle(asar_path, rel, markers):
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(
            ["npx", "--yes", "@electron/asar", "extract-file", asar_path, rel],
            cwd=td, check=True, capture_output=True,
        )
        blob = open(os.path.join(td, os.path.basename(rel)), "rb").read()
        for m in markers:
            if m not in blob:
                sys.exit(f"VERIFY FAILED: {m!r} missing from extracted {rel}")
        subprocess.run(["node", "--check", os.path.join(td, os.path.basename(rel))], check=True)


def main():
    ap = argparse.ArgumentParser(description="Unofficial ZCode bot group-chat / discord app patches")
    ap.add_argument("--app", default=os.environ.get("ZCODE_APP", DEFAULT_ASAR), help="path to app.asar")
    ap.add_argument("--discord", action="store_true", help="also apply the discord upgrades")
    ap.add_argument("--restore", action="store_true", help="roll back from the backup")
    args = ap.parse_args()
    asar = args.app

    if args.restore:
        bak = asar + ".bak-teamlead"
        if not os.path.exists(bak):
            sys.exit(f"no backup at {bak}")
        shutil.copy2(bak, asar)
        print(f"restored {asar} from {bak}. Restart ZCode.")
        return

    if not os.path.exists(asar):
        sys.exit(f"app.asar not found at {asar} (override with --app or ZCODE_APP)")

    data = bytearray(open(asar, "rb").read())
    orig_len = len(data)
    hsz2, base, hdr = asar_header(asar)
    header_before = bytes(data[12:12 + hsz2])

    print(f"[*] target: {asar}")
    print("[*] telegram group-chat patches")
    apply_snippet(data, S1, R1, M1, "1/4 group gate")
    apply_snippet(data, REGION2, NEW2, M2, "2/4 group binding")
    apply_snippet(data, S3, R3, M3, "3/4 bind reply")
    apply_snippet(data, S4, R4, M4, "4/4 @suffix parse")
    print("[*] mid-task ack + auto-requeue")
    apply_patch8(data)

    if args.discord:
        print("[*] discord upgrades")
        dfile = os.path.join(HERE, "discord-adapter-v2.js")
        if not os.path.exists(dfile):
            sys.exit(f"discord adapter source missing: {dfile}")
        if bytes(data).find(M5) != -1:
            print("  5/6 discord layer: already present, skipping")
        else:
            i1 = bytes(data).find(D_START)
            i2 = bytes(data).find(D_END, i1)
            if i1 == -1 or i2 == -1:
                sys.exit("  5/6: ZCODE_discordAdapter region not found - this machine "
                         "never had the discord injection; only the adapter layer can be patched on machines that have it")
            region = bytes(data[i1:i2])
            new_d = open(dfile, "rb").read()
            if len(new_d) > len(region):
                sys.exit(f"  5/6: replacement {len(new_d)} > region {len(region)}")
            data[i1:i1 + len(region)] = new_d + b" " * (len(region) - len(new_d))
            print(f"  5/6 discord layer: applied @ {i1}")
        if bytes(data).find(M6) != -1:
            print("  6/6 selection gate: already present, skipping")
        else:
            n = bytes(data).count(S6)
            if n != 1:
                sys.exit(f"  6/6: gate snippet count={n}, aborting")
            i6 = data.find(S6)
            data[i6:i6 + len(S6)] = pad_to(R6, S6)
            print(f"  6/6 selection gate: applied @ {i6}")

        node = find_file(hdr, "out/renderer/assets/styles-DEELZGp2.js")
        if node is None:
            sys.exit("  renderer asset not found in asar header")
        roff, rsize = base + int(node["offset"]), node["size"]
        region = bytes(data[roff:roff + rsize])
        if region.find(M7) != -1:
            print("  renderer token input: already present, skipping")
        else:
            src = region.decode("utf-8")
            saved = 0
            for old, new in R_LOGS:
                if old not in src:
                    sys.exit(f"  renderer: donor log string missing ({old[:30]}) - version differs, aborting")
                saved += len(old.encode()) - len(new.encode())
                src = src.replace(old, new)
            anchor = ("else M=(0,$.jsxs)(`div`,{className:`flex w-full flex-wrap justify-end gap-2`,"
                      "children:[!j&&!D?")
            if src.count(anchor) != 1:
                sys.exit("  renderer: settings-chain anchor missing - version differs, aborting")
            src = src.replace(
                anchor,
                R_B1 + "else if(e.provider!==`discord`||C)M=(0,$.jsxs)(`div`,"
                       "{className:`flex w-full flex-wrap justify-end gap-2`,children:[!j&&!D?",
            )
            newb = src.encode()
            if len(newb) > rsize:
                sys.exit(f"  renderer: grew {len(newb) - rsize} bytes - trim donors")
            data[roff:roff + rsize] = newb + b" " * (rsize - len(newb))
            print(f"  renderer token input: applied @ {roff}")

    if bytes(data) == open(asar, "rb").read():
        print("nothing to do - all patches already present")
        return

    assert len(data) == orig_len, "size changed!"
    assert bytes(data[12:12 + hsz2]) == header_before, "header changed!"
    bak = asar + ".bak-teamlead"
    if not os.path.exists(bak):
        shutil.copy2(asar, bak)
        print(f"[*] backup written: {bak}")
    open(asar, "wb").write(bytes(data))
    print(f"[*] written OK ({orig_len} bytes, header untouched)")

    print("[*] verifying (extract + syntax check)...")
    verify_bundle(asar, "out/host/index.js", [M1, M2, M3, M4, M8])
    if args.discord:
        verify_bundle(asar, "out/renderer/assets/styles-DEELZGp2.js", [M7])
    print("VERIFY OK. Fully quit ZCode (Cmd+Q) and reopen to load the patched runtime.")
    print(f"Roll back any time: python3 {os.path.abspath(__file__)} --restore")


if __name__ == "__main__":
    main()
