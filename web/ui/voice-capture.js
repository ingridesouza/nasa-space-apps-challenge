// F08 voice: AudioWorklet that only forwards each microphone frame (128 samples) to voice.js.
registerProcessor('h2g2-capture', class extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0]
    if (channel) this.port.postMessage(channel.slice(0))
    return true
  }
})
