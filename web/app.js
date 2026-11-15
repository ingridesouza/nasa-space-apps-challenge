// H2G2 · orquestração do front. Visor (F03/F04) em tela cheia; mapa (F01) num círculo
// que expande; rota (F02 + F06) num card; assistente (F08) no topo.
// A posição atual vem do rastreador (simulado em /api/posicao) e é a origem da rota.
import {
  getFichaCientifica, getFotosPerto, getLayers, getPanorama,
  getPoint, getPosicao, postComando,
} from './api.js'
import { TOGGLEABLE_LAYERS } from './layers.js'
import * as mapa from './map.js'
import { falar, iniciarAssistente } from './ui/agente.js'
import { renderCamadas } from './ui/camadas.js'
import { iniciarRota } from './ui/rota.js'
import { iniciarVoz } from './ui/voz.js'
import { contexto, descreverAbertos, executar, iniciarComandos, registrar } from './ui/comandos.js'
import { mudarPagina, paginar } from './ui/paginas.js'
import { esc } from './ui/util.js'

const $ = (id) => document.getElementById(id)
const mobile = () => matchMedia('(max-width:900px)').matches
const TRANSICAO_MS = 260 // igual à transição de .mapa-box em style.css

const estado = {
  posicao: null, // {lat, lon, rotulo}
  local: null, // o que o visor e os cards mostram: posição ou destino
  mapa: 'visor', // 'visor' (círculo) | 'explorar' | 'rota'
  rotaAtiva: false,
  destino: null,
  escalas: [],
  rota: null,
  camadas: Object.fromEntries(TOGGLEABLE_LAYERS.map((l) => [l.id, { visible: l.defaultVisible, opacity: l.defaultOpacity }])),
}
let aguardandoEscala = false

// ---------------- Local (posição ou destino): status, panorama, fotos, ficha ----------------
let seqLocal = 0
let ultimo = null // {pano} do local atual, para redesenhar o status

async function carregarLocal(local) {
  const meu = ++seqLocal
  estado.local = local
  carregando()
  mostrarFicha('carregando')
  const { lat, lon } = local
  const [pano, fotos, ficha] = (await Promise.allSettled([
    getPanorama(lat, lon), getFotosPerto(lat, lon), getFichaCientifica(lat, lon),
  ])).map((r) => (r.status === 'fulfilled' ? r.value : null))
  if (meu !== seqLocal) return // outro local já substituiu este
  ultimo = { pano }
  mapa.setPanorama(pano?.found ? pano : null)
  if (pano) mostrarPano(pano)
  else limparPano()
  mostrarFicha(ficha ?? 'erro')
  if (fotos) mostrarFotos(fotos)
  else $('c-fotos').hidden = true
}

// barra de imagens vazia (e fechada pelo :has do CSS) até haver destino com rota calculada
function limparBarra() {
  seqLocal++
  estado.local = null
  ultimo = null
  limparPano()
  fecharFoto()
  mapa.setPanorama(null)
  for (const id of ['c-status', 'c-fotos', 'c-ficha']) $(id).hidden = true
  colapsarGrupo('g-imagens', false)
}

const mesmoPonto = (a, b) => a && b && a.lat === b.lat && a.lon === b.lon

function carregando() {
  for (const id of ['c-pano', 'c-fotos', 'c-ficha']) $(id).hidden = true
}

function card(id, html) { $(id).innerHTML = html; $(id).hidden = false }

// ---------------- Panorama ----------------
let viewer = null // preview (sempre no painel)
let viewerFundo = null // cópia no visor
let cfgPano = null
let noVisor = false
// preview mais aproximado; no fundo, volta a 90° e sobe/desce um pouco rumo ao centro da imagem
const HFOV_PREVIEW = 65, HFOV_FUNDO = 90, CENTRO_FUNDO = 0.5, CENTRO_PREVIEW = 0.3
let voff = 0
let panoSeq = 0

function limparPano() {
  panoSeq++
  if (noVisor) recolher()
  if (viewer) { viewer.destroy(); viewer = null }
  $('pano').innerHTML = ''
  $('c-pano').hidden = true
}

