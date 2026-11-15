// F08 voice: "Marvin, route to Altadena" → local Whisper → "Confirm?" → "yes" → route on the map. No speech output: replies show on the pill.
// Hands-free (energy-based speech detector) or "hold space". Plan: docs/feature-08-voz-plano-execucao.md
import { sendVoice } from '../api.js'

const RATE = 16000
const START_S = 0.15 // speech starts after this much above the threshold
const END_S = 1.2 // and ends after this much silence (free speech has pauses: "I'm in the middle of a route… and")
const BEFORE_S = 0.3 // keeps the start of the word that triggered the detector
const MAX_S = 59 // the API rejects more than 60 s
const CONFIRM_MS = 8000 // window for the "yes" after the "Confirm?" shows on the pill
const LISTEN_MS = 8000 // after a bare "Hey Marvin", waits for the request this long

/** Resamples to 16 kHz by averaging each window (no aliasing from skipping samples). */
export function to16k(samples, rate) {
  const r = rate / RATE
  const out = new Float32Array(Math.floor(samples.length / r))
  for (let i = 0; i < out.length; i++) {
    const a = Math.floor(i * r)
    const b = Math.max(a + 1, Math.floor((i + 1) * r))
    let s = 0
    for (let j = a; j < b; j++) s += samples[j]
    out[i] = s / (b - a)
  }
  return out
}

const short = (name) => name.split('—')[0].trim()

/** Spoken summary built only with /api/route numbers; danger comes first. */
export function routeSummary(data, name) {
  const r = data?.routes?.find((x) => x.type === 'safest') ?? data?.routes?.[0]
  if (!r) return `I could not compute the route to ${name}.`
  const alerts = r.alerts ?? []
  const dangers = alerts.filter((a) => a.level === 'danger').map((a) => `Danger: ${a.message}`)
  const cautions = alerts.filter((a) => a.level === 'caution').length
  const km = (r.distance_m / 1000).toLocaleString('en-US', { maximumFractionDigits: 1 })
  return [
    ...dangers,
    `Safest route to ${name}: ${km} kilometers, about ${Math.round(r.estimated_time_min)} minutes.`,
    cautions ? `${cautions} caution ${cautions > 1 ? 'points' : 'point'} along the way, see the map.` : '',
  ].join(' ').trim()
}

/**
 * button: turns hands-free on/off; status: state line (aria-live).
 * currentPoint() → {lat, lon} | null; route(origin, destination) → Promise<data from /api/route | null>;
 * ask(text): sends to the assistant, which shows the answer.
 * execute(cmd) → {ok, text}: interface command (F11); context() → {openBlocks, focus}.
 */
