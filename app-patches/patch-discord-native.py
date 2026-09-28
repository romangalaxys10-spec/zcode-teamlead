#!/usr/bin/env python3
"""Patch ZCode 3.14.3 host+renderer: enable the reserved Discord bot provider.
- Host: register a Discord adapter into F.discord + a Gateway-WebSocket channel
  runtime that mirrors the feishu/telegram channel runtimes.
- Renderer: flip Discord `implemented:!1` -> `!0` and add i18n token descriptions.
Idempotent: skips already-patched files."""
import sys

HOST = "/tmp/zcode-discord/app/out/host/index.js"
RENDERER = "/tmp/zcode-discord/app/out/renderer/assets/styles-DEELZGp2.js"
I18N = "/tmp/zcode-discord/app/out/renderer/assets/IntlProvider-BMWo3Clv.js"

ADAPTER = r'''function ZCODE_discordAdapter(zc){const API="https://discord.com/api/v10";async function tok(c){const t=await zc.loadCredential(c.credentialRef);return typeof t==="string"?t.trim():""}async function me(c){const t=await zc.loadCredential(c.credentialRef);if(typeof t!=="string"||!t.trim())return null;try{const r=await fetch(API+"/users/@me",{headers:{Authorization:"Bot "+t.trim()},signal:AbortSignal.timeout(8000)});return r.ok?await r.json():null}catch{return null}}return{async test(c){if(!c.enabled)return{ok:!1,message:"Discord bot is disabled."};if(!c.credentialRef)return{ok:!1,message:"Discord bot token is missing."};const u=await me(c);return u?{ok:!0,name:u.username,message:"Discord bot is reachable."}:{ok:!1,message:"Discord token rejected."}},async resolveName(c){const u=await me(c);return u&&u.username||null},async syncCommands(c){},async send(c,o){const t=await tok(c);if(!t)return;const target=o.providerUserId||o.providerContextToken;if(!target)return;const parts=String(o.text??"").match(/[\s\S]{1,1900}/g)||[];for(const p of parts){const r=await fetch(API+"/channels/"+target+"/messages",{method:"POST",headers:{"content-type":"application/json",Authorization:"Bot "+t},body:JSON.stringify({content:p})});if(!r.ok)throw new Error("Discord send failed: HTTP "+r.status)}},async sendTyping(c,o){const t=await tok(c);const target=o.providerUserId||o.providerContextToken;if(!t||!target)return;try{await fetch(API+"/channels/"+target+"/typing",{method:"POST",headers:{Authorization:"Bot "+t},signal:AbortSignal.timeout(5000)})}catch{}},async downloadAttachment(){return null},parseCallback(p){if(typeof p!=="object"||p===null)return[];const m=p.message;if(typeof m!=="object"||m===null)return[];const botId=typeof p.botId==="string"?p.botId:"";const uid=m.author&&typeof m.author.id==="string"?m.author.id:"";if(!botId||!uid)return[];let text=typeof m.content==="string"?m.content:"";const self=typeof p.selfUserId==="string"?p.selfUserId:"";if(self){text=text.split("<@"+self+">").join(" ").split("<@!"+self+">").join(" ")}text=text.trim();if(!text)return[];const chatId=m.channel_id!=null?String(m.channel_id):uid;return[{botId,text,actor:{provider:"discord",botId,providerUserId:chatId,displayName:m.author&&m.author.username||void 0,chatType:m.guild_id?"group":"private",chatId,providerMessageId:m.id!=null?String(m.id):void 0}}]}}}
async function ZCODE_dcRun(e,b,re,Yd,stop){let backoff=1000;while(!stop.stop){let hb=null;try{const tok=String(await e.credentialService.load(b.credentialRef)||"").trim();if(!tok){re.setRuntimeStatus({botId:b.id,provider:"discord",status:"error",message:"Discord bot token is missing."});return}const gr=await fetch("https://discord.com/api/v10/gateway/bot",{headers:{Authorization:"Bot "+tok},signal:AbortSignal.timeout(15000)});if(!gr.ok)throw new Error("gateway HTTP "+gr.status);const gurl=(await gr.json()).url;let seq=null,selfId=null;await new Promise((resolve,reject)=>{const ws=new WebSocket(gurl+"?v=10&encoding=json");stop.close=()=>{try{ws.close()}catch{}};ws.onopen=()=>{backoff=1000};ws.onmessage=ev=>{let d;try{d=JSON.parse(typeof ev.data==="string"?ev.data:"")}catch{return}if(d.op===10){const iv=Math.max(5000,(d.d&&d.d.heartbeat_interval)||30000);hb=setInterval(()=>{try{ws.send(JSON.stringify({op:1,d:seq}))}catch{}},iv);try{ws.send(JSON.stringify({op:2,d:{token:"Bot "+tok,intents:34304,properties:{os:"darwin",browser:"zcode",device:"zcode"}}}))}catch{}}else if(d.op===11){}else if(d.op===0){if(d.s!=null)seq=d.s;if(d.t==="READY"){selfId=d.d&&d.d.user&&d.d.user.id;try{re.setRuntimeStatus({botId:b.id,provider:"discord",status:"connected",message:"Discord Gateway is connected."})}catch{}}else if(d.t==="MESSAGE_CREATE"&&d.d){const m=d.d;const dm=!m.guild_id;const mentioned=Array.isArray(m.mentions)&&selfId&&m.mentions.some(u=>u&&u.id===selfId);if(dm||mentioned){ZCODE_dcIngest(Yd,b,{botId:b.id,selfUserId:selfId,message:m}).catch(()=>{})}}}};ws.onclose=()=>{if(hb)clearInterval(hb);reject(new Error("websocket closed"))};ws.onerror=()=>{}})}catch(err){if(stop.stop)break;try{re.setRuntimeStatus({botId:b.id,provider:"discord",status:"error",message:("Discord Gateway error: "+String(err&&err.message||err)).slice(0,140)})}catch{}}if(hb)clearInterval(hb);if(stop.stop)break;await new Promise(r=>setTimeout(r,backoff));backoff=Math.min(backoff*2,30000)}if(!stop.stop){try{re.setRuntimeStatus({botId:b.id,provider:"discord",status:"idle",message:"Discord Gateway is stopped."})}catch{}}}
async function ZCODE_dcIngest(Yd,b,payload){try{await Yd("discord",payload)}catch{}}
'''