function mostrarPano(p) {
  limparPano()
  if (!p.found) return
  $('c-pano').hidden = false
  $('pano-rotulo').textContent = `${p.rotulo} · ${p.credito}`
  voff = p.pannellum.vOffset || 0
  cfgPano = Object.assign({}, p.pannellum, {
    showControls: false, compass: false,
    hotSpots: [{ pitch: 0, yaw: p.pannellum.yaw, type: 'info', text: 'direção do ponto informado' }],
  })
  // cria o viewer só depois do card pintar: init do pannellum é pesado e travava a animação
  const seq = panoSeq
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (seq !== panoSeq) return
    viewer = pannellum.viewer('pano', Object.assign({}, cfgPano, { hfov: HFOV_PREVIEW, pitch: voff * CENTRO_PREVIEW }))
  }))
}

// duas barras independentes na coluna da direita (rota e imagens), cada uma com seu botão
function colapsarGrupo(id, c) {
  const g = $(id)
  g.classList.toggle('colapsada', c)
  const t = g.querySelector('.grupo-toggle')
  t.textContent = c ? '‹' : '›'
  t.title = `${c ? 'Expandir' : 'Recolher'} ${t.dataset.nome}`
  t.setAttribute('aria-expanded', String(!c))
  if (id === 'g-rota' && !c) requestAnimationFrame(() => paginar($('c-rota'))) // escondido mediu 0 px
  if (id === 'g-imagens') {
    $('fichas').classList.toggle('colapsada', c)
    if (!c) requestAnimationFrame(() => { viewer?.resize(); posicionarFichas() }) // pannellum mediu 0 px escondido
  }
}
// fichas à esquerda da barra de imagens (embaixo, CSS); no mobile ficam acima da folha inferior
function posicionarFichas() {
  const f = $('fichas')
  f.style.bottom = mobile() ? innerHeight - $('flutuante').getBoundingClientRect().top + 8 + 'px' : ''
}
{
  const ro = new ResizeObserver(posicionarFichas)
  for (const id of ['flutuante', 'c-rota', 'c-status', 'c-pano', 'c-fotos']) ro.observe($(id))
  addEventListener('resize', posicionarFichas)
  $('flutuante').addEventListener('scroll', posicionarFichas)
}
for (const t of document.querySelectorAll('.grupo-toggle')) {
  t.addEventListener('click', () => { const g = t.parentElement; colapsarGrupo(g.id, !g.classList.contains('colapsada')) })
}

// visor ganha um 2º viewer (mesma imagem, yaw atual); o preview continua no painel
function expandir() {
  if (!viewer) return
  colapsarGrupo('g-imagens', true)
  fecharFoto()
  const d = document.createElement('div')
  d.id = 'pano-fundo'
  $('visor-stage').appendChild(d)
  viewerFundo = pannellum.viewer('pano-fundo', Object.assign({}, cfgPano, {
    hfov: HFOV_FUNDO, pitch: voff * CENTRO_FUNDO, yaw: viewer.getYaw(),
  }))
  $('visor-vazio').hidden = true
  $('visor-fechar').hidden = false
  noVisor = true
  // tira o foco do botão (agora na barra recolhida) e entrega ao panorama
  if (document.activeElement) document.activeElement.blur()
  d.tabIndex = 0
  d.focus({ preventScroll: true })
}
function recolher() {
  if (viewerFundo) { viewerFundo.destroy(); viewerFundo = null }
  $('pano-fundo')?.remove()
  $('visor-vazio').hidden = !!viewer
  $('visor-fechar').hidden = true
  noVisor = false
  colapsarGrupo('g-imagens', false)
}
$('pano-expandir').addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); noVisor ? recolher() : expandir() })

// ---------------- Fotos ----------------
const FOTOS_POR_PAG = 3
let fotosLista = [], fotosPag = 0

function mostrarFotos(f) {
  $('c-fotos').hidden = !f.total
  if (!f.total) return
  fotosLista = f.fotos
  fotosPag = 0
  renderFotos(0)
}

