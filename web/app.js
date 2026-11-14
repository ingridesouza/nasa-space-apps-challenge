// H2G2 · orquestração do front. Visor (F03/F04) em tela cheia; mapa (F01) num círculo
// que expande; rota (F02 + F06) num card; assistente (F08) no topo.
// A posição atual vem do rastreador (simulado em /api/posicao) e é a origem da rota.
import {
  getFichaCientifica, getFotosPerto, getLayers, getPanorama,
  getPoint, getPosicao,
} from './api.js'
import { TOGGLEABLE_LAYERS } from './layers.js'
import * as mapa from './map.js'
import { iniciarAssistente } from './ui/agente.js'
import { renderCamadas } from './ui/camadas.js'
import { iniciarRota } from './ui/rota.js'
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

// barra fechada e travada (sem toggle) até haver destino com rota calculada
function limparBarra() {
  seqLocal++
  estado.local = null
  ultimo = null
  limparPano()
  fecharFoto()
  mapa.setPanorama(null)
  for (const id of ['c-status', 'c-fotos', 'c-ficha']) $(id).hidden = true
  $('flutuante-toggle').hidden = true
  colapsarBarra(false)
  $('flutuante').hidden = $('c-rota').hidden
}

const mesmoPonto = (a, b) => a && b && a.lat === b.lat && a.lon === b.lon

function carregando() {
  for (const id of ['c-pano', 'c-fotos', 'c-ficha']) $(id).hidden = true
  $('flutuante-toggle').hidden = false
  const primeira = $('flutuante').hidden
  if (primeira) colapsarBarra(true) // nasce transparente e faz fade-in
  posicionarToggle()
  if (primeira) requestAnimationFrame(() => requestAnimationFrame(() => colapsarBarra(false)))
}

function card(id, html) { $(id).innerHTML = html; $(id).hidden = false; $('flutuante').hidden = false }

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
  $('pano-rotulo').innerHTML = `${esc(p.rotulo)} · ${esc(p.credito)}` +
    (p.page_url ? ` · <a href="${esc(p.page_url)}" target="_blank" rel="noopener">NASA</a>` : '')
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

// barra da direita: colapsa/expande
function colapsarBarra(c) {
  $('flutuante').classList.toggle('colapsada', c)
  $('flutuante-toggle').textContent = c ? '‹' : '›'
  $('flutuante-toggle').title = c ? 'Expandir barra' : 'Recolher barra'
  $('flutuante-toggle').setAttribute('aria-expanded', String(!c))
  $('fichas').classList.toggle('colapsada', c)
  posicionarToggle()
}
// botão fica à esquerda do primeiro card (largura variável); recolhido, vai para a borda
function posicionarToggle() {
  const t = $('flutuante-toggle'), s = $('c-status').hidden ? $('c-rota') : $('c-status')
  const colap = $('flutuante').classList.contains('colapsada')
  t.style.right = mobile() ? '' : (colap || s.hidden) ? '20px' : (20 + s.offsetWidth + 8) + 'px'
}
// fichas ancoradas na base do bloco de fotos (ou topo da barra no mobile), crescem para cima
function posicionarFichas() {
  const f = $('fichas'), fl = $('flutuante')
  if (fl.hidden) return
  const ref = mobile() || $('c-fotos').hidden ? fl.getBoundingClientRect() : $('c-fotos').getBoundingClientRect()
  f.style.bottom = (mobile() ? innerHeight - ref.top + 8 : Math.max(20, innerHeight - ref.bottom)) + 'px'
}
{
  const ro = new ResizeObserver(() => { posicionarFichas(); posicionarToggle() })
  for (const id of ['flutuante', 'c-rota', 'c-status', 'c-pano', 'c-fotos']) ro.observe($(id))
  addEventListener('resize', () => { posicionarFichas(); posicionarToggle() })
  $('flutuante').addEventListener('scroll', posicionarFichas)
}
$('flutuante-toggle').addEventListener('click', () => colapsarBarra(!$('flutuante').classList.contains('colapsada')))

// visor ganha um 2º viewer (mesma imagem, yaw atual); o preview continua no painel
function expandir() {
  if (!viewer) return
  colapsarBarra(true)
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
  colapsarBarra(false)
}
$('pano-expandir').addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); noVisor ? recolher() : expandir() })

// ---------------- Fotos ----------------
const FOTOS_POR_PAG = 4
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
    b.innerHTML = `<img loading="lazy" src="${esc(ft.thumb)}" alt=""><p>${ft.distancia_m} m · ${esc(ft.instrument)}</p>`
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
  $('flutuante').hidden = false
  requestAnimationFrame(posicionarFichas)
}

// ---------------- Mapa: círculo <-> tela cheia ----------------
const camadas = () => renderCamadas($('camadas'), estado)

function depoisDaTransicao(fn) { setTimeout(fn, TRANSICAO_MS) }

function instrucao(texto) {
  $('instrucao').hidden = !texto
  $('instrucao').textContent = texto ?? ''
}

// card de rota: aberto no mapa, recolhido no visor (deixa ver os dados do destino)
function rotaAberta(aberta) {
  const d = $('c-rota').querySelector('details.rota-corpo')
  if (d) d.open = aberta
}

function abrirMapa(modo) {
  estado.mapa = modo
  rotaAberta(true)
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
  rotaAberta(false)
  let carga = Promise.resolve()
  if (estado.rotaAtiva && !estado.destino) cancelarRota()
  depoisDaTransicao(() => {
    mapa.redimensionar()
    mapa.centrar(estado.destino ?? estado.posicao, estado.rota)
    viewer?.resize()
  })
  return carga
}

$('btn-expandir').addEventListener('click', () => abrirMapa('explorar'))
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
  $('flutuante').hidden = false
  estado.destino = p
  estado.escalas = []
  mapa.setDestino(p)
  mapa.setEscalas([])
  instrucao(null)
  $('btn-rota').textContent = 'Editar rota'
  atualizarRota(estado.posicao, p, [])
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
  // explorar: leitura rápida de lat, lon e elevação
  const meu = ++seqLeitura
  const el = $('leitura')
  el.hidden = false
  el.textContent = `${lat.toFixed(6)}° · ${lon.toFixed(6)}°E · consultando elevação…`
  try {
    const rv = (await getPoint(lat, lon)).raster_values
    if (meu !== seqLeitura) return
    el.textContent = `${lat.toFixed(6)}° · ${lon.toFixed(6)}°E · ` + (rv.elevacao_m === null
      ? 'sem elevação (fora do DTM)'
      : `${rv.elevacao_m.toFixed(1)} m${rv.slope_deg !== null ? ` · ${rv.slope_deg.toFixed(1)}°` : ''}`)
  } catch (e) {
    if (meu === seqLeitura) el.textContent = `${lat.toFixed(6)}° · ${lon.toFixed(6)}°E · ${e.message}`
  }
}

// ---------------- Camadas (delegação: o HTML é refeito a cada render) ----------------
$('camadas').addEventListener('click', (e) => {
  if (e.target.closest('[data-minimizar]')) return fecharMapa()
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
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape' || !$('assistente').hidden) return // Esc do assistente é dele
  if (estado.mapa !== 'visor') fecharMapa()
  else fecharVisor()
})

// ---------------- F08: assistente ----------------
iniciarAssistente($('assistente'), $('btn-assistente'), () => estado.local ?? estado.posicao)

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
    onLoad: () => {
      if (estado.posicao) { mapa.setOrigem(estado.posicao); mapa.centrar(estado.posicao) }
    },
  })
} catch (e) {
  $('mapa-status').textContent = `sem mapa: ${e.message}`
}
