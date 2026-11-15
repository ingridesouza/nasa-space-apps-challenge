// F11: carrossel de páginas no lugar da rolagem. Mede os blocos do card, agrupa
// o que cabe na altura máxima e esconde o resto; ‹ 1/3 › troca de página (clique ou voz).
// Bloco com .pag-fixo aparece em todas as páginas (ex.: "cancelar rota").
const est = new WeakMap() // el -> {pag, total, max, sel}
const NAV_PX = 36

const alturaDe = (b) => {
  const cs = getComputedStyle(b)
  return b.getBoundingClientRect().height + parseFloat(cs.marginTop) + parseFloat(cs.marginBottom)
}

/** el: contêiner que não é recriado; max: px ou () => px; sel: seletor dos blocos (relativo a el). */
export function paginar(el, { max, sel } = {}) {
  const s = est.get(el) ?? { pag: 0, total: 1, sel: ':scope > *' }
  if (max !== undefined) s.max = max
  if (sel !== undefined) s.sel = sel
  est.set(el, s)
  el.querySelector(':scope > .pag-nav')?.remove()
  const blocos = [...el.querySelectorAll(s.sel)]
  for (const b of blocos) b.classList.remove('pag-fora')
  const limite = typeof s.max === 'function' ? s.max() : s.max
  const fixos = blocos.filter((b) => b.classList.contains('pag-fixo'))
  const moveis = blocos.filter((b) => !b.classList.contains('pag-fixo'))
  const gap = parseFloat(getComputedStyle(moveis[0]?.parentElement ?? el).rowGap) || 0
  const alturas = moveis.map((b) => alturaDe(b) + gap)
  const soma = alturas.reduce((a, h) => a + h, 0)
  const fixo = fixos.reduce((a, b) => a + alturaDe(b) + gap, 0)
  // card escondido mede 0: fica tudo visível e repagina quando aparecer
  if (!soma || !limite || soma + fixo <= limite) { s.total = 1; s.pag = 0; return s }
  const util = Math.max(limite - fixo - NAV_PX, 60)
  const paginas = [[]]
  let acc = 0
  moveis.forEach((b, i) => {
    if (acc + alturas[i] > util && paginas.at(-1).length) { paginas.push([]); acc = 0 }
    paginas.at(-1).push(b)
    acc += alturas[i]
  })
  s.total = paginas.length
  s.pag = Math.min(Math.max(s.pag, 0), s.total - 1)
  paginas.forEach((p, i) => { if (i !== s.pag) for (const b of p) b.classList.add('pag-fora') })
  const nav = document.createElement('div')
  nav.className = 'pag-nav'
  nav.innerHTML = `<button type="button" class="fotos-seta" data-pag="-1" aria-label="Página anterior" ${s.pag === 0 ? 'disabled' : ''}>‹</button>
    <span class="fotos-pag">${s.pag + 1} / ${s.total}</span>
    <button type="button" class="fotos-seta" data-pag="1" aria-label="Próxima página" ${s.pag === s.total - 1 ? 'disabled' : ''}>›</button>`
  nav.addEventListener('click', (e) => {
    const d = e.target.closest('[data-pag]')?.dataset.pag
    if (!d) return
    e.stopPropagation()
    mudarPagina(el, Number(d))
  })
  el.appendChild(nav)
  return s
}

/** ±1 página. false = não havia para onde ir. */
export function mudarPagina(el, delta) {
  const s = est.get(el)
  if (!s) return false
  paginar(el) // remede: o card pode ter mudado desde a última vez
  const novo = Math.min(Math.max(s.pag + delta, 0), s.total - 1)
  if (novo === s.pag) return false
  s.pag = novo
  paginar(el)
  return true
}

export function irPagina(el, n) {
  const s = est.get(el)
  if (s) s.pag = n
}
