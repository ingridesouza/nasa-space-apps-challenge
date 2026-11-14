// F08 voz: AudioWorklet que só repassa cada quadro do microfone (128 amostras) para voz.js.
registerProcessor('h2g2-captura', class extends AudioWorkletProcessor {
  process(inputs) {
    const canal = inputs[0]?.[0]
    if (canal) this.port.postMessage(canal.slice(0))
    return true
  }
})
