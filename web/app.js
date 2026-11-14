// Orquestração (antes App.tsx): estado num objeto, cada handler chama os renders afetados.
import { getConditions, getLayers, getNomenclature, getRoverPhotos } from './api.js'
import { TOGGLEABLE_LAYERS } from './layers.js'
import * as mapa from './map.js'
import { abrirLightbox } from './ui/lightbox.js'
import { renderCamadas, renderCondicoes, renderHud } from './ui/paineis.js'
import { abrirPonto, fecharPonto } from './ui/ponto.js'
import { iniciarRota } from './ui/rota.js'
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
}

const hud = () => renderHud($('hud'), estado)
const camadas = () => renderCamadas($('camadas'), { ...estado, nFotos: estado.fotos.length })

// ---- modo rota ----
const atualizarRota = iniciarRota($('rota'), {
  onFechar: alternarRota,
  onReset: () => marcarRota(null, null),
  onRotaAtiva: mapa.setRota,
})

function marcarRota(origem, destino) {
  estado.origem = origem
  estado.destino = destino
  mapa.setOrigem(origem)
  mapa.setDestino(destino)
  mapa.setModo(!estado.modoRota ? 'point' : !origem ? 'pick-origin' : !destino ? 'pick-destination' : 'pick-origin')
  // instrução grande, cor do marcador que vai aparecer (verde=origem, vermelho=destino)
  const instr = $('instrucao')
  instr.hidden = !estado.modoRota || Boolean(origem && destino)
  instr.classList.toggle('destino', Boolean(origem))
  instr.textContent = !origem ? 'PASSO 1/2 · clique no mapa para marcar a ORIGEM' : 'PASSO 2/2 · clique no mapa para marcar o DESTINO'
  if (estado.modoRota) atualizarRota(origem, destino)
}

function alternarRota() {
  estado.modoRota = !estado.modoRota
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

// ---- carga inicial ----
hud()
camadas()
renderCondicoes($('condicoes'), { conditions: null, error: null })

getConditions()
  .then((c) => {
    estado.sol = c.sol
    renderCondicoes($('condicoes'), { conditions: c, error: null })
    hud()
  })
  .catch((e) => renderCondicoes($('condicoes'), { conditions: null, error: String(e) }))

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
