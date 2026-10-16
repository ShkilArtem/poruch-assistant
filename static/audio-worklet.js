class Capture extends AudioWorkletProcessor {
  constructor() {
    super(); this.buffer = new Float32Array(2048); this.offset = 0;
    this.port.onmessage=e=>{
      if(e.data.type==='flush'){
        if(this.offset){const tail=this.buffer.slice(0,this.offset);this.port.postMessage(tail.buffer,[tail.buffer]);this.offset=0;}
        this.port.postMessage({type:'flushed',id:e.data.id});
      }
    };
  }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (channel) for (const sample of channel) {
      this.buffer[this.offset++] = sample;
      if (this.offset === this.buffer.length) {
        this.port.postMessage(this.buffer.buffer, [this.buffer.buffer]);
        this.buffer = new Float32Array(2048); this.offset = 0;
      }
    }
    return true;
  }
}
registerProcessor('capture', Capture);
