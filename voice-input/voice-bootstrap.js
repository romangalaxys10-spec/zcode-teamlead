// voice-bootstrap.js — ZCode main-process bootstrap (ESM; package.json "type":"module").
// Loads the ORIGINAL main entry unchanged, but first installs a
// web-contents-created hook that injects voice-inject.js into the app's own
// renderer pages on did-finish-load. Revert = restore package.json
// "main": "out/main/index.js".
import { app } from 'electron'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { homedir } from 'node:os'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))

let inject = ''
try {
  try { inject = readFileSync(join(homedir(), '.zcode/voice/voice-inject.js'), 'utf8') } catch { inject = readFileSync(join(here, 'voice-inject.js'), 'utf8') }
} catch (e) {
  console.error('[voice] voice-inject.js unreadable, dictation disabled:', e?.message)
}

// Inject ONLY into the app's own local pages — never into remote web content.
function shouldInject(wc) {
  try {
    const u = wc.getURL()
    return u.startsWith('file:') || u.startsWith('app:')
  } catch {
    return false
  }
}

app.on('web-contents-created', (_event, wc) => {
  wc.on('did-finish-load', () => {
    if (!inject || !shouldInject(wc)) return
    wc.executeJavaScript(inject, true).catch((e) => {
      console.error('[voice] injection failed on', String(wc.getURL?.() || '?'), e?.message)
    })
  })
})

await import('./out/main/index.js')