TICK = r'''var ZCODE_dcMap=new Map;var ZCODE_dcTick=async()=>{try{const C=await n.readConfig();const want=new Set(C.bots.filter(k=>k.provider==="discord"&&k.enabled&&k.credentialRef).map(k=>k.id));for(const id of[...ZCODE_dcMap.keys()])if(!want.has(id)){const s=ZCODE_dcMap.get(id);s.stop=!0;try{s.close&&s.close()}catch{}ZCODE_dcMap.delete(id)}for(const b of C.bots)if(want.has(b.id)&&!ZCODE_dcMap.has(b.id)){const stop={stop:!1};ZCODE_dcMap.set(b.id,stop);ZCODE_dcRun(e,b,re,Yd,stop).catch(()=>{ZCODE_dcMap.delete(b.id)})}}catch{}};setInterval(()=>{ZCODE_dcTick().catch(()=>{})},8000);ZCODE_dcTick().catch(()=>{});'''


def main():
    changed = []

    src = open(HOST, errors="ignore").read()
    if "ZCODE_discordAdapter" in src:
        print("host: already patched")
    else:
        anchor_f = "function up(e){"
        assert src.count(anchor_f) == 1, "up( anchor missing"
        src = src.replace(anchor_f, ADAPTER + anchor_f, 1)
        changed.append("host: adapter+runtime injected (module scope)")

        old = "discord:null"
        new = 'discord:ZCODE_discordAdapter({loadCredential:i(h=>e.credentialService.load(h),"loadCredential")})'
        assert src.count(old) == 1, "discord:null anchor missing"
        src = src.replace(old, new, 1)
        changed.append("host: F.discord registered")

        anchor_u = "summarizeCallbackPayload:SH,processProviderCallback:Yd});"
        assert src.count(anchor_u) == 1, "feishu wiring anchor missing"
        src = src.replace(anchor_u, anchor_u + TICK, 1)
        changed.append("host: discord channel tick wired")
    open(HOST, "w").write(src)

    r = open(RENDERER, errors="ignore").read()
    flag_old = "id:`discord`,label:`Discord`,implemented:!1"
    flag_new = "id:`discord`,label:`Discord`,implemented:!0"
    if flag_new in r:
        print("renderer: already patched")
    else:
        assert r.count(flag_old) == 1, "renderer discord entry missing"
        r = r.replace(flag_old, flag_new, 1)
        changed.append("renderer: discord implemented flag flipped")
    open(RENDERER, "w").write(r)

    s = open(I18N, errors="ignore").read()
    # repair pass: a prior version could orphan the webhook key ("...discord":"v":<webhookvalue>)
    import re as _re
    s2, n_fixed = _re.subn(
        r'("bots\.botTokenDescription\.discord":"[^"]*")":(?=[`"])',
        r'\1,"bots.botTokenDescription.webhook":',
        s,
    )
    if n_fixed:
        s = s2
        changed.append(f"i18n: restored {n_fixed} orphaned webhook key(s)")
    have = s.count('"bots.botTokenDescription.discord"')
    if have >= 2:
        print("i18n: already patched (both locales)")
    else:
        anchor = '"bots.botTokenDescription.webhook'
        while s.count('"bots.botTokenDescription.discord"') < 2 and anchor in s:
            # insert before the first webhook key that isn't already preceded by a discord key
            idx = 0
            while True:
                idx = s.find(anchor, idx)
                assert idx != -1, "webhook i18n anchor missing"
                if s[max(0, idx - 200):idx].count('"bots.botTokenDescription.discord"') == 0:
                    break
                idx += 1
            val = "\\u4fdd\\u5b58 Discord Bot Token\\u3002" if s.count('"bots.botTokenDescription.discord"') == 0 else "Save your Discord bot token."
            s = s[:idx] + f'"bots.botTokenDescription.discord":"{val}",' + s[idx:]
        changed.append("i18n: discord token description ensured (zh+en)")
    open(I18N, "w").write(s)

    for c in changed:
        print("OK", c)


if __name__ == "__main__":
    sys.exit(main())