function renderFotos(dir) {
  const total = Math.max(1, Math.ceil(fotosLista.length / FOTOS_POR_PAG))
  fotosPag = Math.min(Math.max(fotosPag, 0), total - 1)
  const box = $('fotos')
  box.innerHTML = ''
  for (const ft of fotosLista.slice(fotosPag * FOTOS_POR_PAG, (fotosPag + 1) * FOTOS_POR_PAG)) {
    const b = document.createElement('button')
    b.type = 'button'; b.className = 'foto'; b.title = ft.rotulo
    b.innerHTML = `<img loading="lazy" src="${esc(ft.thumb)}" alt=""><p>${ft.distancia_m < 5 ? '&lt; 10' : `~${Math.round(ft.distancia_m / 10) * 10}`} m · ${esc(ft.instrument)}</p>`
    b.onclick = () => abrirFoto(ft)
    box.appendChild(b)
  }
  box.classList.remove('slide-next', 'slide-prev')
  if (dir) { void box.offsetWidth; box.classList.add(dir > 0 ? 'slide-next' : 'slide-prev') }
  $('fotos-nav').hidden = total <= 1
  $('fotos-pag').textContent = `${fotosPag + 1} / ${total}`
  $('fotos-prev').disabled = fotosPag === 0
  $('fotos-next').disabled = fotosPag === total - 1
}
$('fotos-prev').addEventListener('click', () => { fotosPag--; renderFotos(-1) })
$('fotos-next').addEventListener('click', () => { fotosPag++; renderFotos(1) })

function abrirFoto(ft) {
  if (noVisor) recolher()
  $('visor-img').src = ft.img
  $('visor-img').alt = ft.rotulo
  $('visor-img').hidden = false
  $('visor-vazio').hidden = true
  $('visor-fechar').hidden = false
}
function fecharFoto() {
  $('visor-img').hidden = true
  $('visor-img').removeAttribute('src')
  $('visor-vazio').hidden = noVisor
  $('visor-fechar').hidden = !noVisor
}
function fecharVisor() { if (noVisor) recolher(); fecharFoto() }
$('visor-fechar').addEventListener('click', fecharVisor)

// ---------------- Ficha científica (F04, card.js) ----------------
function mostrarFicha(d, abrir = false) {
  const aberta = $('c-ficha').open
  $('c-ficha').hidden = false
  $('c-ficha').open = abrir || (d !== 'carregando' && aberta)
  const [nome, tipo] = H2G2Card.titulo(d)
  $('ficha-nome').textContent = nome
  $('ficha-tipo').textContent = tipo
  $('ficha').innerHTML = H2G2Card.html(d)
  requestAnimationFrame(() => { paginarFicha(); posicionarFichas() })
}
// F11: ficha sem rolagem, em páginas; a lista de linhas quebra item a item
const paginarFicha = () => paginar($('ficha'), { sel: ':scope > :not(ul), :scope > ul > li', max: () => innerHeight * 0.42 })
$('c-ficha').addEventListener('toggle', () => { if ($('c-ficha').open) paginarFicha() })
addEventListener('resize', () => { paginarFicha(); paginar($('c-rota')); paginar($('assistente')) })

// ---------------- Mapa: círculo <-> tela cheia ----------------
const camadas = () => renderCamadas($('camadas'), estado)

function depoisDaTransicao(fn) { setTimeout(fn, TRANSICAO_MS) }

function instrucao(texto) {
  $('instrucao').hidden = !texto
  $('instrucao').textContent = texto ?? ''
}

function abrirMapa(modo) {
  estado.mapa = modo
  document.body.classList.add('mapa-aberto')
  $('mapa-box').removeAttribute('title')
  camadas()
  $('camadas').hidden = false
  $('coords').hidden = modo !== 'rota'
  mapa.setModo(modo)
  if (modo === 'rota') {
    if (!estado.rotaAtiva) {
      estado.rotaAtiva = true // card de rota só aparece com destino (a instrução já guia o clique)
      atualizarRota(estado.posicao, null, [])
    }
    if (!estado.destino) instrucao('clique no mapa ou digite as coordenadas do DESTINO')
  }
  depoisDaTransicao(() => { mapa.redimensionar(); mapa.centrar(estado.destino ?? estado.posicao, estado.rota) })
}

function fecharMapa() {
  estado.mapa = 'visor'
  aguardandoEscala = false
  document.body.classList.remove('mapa-aberto')
  $('mapa-box').title = 'Expandir mapa'
  for (const id of ['camadas', 'coords', 'leitura']) $(id).hidden = true
  instrucao(null)
  mapa.setModo('visor')
  let carga = Promise.resolve()
  if (estado.rotaAtiva && !estado.destino) cancelarRota()
  depoisDaTransicao(() => {
    mapa.redimensionar()
    mapa.centrar(estado.destino ?? estado.posicao, estado.rota)
    viewer?.resize()
  })
  return carga
}

