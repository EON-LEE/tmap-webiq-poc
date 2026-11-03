class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.resetFrame();
  }
  resetFrame() {
    this.frame = new ArrayBuffer(4800);
    this.view = new DataView(this.frame);
    this.offset = 0;
  }
  process(inputs, outputs) {
    for (const output of outputs) for (const channel of output) channel.fill(0);
    const channels = inputs[0];
    if (!channels?.length) return true;
    for (let i = 0; i < channels[0].length; i++) {
      let value = 0;
      for (const channel of channels) value += channel[i];
      value = Math.max(-1, Math.min(1, value / channels.length));
      this.view.setInt16(this.offset * 2, Math.round(value * (value < 0 ? 32768 : 32767)), true);
      if (++this.offset === 2400) {
        this.port.postMessage(this.frame, [this.frame]);
        this.resetFrame();
      }
    }
    return true;
  }
}
registerProcessor("pcm-capture", PcmCapture);
