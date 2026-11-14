// F08 voz: "Guia, rota até Altadena" → Whisper local → "Confirma?" → "sim" → rota no mapa → resumo falado.
// Mãos-livres (detector de fala por energia) ou "segure espaço". Plano: docs/feature-08-voz-plano-execucao.md
import { enviarVoz } from '../api.js'
import { falar } from './agente.js'

const TAXA = 16000
const INICIO_S = 0.15 // fala começa depois disso acima do limiar
const FIM_S = 1.2 // e termina depois disso de silêncio (fala livre tem pausa: "to no meio de uma rota… e")
const ANTES_S = 0.3 // guarda o começo da palavra que disparou o detector
const MAX_S = 14 // a API recusa acima de 15 s
const CONFIRMA_MS = 8000 // janela do "sim" depois que o sistema termina de falar
const ESCUTA_MS = 8000 // depois de um "Ei guia" sozinho, espera o pedido por este tempo

/** Reamostra para 16 kHz pela média de cada janela (sem o serrilhado de pular amostras). */
export function para16k(amostras, taxa) {
  const r = taxa / TAXA
  const out = new Float32Array(Math.floor(amostras.length / r))
  for (let i = 0; i < out.length; i++) {
    const a = Math.floor(i * r)
    const b = Math.max(a + 1, Math.floor((i + 1) * r))
    let s = 0
    for (let j = a; j < b; j++) s += amostras[j]
    out[i] = s / (b - a)
  }
  return out
}

const curto = (nome) => nome.split('—')[0].trim()

/** Resumo falado montado só com números do /api/route; o perigo vem primeiro. */
export function resumoRota(data, nome) {
  const r = data?.rotas?.find((x) => x.tipo === 'mais_segura') ?? data?.rotas?.[0]
  if (!r) return `Não consegui calcular a rota até ${nome}.`
  const alertas = r.alertas ?? []
  const perigos = alertas.filter((a) => a.nivel === 'perigo').map((a) => `Perigo: ${a.mensagem}`)
  const atencao = alertas.filter((a) => a.nivel === 'atencao').length
  const km = (r.distancia_m / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })
  return [
    ...perigos,
    `Rota mais segura até ${nome}: ${km} quilômetros, cerca de ${Math.round(r.tempo_estimado_min)} minutos.`,
    atencao ? `${atencao} ${atencao > 1 ? 'pontos' : 'ponto'} de atenção no caminho, veja no mapa.` : '',
  ].join(' ').trim()
}

/**
 * botao: liga/desliga o mãos-livres; status: linha de estado (aria-live).
 * pontoAtual() → {lat, lon} | null; rota(origem, destino) → Promise<dados do /api/route | null>;
 * perguntar(texto): manda ao assistente, que mostra e fala a resposta.
 */