$('mapa-box').addEventListener('click', () => { if (estado.mapa === 'visor') abrirMapa('explorar') })
$('btn-rota').addEventListener('click', () => abrirMapa('rota'))

// ---------------- Rota ----------------
const atualizarRota = iniciarRota($('c-rota'), {
  onCancelar: cancelarRota,
  onRotaAtiva: (r) => {
    estado.rota = r
    mapa.setRota(r)
    if (r && estado.mapa === 'visor') mapa.centrar(null, r)
    // rota calculada: a barra abre com panorama, fotos e ficha do DESTINO (não da origem)
    if (r && estado.destino && !mesmoPonto(estado.local, estado.destino)) {
      carregarLocal({ ...estado.destino, tipo: 'destino', rotulo: 'o destino da rota' })
    }
  },
  onAdicionarEscala: () => {
    if (estado.mapa !== 'rota') abrirMapa('rota')
    aguardandoEscala = true
    instrucao('clique no mapa para adicionar a PARADA')
  },
  onRemoverEscala: (i) => {
    estado.escalas.splice(i, 1)
    mapa.setEscalas(estado.escalas)
    atualizarRota(estado.posicao, estado.destino, estado.escalas)
  },
  onAbrirAlvo: async (alvo) => {
    if (!alvo?.lat) return
    if (estado.mapa !== 'visor') await fecharMapa()
    getFichaCientifica(alvo.lat, alvo.lon).then((f) => mostrarFicha(f, true), () => mostrarFicha('erro', true))
  },
})

function definirDestino(p) {
  if (!mesmoPonto(estado.local, p)) limparBarra() // dados do destino anterior saem já
  $('c-rota').hidden = false
  colapsarGrupo('g-rota', false)
  estado.destino = p
  estado.escalas = []
  mapa.setDestino(p)
  mapa.setEscalas([])
  instrucao(null)
  $('btn-rota').textContent = 'Editar rota'
  return atualizarRota(estado.posicao, p, [])
}

function cancelarRota() {
  Object.assign(estado, { rotaAtiva: false, destino: null, escalas: [], rota: null })
  aguardandoEscala = false
  mapa.setDestino(null)
  mapa.setEscalas([])
  mapa.setRota(null)
  $('c-rota').hidden = true
  $('btn-rota').textContent = 'Planejar rota'
  if (estado.mapa === 'rota') {
    estado.mapa = 'explorar'
    mapa.setModo('explorar')
    $('coords').hidden = true
    instrucao(null)
  }
  limparBarra()
}

// ---------------- Destino por coordenadas ----------------
function msg(texto) {
  $('coords-msg').hidden = !texto
  $('coords-msg').textContent = texto || ''
}

function lerCoords() {
  const lat = parseFloat($('lat').value)
  let lon = parseFloat($('lon').value)
  const latOk = Number.isFinite(lat) && lat >= -90 && lat <= 90
  const lonOk = Number.isFinite(lon)
  $('lat').setAttribute('aria-invalid', !latOk)
  $('lon').setAttribute('aria-invalid', !lonOk)
  if (!latOk || !lonOk) return null
  if (lon < 0) { lon += 360; $('lon').value = lon.toFixed(6) }
  return { lat, lon }
}

let janela = null // recorte do boxwork (/map): aviso quando o destino cai fora
fetch('/map').then((r) => r.json()).then((m) => (janela = m.window || null)).catch(() => {})

$('coords').addEventListener('submit', (e) => {
  e.preventDefault()
  const c = lerCoords()
  if (!c) return msg('Latitude entre −90 e 90; longitude numérica (°E).')
  const dentro = !janela || (c.lat >= janela.lat_min && c.lat <= janela.lat_max && c.lon >= janela.lon_min && c.lon <= janela.lon_max)
  msg(dentro ? null : 'Fora da janela do boxwork — resultados podem ser vazios.')
  definirDestino(c)
  mapa.centrar(c)
})

