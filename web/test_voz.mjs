// F08 voz: testes das funções puras do front (node web/test_voz.mjs; sem navegador)
import assert from 'node:assert/strict'
import { para16k, resumoRota } from './ui/voz.js'

// 48 kHz → 16 kHz: um terço das amostras, cada uma a média de 3
assert.deepEqual([...para16k(Float32Array.from([1, 2, 3, 4, 5, 6]), 48000)], [2, 5])
assert.equal(para16k(new Float32Array(44100), 44100).length, 16000) // taxa fracionária
assert.equal(para16k(new Float32Array(16000), 16000).length, 16000) // já em 16 kHz

const rota = (alertas) => ({ rotas: [{ tipo: 'mais_rapida', distancia_m: 900, tempo_estimado_min: 9 },
  { tipo: 'mais_segura', distancia_m: 1234, tempo_estimado_min: 24.6, alertas }] })
assert.equal(resumoRota(rota([]), 'Altadena'), 'Safest route to Altadena: 1.2 kilometers, about 25 minutes.') // padrão: inglês
assert.equal(resumoRota(rota([]), 'Altadena', 'pt'), 'Rota mais segura até Altadena: 1,2 quilômetros, cerca de 25 minutos.')
assert.equal(resumoRota(rota([]), 'Altadena', 'es'), resumoRota(rota([]), 'Altadena')) // sem texto em espanhol: inglês
const r = resumoRota(rota([{ nivel: 'atencao', mensagem: 'x' }, { nivel: 'perigo', mensagem: 'O Curiosity mediu 22°.' }]), 'a base', 'pt')
assert.ok(r.startsWith('Perigo: O Curiosity mediu 22°. Rota mais segura'), r) // perigo primeiro
assert.ok(r.endsWith('1 ponto de atenção no caminho, veja no mapa.'), r)
assert.ok(resumoRota(rota([{ nivel: 'perigo', mensagem: 'm' }]), 'the base').startsWith('Danger: m Safest route'))
assert.equal(resumoRota(null, 'the base'), "I couldn't plan the route to the base.")
console.log('test_voz.mjs: ok')
