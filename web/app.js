// Orquestração (antes App.tsx): estado num objeto, cada handler chama os renders afetados.
import { apagarMedicao, getConditions, getLayers, getNomenclature, getPrevisao, getRoverPhotos, postMedicao } from './api.js'
import { TOGGLEABLE_LAYERS } from './layers.js'
import * as mapa from './map.js'
import { abrirLightbox } from './ui/lightbox.js'
import { renderCamadas, renderCondicoes, renderHud } from './ui/paineis.js'
import { renderPrevisao } from './ui/previsao.js'
import { abrirPonto, fecharPonto } from './ui/ponto.js'
import { iniciarAssistente } from './ui/agente.js'
import { iniciarRota, setSolEva } from './ui/rota.js'
import { esc } from './ui/util.js'

const $ = (id) => document.getElementById(id)

const estado = {
  ponto: null,
  sol: null,
  zoom: null,
  nomenclatura: [],
  fotos: [],
  camadas: Object.fromEntries(TOGGLEABLE_LAYERS.map((l) => [l.id, { visible: l.defaultVisible, opacity: l.defaultOpacity }])),
  fotosVisiveis: true,
  trilhaVisivel: false, // trilha do Curiosity entra desligada, como Relevo/THEMIS
  modoRota: false,
  origem: null,
  destino: null,
  escalas: [], // paradas intermediárias, em ordem, entre origem e destino
}
let aguardandoEscala = false // true logo depois de "+ adicionar parada no caminho"

const hud = () => {
  renderHud($('hud'), estado)
  if (!$('assistente').hidden) assistente?.render()
}
// F08: assistente responde sobre o ponto aberto ou, sem ponto, sobre a base
const assistente = iniciarAssistente($('assistente'), $('btn-assistente'), () => estado.ponto)
const camadas = () => renderCamadas($('camadas'), { ...estado, nFotos: estado.fotos.length })

// ---- modo rota ----
const atualizarRota = iniciarRota($('rota'), {
  onFechar: alternarRota,
  onReset: () => marcarRota(null, null),
  onRotaAtiva: mapa.setRota,
  onAdicionarEscala: () => {
    aguardandoEscala = true
    mapa.setModo('pick-destination')
    const instr = $('instrucao')
    instr.hidden = false
    instr.classList.add('destino')
    instr.textContent = 'clique no mapa para adicionar a PARADA'
  },
  onRemoverEscala: (i) => {
    estado.escalas.splice(i, 1)
    mapa.setEscalas(estado.escalas)
    atualizarRota(estado.origem, estado.destino, estado.escalas)
  },
})

function marcarRota(origem, destino) {
  estado.origem = origem
  estado.destino = destino
  estado.escalas = []
  mapa.setOrigem(origem)
  mapa.setDestino(destino)
  mapa.setEscalas([])
  mapa.setModo(!estado.modoRota ? 'point' : !origem ? 'pick-origin' : !destino ? 'pick-destination' : 'pick-origin')
  // instrução grande, cor do marcador que vai aparecer (verde=origem, vermelho=destino)
  const instr = $('instrucao')
  instr.hidden = !estado.modoRota || Boolean(origem && destino)
  instr.classList.toggle('destino', Boolean(origem))
  instr.textContent = !origem ? 'PASSO 1/2 · clique no mapa para marcar a ORIGEM' : 'PASSO 2/2 · clique no mapa para marcar o DESTINO'
  if (estado.modoRota) atualizarRota(origem, destino, estado.escalas)
}

function alternarRota() {
  estado.modoRota = !estado.modoRota
  aguardandoEscala = false
  const btn = $('btn-rota')
  btn.classList.toggle('on', estado.modoRota)
  btn.textContent = estado.modoRota ? '✕ cancelar rota' : '◇ planejar rota'
  $('rota').hidden = !estado.modoRota
  fecharPonto($('ponto'))
  mapa.limparPonto()
  estado.ponto = null
  hud()
  marcarRota(null, null)
  if (!estado.modoRota) mapa.setRota(null)
}

function cliqueNoMapa(lat, lon) {
  const p = { lat, lon }
  if (!estado.modoRota) {
    estado.ponto = p
    hud()
    abrirPonto($('ponto'), p, estado.nomenclatura, () => {
      fecharPonto($('ponto'))
      mapa.limparPonto()
      estado.ponto = null
      hud()
    })
  } else if (aguardandoEscala) {
    aguardandoEscala = false
    estado.escalas.push(p)
    mapa.setEscalas(estado.escalas)
    mapa.setModo('pick-origin')
    $('instrucao').hidden = true
    atualizarRota(estado.origem, estado.destino, estado.escalas)
  } else if (!estado.origem) marcarRota(p, null)
  else if (!estado.destino) marcarRota(estado.origem, p)
  else marcarRota(p, null) // terceiro clique recomeça a escolha
}

