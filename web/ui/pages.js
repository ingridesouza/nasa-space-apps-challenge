// F11: page carousel instead of scrolling. Measures the card blocks, groups what fits in the
// maximum height and hides the rest; ‹ 1/3 › changes page (click or voice).
// A block with .page-fixed shows on every page (e.g. "cancel route").
const states = new WeakMap() // el -> {page, total, max, sel}
const NAV_PX = 36

const heightOf = (b) => {
  const cs = getComputedStyle(b)
  return b.getBoundingClientRect().height + parseFloat(cs.marginTop) + parseFloat(cs.marginBottom)
}

/** el: container that is not recreated; max: px or () => px; sel: selector of the blocks (relative to el). */
export function paginate(el, { max, sel } = {}) {
  const s = states.get(el) ?? { page: 0, total: 1, sel: ':scope > *' }
  if (max !== undefined) s.max = max
  if (sel !== undefined) s.sel = sel
  states.set(el, s)
  el.querySelector(':scope > .page-nav')?.remove()
  const blocks = [...el.querySelectorAll(s.sel)]
  for (const b of blocks) b.classList.remove('page-out')
  const limit = typeof s.max === 'function' ? s.max() : s.max
  const fixed = blocks.filter((b) => b.classList.contains('page-fixed'))
  const movable = blocks.filter((b) => !b.classList.contains('page-fixed'))
  const gap = parseFloat(getComputedStyle(movable[0]?.parentElement ?? el).rowGap) || 0
  const heights = movable.map((b) => heightOf(b) + gap)
  const sum = heights.reduce((a, h) => a + h, 0)
  const fixedH = fixed.reduce((a, b) => a + heightOf(b) + gap, 0)
  // a hidden card measures 0: everything stays visible and repaginates when it shows up
  if (!sum || !limit || sum + fixedH <= limit) { s.total = 1; s.page = 0; return s }
  const usable = Math.max(limit - fixedH - NAV_PX, 60)
  const pages = [[]]
  let acc = 0
  movable.forEach((b, i) => {
    if (acc + heights[i] > usable && pages.at(-1).length) { pages.push([]); acc = 0 }
    pages.at(-1).push(b)
    acc += heights[i]
  })
  s.total = pages.length
  s.page = Math.min(Math.max(s.page, 0), s.total - 1)
  pages.forEach((p, i) => { if (i !== s.page) for (const b of p) b.classList.add('page-out') })
  const nav = document.createElement('div')
  nav.className = 'page-nav'
  nav.innerHTML = `<button type="button" class="photos-arrow" data-page="-1" aria-label="Previous page" ${s.page === 0 ? 'disabled' : ''}>‹</button>
    <span class="photos-page">${s.page + 1} / ${s.total}</span>
    <button type="button" class="photos-arrow" data-page="1" aria-label="Next page" ${s.page === s.total - 1 ? 'disabled' : ''}>›</button>`
  nav.addEventListener('click', (e) => {
    const d = e.target.closest('[data-page]')?.dataset.page
    if (!d) return
    e.stopPropagation()
    changePage(el, Number(d))
  })
  el.appendChild(nav)
  return s
}

/** ±1 page. false = there was nowhere to go. */
export function changePage(el, delta) {
  const s = states.get(el)
  if (!s) return false
  paginate(el) // re-measure: the card may have changed since the last time
  const next = Math.min(Math.max(s.page + delta, 0), s.total - 1)
  if (next === s.page) return false
  s.page = next
  paginate(el)
  return true
}

export function goToPage(el, n) {
  const s = states.get(el)
  if (s) s.page = n
}
