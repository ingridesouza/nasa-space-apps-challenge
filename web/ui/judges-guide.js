// Guide for judges: opens a short how-to of the voice system (native <dialog>, Esc closes it)
const dialog = document.getElementById('judges-guide')
document.getElementById('btn-judges').addEventListener('click', (e) => {
  e.currentTarget.blur() // otherwise "hold space to talk" clicks the button again
  dialog.showModal()
})
dialog.addEventListener('click', (e) => {
  if (e.target === dialog || e.target.closest('[data-close]')) dialog.close() // backdrop or ✕
})
// Esc belongs to the dialog: keep app.js from also closing the map/viewer
dialog.addEventListener('keydown', (e) => { if (e.key === 'Escape') e.stopPropagation() })