// ---- painel de camadas (delegação: o HTML é refeito a cada render) ----
$('camadas').addEventListener('click', (e) => {
  const id = e.target.closest('[data-toggle]')?.dataset.toggle
  if (!id) return
  if (id === 'fotos') {
    estado.fotosVisiveis = !estado.fotosVisiveis
    mapa.setFotosVisiveis(estado.fotosVisiveis)
  } else if (id === 'trilha') {
    estado.trilhaVisivel = !estado.trilhaVisivel
    mapa.setTrilhaVisivel(estado.trilhaVisivel)
  } else {
    const c = estado.camadas[id]
    c.visible = !c.visible
    mapa.setCamadaVisivel(id, c.visible)
  }
  camadas()
})
$('camadas').addEventListener('input', (e) => {
  const id = e.target.dataset.opacidade
  if (!id) return
  estado.camadas[id].opacity = Number(e.target.value)
  mapa.setCamadaOpacidade(id, estado.camadas[id].opacity) // sem re-render: não roubar o foco do slider
})
$('btn-rota').addEventListener('click', alternarRota)
// F07 modo traje: mesma tela, só o essencial pro visor (CSS .traje em style.css)
$('btn-traje').addEventListener('click', (e) => {
  e.currentTarget.setAttribute('aria-pressed', document.body.classList.toggle('traje'))
})

// ---- carga inicial ----
hud()
camadas()
const cond = { conditions: null, error: null }
const condicoes = () => renderCondicoes($('condicoes'), cond)
condicoes()

getConditions()
  .then((c) => {
    estado.sol = c.sol
    cond.conditions = c
    condicoes()
    hud()
    // teste previsto × medido sobre o sol das condições (PDF da F06)
    getPrevisao({ sol: c.sol }).then((v) => { prev.validacao = v; previsao() }).catch(() => {})
  })
  .catch((e) => {
    cond.error = String(e)
    condicoes()
  })

// ---- F06: faixa de previsão (sol da EVA; janela padrão de 2 h) ----
const DURACAO_PADRAO_MIN = 120
const prev = { previsao: null, validacao: null, solEva: null, carregando: true }
const previsao = () => renderPrevisao($('previsao'), prev)
let pedidoPrev = 0
async function carregarPrevisao(sol) {
  const meu = ++pedidoPrev
  prev.carregando = true
  if (sol) prev.solEva = sol
  previsao()
  const p = await getPrevisao({ duracao_min: DURACAO_PADRAO_MIN, ...(sol && { sol }) }).catch(() => null)
  if (meu !== pedidoPrev) return // trocou de sol no meio
  Object.assign(prev, { previsao: p, carregando: false, solEva: p?.sol ?? prev.solEva })
  previsao()
  if (sol) setSolEva(sol)
}
carregarPrevisao(null)
$('previsao').addEventListener('change', (e) => {
  if (!e.target.matches('[data-sol-eva]')) return
  const sol = Number(e.target.value)
  if (Number.isInteger(sol) && sol >= 1) carregarPrevisao(sol)
})
$('previsao').addEventListener('click', async (e) => {
  const passo = Number(e.target.closest('[data-sol-passo]')?.dataset.solPasso)
  if (passo && prev.solEva) return carregarPrevisao(prev.solEva + passo)
  const apagar = e.target.closest('[data-apagar-medicao]')?.dataset.apagarMedicao
  if (apagar) {
    await apagarMedicao(apagar)
    prev.msgMedicao = `medição do sol ${apagar} apagada`
    carregarPrevisao(prev.solEva)
  }
})
// medição do habitat: vira a base da previsão, sem a Terra
$('previsao').addEventListener('submit', async (e) => {
  if (!e.target.matches('[data-medir]')) return
  e.preventDefault()
  const dados = Object.fromEntries([...new FormData(e.target)].filter(([, v]) => v !== '').map(([k, v]) => [k, Number(v)]))
  try {
    const m = await postMedicao(dados)
    prev.msgMedicao = `medição do sol ${m.sol} salva: as previsões seguintes partem dela`
  } catch (err) {
    prev.msgMedicao = err.message
  }
  carregarPrevisao(prev.solEva)
})

// lista pequena; falha silenciosa não impede o resto
getNomenclature().then((n) => (estado.nomenclatura = n)).catch(() => {})

try {
  const metas = await getLayers()
  $('status').remove()
  $('tint').hidden = false
  mapa.criarMapa($('mapa'), metas, {
    onClick: cliqueNoMapa,
    onZoom: (z) => {
      estado.zoom = z
      hud()
    },
    onPhotoClick: (foto) => {
      const lista = estado.fotos.map((p) => ({ url: p.url, sol: p.sol, camera: p.camera, caption: `${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}` }))
      abrirLightbox(lista, estado.fotos.findIndex((p) => p.url === foto.url))
    },
    onLoad: () => {
      // "rastro do rover" -- pins nas posições reais das fotos
      getRoverPhotos()
        .then((f) => {
          estado.fotos = f
          mapa.setFotos(f)
          camadas()
        })
        .catch(() => {})
    },
  })
} catch (e) {
  $('status').innerHTML = `<span style="color:var(--danger)">Não consegui falar com a API (${esc(e.message)}). Ela está rodando?</span>`
}
