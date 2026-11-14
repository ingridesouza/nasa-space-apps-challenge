// Lightbox único (fotos próximas + pins do rastro do rover). Fica no <body>:
// dentro de painel com backdrop-filter, position:fixed vira relativo ao painel.
// Tamanho fixo com letterbox -- câmeras do Curiosity têm proporções bem diferentes.
import { esc } from './util.js'

let el = null
let fotos = []
let i = 0

function fechar() {
  el?.remove()
  el = null
  window.removeEventListener('keydown', teclas)
}

function ir(delta) {
  i = (i + delta + fotos.length) % fotos.length
  render()
}

function teclas(e) {
  if (e.key === 'Escape') fechar()
  if (e.key === 'ArrowRight') ir(1)
  if (e.key === 'ArrowLeft') ir(-1)
}

function render() {
  const f = fotos[i]
  const varias = fotos.length > 1
  el.innerHTML = `
    <div class="h2g2-lightbox-corpo">
      ${varias ? '<button class="h2g2-lightbox-nav h2g2-mono" data-ir="-1" aria-label="Foto anterior">‹</button>' : ''}
      <div class="h2g2-lightbox-img" data-fechar><img src="${esc(f.url)}" alt="${esc(f.camera)} · sol ${esc(f.sol)}"></div>
      ${varias ? '<button class="h2g2-lightbox-nav h2g2-mono" data-ir="1" aria-label="Próxima foto">›</button>' : ''}
    </div>
    <div class="h2g2-mono h2g2-lightbox-legenda">
      ${f.caption ? `${esc(f.caption)} · ` : ''}sol ${esc(f.sol)} · ${esc(f.camera)}
      ${varias ? `<span class="h2g2-dim"> · ${i + 1}/${fotos.length}</span>` : ''}
    </div>`
}

/** lista: [{url, sol, camera, caption?}] */
export function abrirLightbox(lista, indice) {
  if (!lista[indice]) return
  fechar()
  fotos = lista
  i = indice
  el = document.createElement('div')
  el.className = 'h2g2-lightbox'
  el.addEventListener('click', (e) => {
    const nav = e.target.closest('[data-ir]')
    if (nav) return ir(Number(nav.dataset.ir))
    // clique no fundo ou na própria foto fecha; legenda não
    if (e.target === el || e.target.closest('[data-fechar]')) fechar()
  })
  document.body.appendChild(el)
  window.addEventListener('keydown', teclas)
  render()
}
