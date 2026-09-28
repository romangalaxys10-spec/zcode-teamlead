// voice-inject.js — ZCode voice dictation, injected into the app's own renderer pages.
// Hold Alt+V (or click the pill) to record; release to transcribe locally
// (127.0.0.1:8399 mlx-whisper) and insert text at the caret of the focused
// input via execCommand('insertText') — the React-safe path.
// Canonical copy; the installed copy lives inside app.asar (revert: app.asar.bak-voice).
(() => {
  if (window.__zcodeVoice) return
  window.__zcodeVoice = true

  const STT = 'http://127.0.0.1:8399/transcribe'
  const pill = document.createElement('div')
  pill.textContent = '🎤 hold ⌥V'
  Object.assign(pill.style, {
    position: 'fixed', right: '14px', bottom: '14px', zIndex: 2147483647,
    padding: '6px 12px', borderRadius: '999px', font: '12px -apple-system,sans-serif',
    background: 'rgba(30,30,34,.82)', color: '#eee', cursor: 'pointer',
    userSelect: 'none', opacity: '0.35', transition: 'opacity .15s, background .15s',
    pointerEvents: 'auto',
  })
  pill.addEventListener('mouseenter', () => (pill.style.opacity = '1'))
  pill.addEventListener('mouseleave', () => (pill.style.opacity = '0.35'))
  pill.addEventListener('click', () => (rec.active || rec.pending ? rec.stop() : rec.start()))
  document.body ? document.body.appendChild(pill) : document.addEventListener('DOMContentLoaded', () => document.body.appendChild(pill))

  function say(t, bg) {
    pill.textContent = t
    pill.style.background = bg || 'rgba(30,30,34,.82)'
  }

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

  const rec = {
    active: false, pending: false, stopRequested: false, mr: null, chunks: [], target: null,
    async start() {
      if (this.active || this.pending) return
      this.pending = true
      this.stopRequested = false
      this.target = document.activeElement
      let stream
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      } catch (e) {
        this.pending = false
        say('🎤 mic blocked — grant permission', 'rgba(140,30,30,.9)')
        setTimeout(() => say('🎤 hold ⌥V'), 2500)
        return
      }
      try {
        this.chunks = []
        const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : ''
        this.mr = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
      } catch (e) {
        this.pending = false
        stream.getTracks().forEach((t) => t.stop())
        say('🎤 recorder unavailable', 'rgba(140,30,30,.9)')
        setTimeout(() => say('🎤 hold ⌥V'), 2500)
        return
      }
      this.mr.ondataavailable = (e) => e.data.size && this.chunks.push(e.data)
      this.mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(this.chunks, { type: this.mr.mimeType || 'audio/webm' })
        this.submit(blob)
      }
      if (this.stopRequested) {
        // keyup already happened while permission prompt was open — nothing to record
        this.pending = false
        stream.getTracks().forEach((t) => t.stop())
        say('🎤 hold ⌥V')
        return
      }
      this.pending = false
      this.active = true
      say('● REC — release ⌥V', 'rgba(180,40,40,.95)')
    },
    stop() {
      if (this.pending) { this.stopRequested = true; return }
      if (!this.active) return
      this.active = false
      if (this.mr && this.mr.state !== 'inactive') this.mr.stop()
      say('⏳ transcribing…', 'rgba(30,80,140,.9)')
    },
    insertAtCaret(el, text) {
      el.focus()
      if (el.isContentEditable) {
        if (document.execCommand('insertText', false, text)) return true
        return false
      }
      if (document.execCommand('insertText', false, text)) return true
      if (typeof el.setRangeText === 'function') {
        const s = el.selectionStart ?? el.value.length
        const e = el.selectionEnd ?? s
        el.setRangeText(text, s, e, 'end')
        el.dispatchEvent(new Event('input', { bubbles: true }))
        return true
      }
      return false
    },
    async submit(blob) {
      try {
        const res = await fetch(STT, { method: 'POST', body: blob })
        const data = await res.json()
        if (!res.ok) throw new Error(data.error || res.statusText)
        const text = (data.text || '').trim()
        if (!text) throw new Error('empty transcript')
        const el = this.target && this.target.isConnected ? this.target : document.activeElement
        if (editable(el) && this.insertAtCaret(el, text)) {
          say('✓ ' + (text.length > 26 ? text.slice(0, 26) + '…' : text), 'rgba(30,120,60,.9)')
        } else {
          await navigator.clipboard.writeText(text).catch(() => {})
          say('⧉ copied (focus a text input first)', 'rgba(120,90,20,.9)')
        }
      } catch (e) {
        say('🎤 ' + (e.message || 'STT down'), 'rgba(140,30,30,.9)')
      }
      setTimeout(() => say('🎤 hold ⌥V'), 2600)
    },
  }

  window.addEventListener('keydown', (e) => {
    if (e.altKey && (e.code === 'KeyV' || e.key === 'v') && !e.repeat && !e.metaKey && !e.ctrlKey) {
      e.preventDefault()
      rec.start()
    }
  }, true)
  window.addEventListener('keyup', (e) => {
    if (e.altKey || e.code === 'KeyV' || e.key === 'v') {
      if (rec.active || rec.pending) { e.preventDefault(); rec.stop() }
    }
  }, true)

  fetch('http://127.0.0.1:8399/health').then((r) => r.json()).catch(() => say('🎤 hold ⌥V (STT offline)'))
})()
