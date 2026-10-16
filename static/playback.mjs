// Keep microphone suppression active across synthesis gaps and queued WAV chunks.
export class PlaybackQueue {
  constructor({createAudio, onPlaying, onError, getVolume, getRate=()=>1, onChunk=()=>{}, onDrained=()=>{}}) {
    Object.assign(this, {createAudio, onPlaying, onError, getVolume, getRate, onChunk, onDrained});
    this.items=[];this.current=null;this.turn=null;this.streaming=false;this.epoch=0;
  }
  start(turn) {
    this.stop();this.turn=turn;this.streaming=true;this.drained=false;this.onPlaying(true,turn);
  }
  enqueue(wav,turn,text='') {
    if(turn!==this.turn)return;
    this.items.push({wav,text});this.pump();
  }
  finish(turn) {
    if(turn!==this.turn)return;
    this.streaming=false;this.idle();
  }
  idle() {
    if(!this.streaming&&!this.current&&!this.items.length){this.onPlaying(false,this.turn);if(!this.drained){this.drained=true;this.onDrained(this.turn);}}
  }
  pump() {
    if(this.current||!this.items.length){this.idle();return;}
    const epoch=this.epoch;
    const item=this.items.shift();const entry=this.createAudio(item.wav);this.current=entry;
    entry.audio.volume=this.getVolume();
    entry.audio.preservesPitch=true;entry.audio.playbackRate=this.getRate();
    const complete=()=>{
      if(epoch!==this.epoch||this.current!==entry)return;
      entry.audio.onended=null;entry.audio.onerror=null;entry.dispose();this.current=null;this.pump();
    };
    entry.audio.onended=complete;
    entry.audio.onerror=()=>{this.onError('Не вдалося відтворити аудіофрагмент.');complete();};
    Promise.resolve(entry.audio.play()).then(()=>{
      if(epoch===this.epoch&&this.current===entry)this.onChunk(item.text,this.turn);
    }).catch(error=>{
      if(epoch!==this.epoch||this.current!==entry)return;
      this.onError('Не вдалося відтворити голос: '+error.message);complete();
    });
  }
  setVolume(value) {if(this.current)this.current.audio.volume=value;}
  setRate(value) {if(this.current)this.current.audio.playbackRate=value;}
  stop() {
    const turn=this.turn;this.epoch++;this.items=[];this.streaming=false;this.drained=true;
    if(this.current){const entry=this.current;this.current=null;entry.audio.onended=null;entry.audio.onerror=null;entry.audio.pause();entry.dispose();}
    this.turn=null;this.onPlaying(false,turn);
  }
}