export function iniciarVoz(botao, status, { pontoAtual, rota, perguntar }) {
  let ctx = null
  let taxa = 48000
  let maosLivres = true // como a Siri: sempre ouvindo pelo "Ei guia"; o botão desliga
  let segurando = false
  let ocupado = false
  let gravando = null // quadros da fala atual
  let antes = []
  let acima = 0
  let abaixo = 0
  let ruido = 0.01
  let pendente = null // rota esperando o "sim"
  let confirmarAte = 0
  let escutaAte = 0 // > agora: a próxima fala já é com o Guia
  let mudoAte = 0

  const mostrar = (texto) => { status.textContent = texto; status.hidden = !texto }
  const ocioso = () => mostrar(!maosLivres ? ''
    : ctx?.state === 'running' ? 'diga "Ei guia" · ou segure espaço' : 'clique na página para ligar o microfone')

  async function ligarMicrofone() {
    if (ctx) return
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    ctx = new AudioContext()
    taxa = ctx.sampleRate
    await ctx.audioWorklet.addModule(new URL('./voz-captura.js', import.meta.url))
    const no = new AudioWorkletNode(ctx, 'h2g2-captura')
    no.port.onmessage = (e) => quadro(e.data)
    ctx.createMediaStreamSource(stream).connect(no)
    no.connect(ctx.destination) // a saída é silêncio; ligado só para o navegador processar o nó
    // sem gesto do usuário o navegador deixa o áudio suspenso: liga no primeiro clique ou tecla
    ctx.resume()
    const retomar = () => ctx.resume().then(ocioso)
    document.addEventListener('pointerdown', retomar, { once: true })
    document.addEventListener('keydown', retomar, { once: true })
  }

  /** Bipe de "estou ouvindo" (oscilador, sem arquivo de som). */
  function bipe() {
    const o = ctx.createOscillator()
    const g = ctx.createGain()
    o.frequency.value = 880
    g.gain.setValueAtTime(0.15, ctx.currentTime)
    g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15)
    o.connect(g).connect(ctx.destination)
    o.start()
    o.stop(ctx.currentTime + 0.15)
    mudoAte = Date.now() + 300 // não gravar o próprio bipe
  }

  function quadro(f) {
    const agora = Date.now()
    if (segurando) return gravando.push(f)
    if (agora < mudoAte) return
    if (ocupado || speechSynthesis.speaking) {
      // microfone mudo enquanto o sistema fala: não ouvir a si mesmo
      if (pendente) confirmarAte = agora + CONFIRMA_MS
      gravando = null
      acima = 0
      return
    }
    if (pendente && agora > confirmarAte && !gravando) {
      pendente = null
      falar('Sem confirmação. Cancelado.')
      return
    }
    if (escutaAte && agora > escutaAte && !gravando) {
      escutaAte = 0
      ocioso()
    }
    if (!maosLivres && !pendente && !escutaAte) return
    const dur = f.length / taxa
    let soma = 0
    for (const x of f) soma += x * x
    const rms = Math.sqrt(soma / f.length)
    const limiar = Math.max(ruido * 3, 0.01)
    if (!gravando) {
      antes.push(f)
      while (antes.length * dur > ANTES_S) antes.shift()
      if (rms <= limiar) {
        acima = 0
        ruido = ruido * 0.99 + rms * 0.01 // o limiar acompanha o ruído da sala
      } else if ((acima += dur) >= INICIO_S) {
        gravando = antes
        antes = []
        abaixo = 0
        mostrar('gravando…')
      }
      return
    }
    gravando.push(f)
    abaixo = rms > limiar ? 0 : abaixo + dur
    if (abaixo >= FIM_S || gravando.length * dur >= MAX_S) {
      const escutando = agora < escutaAte
      escutaAte = 0
      terminar(Boolean(pendente) || escutando)
    }
  }

  function terminar(ativado) {
    const partes = gravando ?? []
    gravando = null
    acima = 0
    const tudo = new Float32Array(partes.reduce((n, p) => n + p.length, 0))
    let o = 0
    for (const p of partes) { tudo.set(p, o); o += p.length }
    const audio = para16k(tudo, taxa)
    if (audio.length < TAXA * 0.3) return ocioso() // clique ou tosse, não fala
    processar(audio.subarray(0, MAX_S * TAXA), ativado)
  }

  async function processar(audio, ativado) {
    ocupado = true
    mostrar('transcrevendo…')
    const confirmando = Boolean(pendente)
    try {
      const p = pontoAtual()
      const r = await enviarVoz(audio, { ativado, confirmando, lat: p?.lat, lon: p?.lon })
      if (r.texto) mostrar(`ouvi: “${r.texto}”`)
      await agir(r, confirmando, ativado)
    } catch (e) {
      mostrar(`voz: ${e.message}`)
      falar('A voz falhou. Use a caixa de texto.')
    } finally {
      ocupado = false
    }
  }

  async function agir(r, confirmando, ativado) {
    if (confirmando) {
      const acao = pendente
      pendente = null
      if (r.intencao !== 'sim') return falar('Cancelado.')
      falar(`Calculando a rota até ${acao.nome}.`)
      return falar(resumoRota(await rota(acao.origem, acao.destino), acao.nome))
    }
    if (r.intencao === 'escutar') {
      bipe()
      escutaAte = Date.now() + ESCUTA_MS
      return mostrar('ouvindo… pode falar')
    }
    if (r.intencao === 'rota' && r.destino) {
      pendente = { origem: r.origem, destino: { lat: r.destino.lat, lon: r.destino.lon }, nome: curto(r.destino.nome) }
      confirmarAte = Date.now() + CONFIRMA_MS
      return falar(r.fala)
    }
    if (r.intencao === 'rota') return falar(r.fala) // "marque no mapa onde você está"
    if (r.intencao === 'pergunta') return perguntar(r.pergunta)
    if (r.intencao === 'sim' || r.intencao === 'nao') return falar('Não há nada para confirmar.')
    if (ativado && r.fala) falar(r.fala) // "Não entendi." só quando a pessoa apertou para falar
    else ocioso()
  }

  const digitando = (e) => e.target.closest?.('input, textarea, select, [contenteditable]')
  document.addEventListener('keydown', async (e) => {
    if (e.code !== 'Space' || digitando(e)) return
    e.preventDefault()
    if (e.repeat || segurando || ocupado) return
    speechSynthesis.cancel() // falar por cima interrompe o sistema
    try {
      await ligarMicrofone()
    } catch (err) {
      return mostrar(`microfone indisponível: ${err.message}`)
    }
    segurando = true
    gravando = []
    mostrar('ouvindo… solte espaço ao terminar')
  })
  document.addEventListener('keyup', (e) => {
    if (e.code !== 'Space' || digitando(e)) return
    e.preventDefault()
    if (!segurando) return
    segurando = false
    terminar(true)
  })
  async function ligarMaosLivres(ligado) {
    try {
      await ligarMicrofone()
    } catch (err) {
      ligado = false
      mostrar(`microfone indisponível: ${err.message}`)
    }
    maosLivres = ligado
    botao.classList.toggle('on', maosLivres)
    botao.setAttribute('aria-pressed', String(maosLivres))
    if (ctx) ocioso()
  }
  botao.addEventListener('click', () => {
    botao.blur() // senão o espaço do "segure para falar" clica no botão
    ligarMaosLivres(!maosLivres)
  })
  ligarMaosLivres(true) // ao abrir: o navegador pede o microfone uma vez
}