// ---------------- Clique no mapa expandido ----------------
let seqLeitura = 0
async function cliqueNoMapa(lat, lon) {
  const p = { lat, lon }
  if (estado.mapa === 'rota') {
    if (aguardandoEscala) {
      aguardandoEscala = false
      instrucao(null)
      estado.escalas.push(p)
      mapa.setEscalas(estado.escalas)
      return atualizarRota(estado.posicao, estado.destino, estado.escalas)
    }
    $('lat').value = lat.toFixed(6)
    $('lon').value = lon.toFixed(6)
    msg(null)
    return definirDestino(p)
  }
  return lerPonto(lat, lon) // explorar: leitura rápida de lat, lon e elevação
}

/** Escreve (e devolve) lat, lon e elevação do ponto na linha de leitura. */
async function lerPonto(lat, lon) {
  const meu = ++seqLeitura
  const el = $('leitura')
  el.hidden = false
  el.textContent = `${lat.toFixed(6)}° · ${lon.toFixed(6)}°E · consultando elevação…`
  try {
    const ponto = await getPoint(lat, lon)
    const rv = ponto.raster_values
    const ti = ponto.inercia_termica
    if (meu !== seqLeitura) return
    el.textContent = `${lat.toFixed(6)}° · ${lon.toFixed(6)}°E · ` + (rv.elevacao_m === null
      ? 'sem elevação (fora do DTM)'
      : `${rv.elevacao_m.toFixed(1)} m${rv.slope_deg !== null ? ` · ${rv.slope_deg.toFixed(1)}°` : ''}`)
      + (ti ? ` · TI ${ti.valor}` : '')
  } catch (e) {
    if (meu === seqLeitura) el.textContent = `${lat.toFixed(6)}° · ${lon.toFixed(6)}°E · ${e.message}`
  }
  return el.textContent
}

// ---------------- Camadas (delegação: o HTML é refeito a cada render) ----------------
$('camadas').addEventListener('click', (e) => {
  const id = e.target.closest('[data-toggle]')?.dataset.toggle
  if (!id) return
  const c = estado.camadas[id]
  c.visible = !c.visible
  mapa.setCamadaVisivel(id, c.visible)
  camadas()
})
$('camadas').addEventListener('input', (e) => {
  const id = e.target.dataset.opacidade
  if (!id) return
  estado.camadas[id].opacity = Number(e.target.value)
  mapa.setCamadaOpacidade(id, estado.camadas[id].opacity) // sem re-render: não roubar o foco do slider
})

// ---------------- Teclado ----------------
function voltar() {
  if (estado.mapa !== 'visor') fecharMapa()
  else fecharVisor()
}
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape' || !$('assistente').hidden) return // Esc do assistente é dele
  voltar()
})

// ---------------- F08: assistente ----------------
const assistente = iniciarAssistente($('assistente'), $('btn-assistente'), () => estado.local ?? estado.posicao, {
  // F11: digitado como comando de interface; confirmação no diálogo do navegador
  comando: async (texto) => {
    const r = await postComando(texto, contexto())
    if (!r.fala) return null
    if (!r.comando) return r.fala
    if (r.confirmar && !confirm(r.fala)) return 'Cancelado.'
    return (await executar(r.comando)).texto
  },
})

// F08 voz: "Ei Marvin, rota até …" ou pergunta falada; a origem é sempre a posição atual
iniciarVoz($('btn-voz'), $('voz-status'), {
  pontoAtual: () => estado.posicao,
  rota: (_origem, destino) => definirDestino({ ...destino, tipo: 'destino', rotulo: 'o destino da rota' }),
  perguntar: (texto) => {
    if ($('assistente').hidden) assistente.abrir(true)
    return assistente.enviar(texto, true)
  },
  executar,
  contexto,
})