export function initVoice(button, status, { currentPoint, route, ask, execute, context }) {
  let ctx = null
  let rate = 48000
  let handsFree = true // like Siri: always listening for "Hey Marvin"; the button turns it off
  let holding = false
  let busy = false
  let recording = null // frames of the current utterance
  let before = []
  let above = 0
  let below = 0
  let noise = 0.01
  let pending = null // route or interface command waiting for the "yes"
  let confirmUntil = 0
  let listenUntil = 0 // > now: the next utterance is already addressed to Marvin
  let muteUntil = 0

  const show = (text) => { status.textContent = text; status.hidden = !text }
  const idle = () => show(!handsFree ? 'microphone off · hold space to talk'
    : ctx?.state === 'running' ? 'say "Hey Marvin" · or hold space' : 'click the page to turn on the microphone')

  async function startMicrophone() {
    if (ctx) return
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    ctx = new AudioContext()
    rate = ctx.sampleRate
    await ctx.audioWorklet.addModule(new URL('./voice-capture.js', import.meta.url))
    const node = new AudioWorkletNode(ctx, 'h2g2-capture')
    node.port.onmessage = (e) => frame(e.data)
    ctx.createMediaStreamSource(stream).connect(node)
    node.connect(ctx.destination) // the output is silence; connected only so the browser processes the node
    // without a user gesture the browser keeps audio suspended: resume on the first click or key
    ctx.resume()
    const resume = () => ctx.resume().then(idle)
    document.addEventListener('pointerdown', resume, { once: true })
    document.addEventListener('keydown', resume, { once: true })
  }

  /** "I'm listening" beep (oscillator, no sound file). */
  function beep() {
    const o = ctx.createOscillator()
    const g = ctx.createGain()
    o.frequency.value = 880
    g.gain.setValueAtTime(0.15, ctx.currentTime)
    g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15)
    o.connect(g).connect(ctx.destination)
    o.start()
    o.stop(ctx.currentTime + 0.15)
    muteUntil = Date.now() + 300 // do not record the beep itself
  }

  function frame(f) {
    const now = Date.now()
    if (holding) return recording.push(f)
    if (now < muteUntil) return
    if (busy) {
      if (pending) confirmUntil = now + CONFIRM_MS
      recording = null
      above = 0
      return
    }
    if (pending && now > confirmUntil && !recording) {
      pending = null
      show('No confirmation. Cancelled.')
      return
    }
    if (listenUntil && now > listenUntil && !recording) {
      listenUntil = 0
      idle()
    }
    if (!handsFree && !pending && !listenUntil) return
    const dur = f.length / rate
    let sum = 0
    for (const x of f) sum += x * x
    const rms = Math.sqrt(sum / f.length)
    const threshold = Math.max(noise * 3, 0.01)
    if (!recording) {
      before.push(f)
      while (before.length * dur > BEFORE_S) before.shift()
      if (rms <= threshold) {
        above = 0
        noise = noise * 0.99 + rms * 0.01 // the threshold follows the room noise
      } else if ((above += dur) >= START_S) {
        recording = before
        before = []
        below = 0
        show('recording…')
      }
      return
    }
    recording.push(f)
    below = rms > threshold ? 0 : below + dur
    if (below >= END_S || recording.length * dur >= MAX_S) {
      const listening = now < listenUntil
      listenUntil = 0
      finish(Boolean(pending) || listening)
    }
  }

  function finish(activated) {
    const parts = recording ?? []
    recording = null
    above = 0
    const all = new Float32Array(parts.reduce((n, p) => n + p.length, 0))
    let o = 0
    for (const p of parts) { all.set(p, o); o += p.length }
    const audio = to16k(all, rate)
    if (audio.length < RATE * 0.3) return idle() // a click or a cough, not speech
    process(audio.subarray(0, MAX_S * RATE), activated)
  }

  async function process(audio, activated) {
    busy = true
    show('transcribing…')
    const confirming = Boolean(pending)
    try {
      const p = currentPoint()
      const r = await sendVoice(audio, { activated, confirming, lat: p?.lat, lon: p?.lon, ...context() })
      if (r.text) show(`heard: “${r.text}”`)
      await act(r, confirming, activated)
    } catch (e) {
      show(`voice: ${e.message.split(' (')[0]}`) // on-screen only, never spoken
    } finally {
      busy = false
    }
  }

  async function act(r, confirming, activated) {
    if (confirming) {
      const action = pending
      pending = null
      if (r.intent !== 'yes') return show('Cancelled.')
      if (action.command) return runInterface(action.command)
      show(`Computing the route to ${action.name}.`)
      return show(routeSummary(await route(action.origin, action.destination), action.name))
    }
    if (r.intent === 'listen') {
      beep()
      listenUntil = Date.now() + LISTEN_MS
      return show('listening… go ahead')
    }
    if (r.intent === 'route' && r.destination) {
      pending = { origin: r.origin, destination: { lat: r.destination.lat, lon: r.destination.lon }, name: short(r.destination.name) }
      confirmUntil = Date.now() + CONFIRM_MS
      return show(r.speech)
    }
    if (r.intent === 'route') return show(r.speech) // "mark on the map where you are"
    if (r.intent === 'interface') {
      if (!r.command) return show(r.speech) // missing argument or ambiguous block: the speech says what
      if (!r.confirm) return runInterface(r.command)
      pending = { command: r.command }
      confirmUntil = Date.now() + CONFIRM_MS
      return show(r.speech)
    }
    if (r.intent === 'question') return ask(r.question)
    if (r.intent === 'yes' || r.intent === 'no') return show('There is nothing to confirm.')
    if (activated && r.speech) show(r.speech) // "I didn't understand." only when the person pressed to talk
    else idle()
  }

  /** Interface action: no speech on success (only the status line), speech on failure. */
  async function runInterface(cmd) {
    const res = await execute(cmd)
    show(`${res.ok ? '✓' : '✕'} ${res.text}`)
  }

  const typing = (e) => e.target.closest?.('input, textarea, select, [contenteditable]')
  document.addEventListener('keydown', async (e) => {
    if (e.code !== 'Space' || typing(e)) return
    e.preventDefault()
    if (e.repeat || holding || busy) return
    try {
      await startMicrophone()
    } catch (err) {
      return show(`microphone unavailable: ${err.message}`)
    }
    holding = true
    recording = []
    show('listening… release space when done')
  })
  document.addEventListener('keyup', (e) => {
    if (e.code !== 'Space' || typing(e)) return
    e.preventDefault()
    if (!holding) return
    holding = false
    finish(true)
  })
  async function setHandsFree(on) {
    try {
      await startMicrophone()
    } catch (err) {
      on = false
      show(`microphone unavailable: ${err.message}`)
    }
    handsFree = on
    button.classList.toggle('on', handsFree)
    button.setAttribute('aria-pressed', String(handsFree))
    if (ctx) idle()
  }
  button.addEventListener('click', () => {
    button.blur() // otherwise the space of "hold to talk" clicks the button
    setHandsFree(!handsFree)
  })
  setHandsFree(true) // on open: the browser asks for the microphone once
}
