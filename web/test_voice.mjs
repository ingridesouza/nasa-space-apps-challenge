// F08 voice: tests of the front's pure functions (node web/test_voice.mjs; no browser)
import assert from 'node:assert/strict'
import { routeSummary, to16k } from './ui/voice.js'

// 48 kHz → 16 kHz: a third of the samples, each the mean of 3
assert.deepEqual([...to16k(Float32Array.from([1, 2, 3, 4, 5, 6]), 48000)], [2, 5])
assert.equal(to16k(new Float32Array(44100), 44100).length, 16000) // fractional rate
assert.equal(to16k(new Float32Array(16000), 16000).length, 16000) // already at 16 kHz

const route = (alerts) => ({ routes: [{ type: 'fastest', distance_m: 900, estimated_time_min: 9 },
  { type: 'safest', distance_m: 1234, estimated_time_min: 24.6, alerts }] })
assert.equal(routeSummary(route([]), 'Altadena'), 'Safest route to Altadena: 1.2 kilometers, about 25 minutes.')
const r = routeSummary(route([{ level: 'caution', message: 'x' }, { level: 'danger', message: 'Curiosity measured 22°.' }]), 'the base')
assert.ok(r.startsWith('Danger: Curiosity measured 22°. Safest route'), r) // danger first
assert.ok(r.endsWith('1 caution point along the way, see the map.'), r)
assert.equal(routeSummary(null, 'the base'), 'I could not compute the route to the base.')
console.log('test_voice.mjs: ok')