// ---------------- F11: ações de cada bloco (catálogo em comandos.json) ----------------
const viewerAtivo = () => viewerFundo ?? viewer
const clicar = (sel) => { const b = $('c-rota').querySelector(sel); if (!b) return false; b.click() }
/** Campo do card de rota que só reage a 'change' (rota.js). */
function preencher(sel, valor) {
  const i = $('c-rota').querySelector(sel)
  if (!i) return 'Esse campo só aparece com a rota calculada.'
  i.value = valor
  i.dispatchEvent(new Event('change', { bubbles: true }))
}
function ligarCamada(camada, visivel, opacidade) {
  const c = estado.camadas[camada]
  c.visible = visivel
  if (opacidade !== undefined) { c.opacity = opacidade; mapa.setCamadaOpacidade(camada, opacidade) }
  mapa.setCamadaVisivel(camada, visivel)
  camadas()
}
registrar('m-A', {
  expandir: () => { if (estado.mapa !== 'visor') return 'Mapa já está aberto.'; abrirMapa('explorar') },
  recolher: () => { if (estado.mapa === 'visor') return 'Mapa já está recolhido.'; fecharMapa() },
  aproximar: ({ niveis }) => { mapa.zoom(niveis) },
  afastar: ({ niveis }) => { mapa.zoom(-niveis) },
  mover: ({ direcao }) => { mapa.mover(direcao) },
  centralizar: () => { mapa.centrar(estado.destino ?? estado.posicao, estado.rota) },
  ler: async () => {
    const c = mapa.centro()
    if (!c) return 'Mapa ainda não carregou.'
    if (estado.mapa === 'visor') abrirMapa('explorar')
    $('leitura').hidden = false
    falar((await lerPonto(c.lat, c.lon)).replaceAll('·', ',').replace('°E', ' graus leste'))
  },
})
registrar('m-B', {
  ligar: ({ camada }) => ligarCamada(camada, true),
  desligar: ({ camada }) => ligarCamada(camada, false),
  opacidade: ({ camada, valor }) => ligarCamada(camada, true, valor / 100),
})
registrar('m-C', {
  planejar: () => { abrirMapa('rota') },
  tipo: ({ tipo }) => clicar(`[data-tipo="${tipo}"]`),
  sol: ({ delta }) => clicar(`[data-sol-passo="${delta}"]`),
  alvo: () => clicar('[data-acao="alvo"]'),
  proxima: () => mudarPagina($('c-rota'), 1) || 'Rota: já está na última página.',
  anterior: () => mudarPagina($('c-rota'), -1) || 'Rota: já está na primeira página.',
  recolher: () => { colapsarGrupo('g-rota', true) },
  expandir: () => { colapsarGrupo('g-rota', false) },
  cancelar: () => { if (!estado.rotaAtiva) return 'Não há rota.'; cancelarRota() },
  destino_centro: () => {
    const c = mapa.centro()
    if (!c) return 'Mapa ainda não carregou.'
    if (estado.mapa !== 'rota') abrirMapa('rota')
    $('lat').value = c.lat.toFixed(6)
    $('lon').value = c.lon.toFixed(6)
    definirDestino(c)
  },
  parada: () => {
    const c = mapa.centro()
    if (!estado.destino) return 'Defina o destino antes da parada.'
    if (!c) return 'Mapa ainda não carregou.'
    estado.escalas.push(c)
    mapa.setEscalas(estado.escalas)
    atualizarRota(estado.posicao, estado.destino, estado.escalas)
  },
  remover_parada: ({ n }) => {
    if (!estado.escalas[n - 1]) return `Não há parada ${n}.`
    estado.escalas.splice(n - 1, 1)
    mapa.setEscalas(estado.escalas)
    atualizarRota(estado.posicao, estado.destino, estado.escalas)
  },
  ir_sol: ({ sol }) => preencher('[data-sol-eva]', sol),
  o2: ({ litros }) => preencher('[data-campo="capacidade-o2"]', litros),
  medicao: ({ sol, minima, maxima, pressao, dose }) => {
    const f = $('c-rota').querySelector('form[data-medir]')
    if (!f) return 'Abra uma rota com previsão carregada para registrar a medição.'
    Object.entries({ sol: Math.round(sol), temp_min_c: minima, temp_max_c: maxima, pressao_pa: pressao, dose_ugy_dia: dose ?? '' })
      .forEach(([k, v]) => { f.elements[k].value = v })
    f.requestSubmit()
  },
  apagar_medicao: () => clicar('[data-apagar-medicao]'),
})
registrar('m-D', {
  expandir: () => { if (!viewer) return 'Sem panorama aqui.'; if (!noVisor) expandir() },
  recolher: () => { if (!noVisor) return 'Panorama não está no visor.'; recolher() },
  girar: ({ direcao, graus }) => {
    const v = viewerAtivo()
    if (!v) return 'Sem panorama aqui.'
    if (direcao === 'esquerda' || direcao === 'direita') v.setYaw(v.getYaw() + (direcao === 'direita' ? graus : -graus))
    else v.setPitch(v.getPitch() + (direcao === 'cima' ? graus : -graus))
  },
  aproximar: () => { const v = viewerAtivo(); if (!v) return 'Sem panorama aqui.'; v.setHfov(v.getHfov() - 15) },
  afastar: () => { const v = viewerAtivo(); if (!v) return 'Sem panorama aqui.'; v.setHfov(v.getHfov() + 15) },
  centralizar: () => { const v = viewerAtivo(); if (!v) return 'Sem panorama aqui.'; v.setYaw(cfgPano.yaw) },
})
registrar('m-E', {
  abrir: ({ n }) => {
    const ft = fotosLista[fotosPag * FOTOS_POR_PAG + n - 1]
    if (!ft) return `Não há foto ${n} nesta página.`
    abrirFoto(ft)
  },
  proxima: () => {
    if ((fotosPag + 1) * FOTOS_POR_PAG >= fotosLista.length) return 'Fotos: já está na última página.'
    fotosPag++; renderFotos(1)
  },
  anterior: () => {
    if (fotosPag === 0) return 'Fotos: já está na primeira página.'
    fotosPag--; renderFotos(-1)
  },
  recolher: () => { colapsarGrupo('g-imagens', true) },
  expandir: () => { colapsarGrupo('g-imagens', false) },
})
registrar('m-F', {
  abrir: () => { if ($('c-ficha').hidden) return 'Sem ficha aberta.'; $('c-ficha').open = true },
  fechar: () => { $('c-ficha').open = false },
  proxima: () => mudarPagina($('ficha'), 1) || 'Ficha: já está na última página.',
  anterior: () => mudarPagina($('ficha'), -1) || 'Ficha: já está na primeira página.',
})
registrar('m-G', {
  abrir: () => { assistente.abrir(true) },
  fechar: () => { assistente.abrir(false) },
  proxima: () => mudarPagina($('assistente'), 1) || 'Assistente: não há resposta mais antiga.',
  anterior: () => mudarPagina($('assistente'), -1) || 'Assistente: já está na mais nova.',
  ouvir: () => {
    const b = $('assistente').querySelector('.h2g2-ass-item:not(.pag-fora) [data-ouvir]')
    if (!b) return 'Não há resposta para ouvir.'
    b.click()
  },
})
registrar('m-H', {
  fechar: () => { if ($('visor-fechar').hidden) return 'O visor já está vazio.'; fecharVisor() },
})
registrar('m-I', {
  definir: ({ lat, lon }) => {
    if (estado.mapa !== 'rota') abrirMapa('rota')
    $('lat').value = lat
    $('lon').value = lon
    $('coords').requestSubmit()
  },
})
registrar('m-J', {
  ler: () => { if ($('c-status').hidden) return 'Não há aviso.'; falar($('c-status').textContent.trim()) },
})
registrar('sis', {
  voltar: () => { if (!$('assistente').hidden) assistente.abrir(false); else voltar() },
  silencio: () => { speechSynthesis.cancel() },
  microfone: () => { if ($('btn-voz').getAttribute('aria-pressed') !== 'true') return 'Microfone já está desligado.'; $('btn-voz').click() },
  ajuda: () => { falar(descreverAbertos()) },
})
iniciarComandos().catch((e) => console.warn('catálogo de comandos indisponível:', e))

// ---------------- Carga inicial ----------------
getPosicao()
  .then((p) => {
    estado.posicao = { lat: p.lat, lon: p.lon, rotulo: 'a posição atual', fonte: p.rotulo, tipo: 'posicao' }
    mapa.setOrigem(estado.posicao)
    mapa.centrar(estado.posicao)
  })
  .catch((e) => card('c-status', `<p class="vazio erro">Sem posição: ${esc(e.message)}</p>`))

try {
  const metas = await getLayers()
  $('mapa-status').remove()
  mapa.criarMapa($('mapa'), metas, {
    onClick: cliqueNoMapa,
    onFechar: fecharMapa,
    onLoad: () => {
      if (estado.posicao) { mapa.setOrigem(estado.posicao); mapa.centrar(estado.posicao) }
    },
  })
} catch (e) {
  $('mapa-status').textContent = `sem mapa: ${e.message}`
}
