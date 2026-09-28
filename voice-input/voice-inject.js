// voice-inject.js — ZCode real-time voice dictation (OpenMuse-style live captions).
// Hold Alt+V (or click the mic button beside the usage control in the composer)
// -> streams mic audio to the local faster-whisper service (ws://127.0.0.1:8398)
// -> live partials render in the pill; final text inserts at the caret on release.
// Fallbacks: local batch service :8399, then clipboard. Fully local, no cloud.
(() => {
  if (window.__zcodeVoice) return
  window.__zcodeVoice = true

  const STREAM_WS = 'ws://127.0.0.1:8398/stream'
  const BATCH_URL = 'http://127.0.0.1:8399/transcribe'
  const pill = document.createElement('div')
  pill.textContent = '🎤 hold ⌥V'
  Object.assign(pill.style, {
    position: 'fixed', right: '14px', bottom: '14px', zIndex: 2147483647,
    padding: '6px 12px', borderRadius: '999px', font: '12px -apple-system,sans-serif',
    background: 'rgba(30,30,34,.82)', color: '#eee', cursor: 'pointer',
    userSelect: 'none', opacity: '0.35', transition: 'opacity .15s, background .15s',
    pointerEvents: 'auto', maxWidth: '340px', overflow: 'hidden',
    textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  })
  pill.addEventListener('mouseenter', () => (pill.style.opacity = '1'))
  pill.addEventListener('mouseleave', () => (pill.style.opacity = '0.35'))
  pill.addEventListener('click', () => (rec.active || rec.pending ? rec.stop() : rec.toggle()))
  document.body ? document.body.appendChild(pill) : document.addEventListener('DOMContentLoaded', () => document.body.appendChild(pill))

  function say(t, bg) {
    pill.textContent = t
    pill.style.background = bg || 'rgba(30,30,34,.82)'
  }

  // mic + speaker buttons docked to the chat input's bottom-right corner
  const bar = document.createElement('div')
  Object.assign(bar.style, { position: 'fixed', zIndex: 2147483647, display: 'flex', gap: '4px', pointerEvents: 'auto' })
  const mkbtn = (txt, title) => {
    const b = document.createElement('button')
    b.textContent = txt; b.title = title
    Object.assign(b.style, {
      background: 'rgba(30,30,34,.9)', color: '#eee', border: '1px solid rgba(255,255,255,.14)',
      borderRadius: '8px', cursor: 'pointer', font: '13px -apple-system,sans-serif',
      padding: '4px 8px', opacity: '.85',
    })
    return b
  }
  const mic2 = mkbtn('\u{1F3A4}', 'Voice dictation (hold Alt+V)')
  const spk = mkbtn('\u{1F50A}', 'Toggle voice replies (TTS)')
  mic2.addEventListener('click', (e) => { e.stopPropagation(); rec.active || rec.pending ? rec.stop() : rec.toggle() })
  spk.addEventListener('click', (e) => {
    e.stopPropagation()
    const on = localStorage.getItem('zcode-tts') === '1'
    localStorage.setItem('zcode-tts', on ? '0' : '1')
    spk.textContent = on ? '\u{1F50A}' : '\u{1F504}'
  })
  spk.textContent = localStorage.getItem('zcode-tts') === '1' ? '\u{1F504}' : '\u{1F50A}'
  bar.append(mic2, spk)
  function dockBar() {
    const ed = document.querySelector('textarea') || document.querySelector('[contenteditable="true"]')
    if (!ed) { bar.style.display = 'none'; document.body.appendChild(bar); return }
    const r = ed.getBoundingClientRect()
    bar.style.display = 'flex'
    bar.style.right = Math.max(8, window.innerWidth - r.right + 4) + 'px'
    bar.style.top = (r.top - 34) + 'px'
    if (!bar.isConnected) document.body.appendChild(bar)
  }
  setInterval(dockBar, 2000)
  document.readyState === 'complete' ? dockBar() : window.addEventListener('load', dockBar)

  function editable(el) {
    if (!el) return false
    if (el.isContentEditable) return true
    if (el.tagName === 'TEXTAREA') return true
    if (el.tagName === 'INPUT') {
      const t = (el.getAttribute('type') || 'text').toLowerCase()
      return ['text', 'search', 'url', 'email', 'number', 'password', 'tel'].includes(t)
    }
    return false
  }

  function insertAtCaret(el, text) {
    el.focus()
    if (document.execCommand('insertText', false, text)) return true
    if (typeof el.setRangeText === 'function') {
      const s = el.selectionStart ?? el.value.length
      el.setRangeText(text, s, el.selectionEnd ?? s, 'end')
      el.dispatchEvent(new Event('input', { bubbles: true }))
      return true
    }
    return false
  }

  const rec = {
    active: false, pending: false, stopRequested: false, lock: false,
    ws: null, stream: null, node: null, ctx: null, lastPartial: '', target: null,
    toggle() { this.active || this.pending ? this.stop() : this.start() },
    insertFinal(el, text) {
      if (el && editable(el) && this.insertText(el, text)) return true
      navigator.clipboard.writeText(text).catch(() => {})
      say('⧉ copied (focus a text input first)', 'rgba(120,90,20,.9)')
      return false
    },
    insertText(el, text) {
      el.focus()
      if (document.execCommand('insertText', false, text)) return true
      if (typeof el.setRangeText === 'function') {
        const s = el.selectionStart ?? el.value.length
        el.setRangeText(text, s, el.selectionEnd ?? s, 'end')
        el.dispatchEvent(new Event('input', { bubbles: true }))
        return true
      }
      return false
    },
    async start() {
      if (this.active || this.pending) return
      this.pending = true; this.stopRequested = false
      this.target = document.activeElement
      let stream
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }) }
      catch { this.pending = false; say('🎤 mic blocked — grant permission', 'rgba(140,30,30,.9)'); setTimeout(() => say('🎤 hold ⌥V'), 2500); return }
      // realtime first: ws streaming to :8398
      try {
        const ws = new WebSocket(STREAM_WS)
        this.ws = ws; this.stream = stream
        let opened = false
        ws.onopen = () => {
          opened = true
          this.active = true; this.pending = false
          say('● REC (live) — release ⌥V', 'rgba(180,40,40,.95)')
          this.wireMic(stream, ws)
        }
        ws.onmessage = (ev) => {
          try {
            const d = JSON.parse(ev.data)
            if (d.type === 'partial' && d.text) { this.lastPartial = d.text; say('● ' + d.text.slice(-60), 'rgba(180,40,40,.95)') }
            if (d.type === 'final' && d.text && this.finalWait) {
              this.finalWait(d.text.trim())
              this.finalWait = null
            }
          } catch {}
        }
        ws.onclose = () => {
          if (!opened) this.batch(stream) // ws down -> batch fallback
          else if (this.active) this.active = false
        }
        ws.onerror = () => {}
      } catch { this.batch(stream) }
    },
    wireMic(stream, ws) {
      const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 })
      this.ctx = ctx; this.node = null
      const src = ctx.createMediaStreamSource(stream)
      const proc = ctx.createScriptProcessor(4096, 1, 1)
      proc.onaudioprocess = (e) => {
        if (!this.active) return
        const f = e.inputBuffer.getChannelData(0)
        const pcm = new Int16Array(f.length)
        for (let i = 0; i < f.length; i++) pcm[i] = Math.max(-1, Math.min(1, f[i])) * 32767
        if (ws.readyState === 1) ws.send(pcm.buffer)
      }
      src.connect(proc); proc.connect(ctx.destination)
      this.node = proc; this.ctx = ctx
    },
    batch(stream) {
      // batch fallback via MediaRecorder -> :8399
      this.pending = false
      try {
        const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : ''
        this.mr = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
      } catch { say('🎤 recorder unavailable', 'rgba(140,30,30,.9)'); return }
      const chunks = []
      this.mr.ondataavailable = (e) => e.data.size && chunks.push(e.data)
      this.mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunks, { type: this.mr.mimeType || 'audio/webm' })
        say('⏳ transcribing…', 'rgba(30,80,140,.9)')
        try {
          const res = await fetch(BATCH_URL, { method: 'POST', body: blob })
          const d = await res.json()
          const text = (d.text || '').trim()
          if (!text) throw new Error('empty')
          const el = this.target && this.target.isConnected ? this.target : document.activeElement
          if (editable(el) && this.insertText(el, text)) say('✓ ' + text.slice(0, 40), 'rgba(30,120,60,.9)')
          else { navigator.clipboard.writeText(text).catch(() => {}); say('⧉ copied', 'rgba(120,90,20,.9)') }
        } catch (e) { say('🎤 ' + (e.message || 'batch STT failed'), 'rgba(140,30,30,.9)') }
        setTimeout(() => say('🎤 hold ⌥V'), 2500)
      }
      this.mr.start()
      this.active = true
      say('● REC (batch) — release ⌥V', 'rgba(180,40,40,.95)')
    },
    stop() {
      if (!this.active && !this.pending) return
      this.active = false
      const finish = (finalText) => {
        try { this.ws && this.ws.close() } catch {}
        try { this.stream && this.stream.getTracks().forEach((t) => t.stop()) } catch {}
        try { this.ctx && this.ctx.close() } catch {}
        this.ws = this.stream = this.ctx = this.node = null
        const el = this.target && this.target.isConnected ? this.target : document.activeElement
        const text = (finalText || this.lastPartial || '').trim()
        if (text) {
          if (editable(el) && this.insertText(el, text)) say('✓ ' + text.slice(0, 40), 'rgba(30,120,60,.9)')
          else { navigator.clipboard.writeText(text).catch(() => {}); say('⧉ copied', 'rgba(120,90,20,.9)') }
        } else say('🎤 (nothing heard)')
        this.lastPartial = ''
        setTimeout(() => say('🎤 hold ⌥V'), 2500)
      }
      // wait up to 6s for a better final; use last partial as immediate draft
      this.finalWait = (t) => finish(t)
      const draft = this.lastPartial
      try { this.ws && this.ws.readyState === 1 && this.ws.send('FLUSH') } catch {}
      if (this.mr && this.mr.state !== 'inactive') { this.mr.stop(); return }
      setTimeout(() => { if (this.finalWait === finish) finish(draft) }, 6000)
    },
  }

  window.addEventListener('keydown', (e) => {
    if (e.altKey && (e.code === 'KeyV' || e.key === 'v') && !e.repeat && !e.metaKey && !e.ctrlKey) { e.preventDefault(); rec.start() }
  }, true)
  window.addEventListener('keyup', (e) => {
    if (e.altKey || e.code === 'KeyV' || e.key === 'v') { if (rec.active || rec.pending) { e.preventDefault(); rec.stop() } }
  }, true)

  fetch('http://127.0.0.1:8398/health').then((r) => r.json()).catch(() => say('🎤 hold ⌥V (STT offline)'))
})()
