import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {PlaybackQueue} from '../static/playback.mjs';

function setup(getUserMedia=async()=>{throw Error('No device');}, audioOptions={}) {
  const html=readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
  const element=()=>({value:'',checked:true,textContent:'',children:[],replaceChildren(){this.children=[];},
    add(){},querySelector:()=>null,append(...children){this.children.push(...children);}});
  const nodes=new Map([...html.matchAll(/id="([^"]+)"/g)].map(([,id])=>[id,element()]));
  nodes.get('volume').value='80'; const sockets=[];
  class Socket {static OPEN=1;static CONNECTING=0;constructor(){this.readyState=1;sockets.push(this);}send(){}close(){this.readyState=3;}}
  const code=readFileSync(new URL('../static/app.js',import.meta.url),'utf8').replace(/^import .*;\r?\n/,'');
  vm.runInNewContext(code,{
    PlaybackQueue,WebSocket:Socket,location:{host:'127.0.0.1:8765',protocol:'http:'},
    document:{getElementById:id=>nodes.get(id),createElement:element},
    localStorage:{getItem:()=>null,setItem(){}},window:{addEventListener(){}},setInterval(){},clearInterval(){},
    Option:class {},navigator:{mediaDevices:{enumerateDevices:async()=>[],getUserMedia}},
    fetch:async url=>({ok:true,json:async()=>url==='/api/health'?{ollama:{available:true,model:'test'}}:[]}),
    ...audioOptions,
  });
  return {nodes,sockets,start(){nodes.get('start').onclick();sockets.at(-1).onopen();}};
}

test('late close from the old socket cannot stop a newly opened session',()=>{
  const {nodes,sockets,start}=setup();start();const old=sockets[0];
  nodes.get('stop').onclick();start();
  old.onclose();
  assert.equal(nodes.get('text').disabled,false);
  assert.equal(nodes.get('stop').disabled,false);
  assert.equal(nodes.get('start').disabled,true);
});

test('microphone permission resolving after stop/restart cannot attach to the new session',async()=>{
  let resolve;const pending=new Promise(done=>resolve=done);
  const track={stopped:false,stop(){this.stopped=true;}};
  const {nodes,start}=setup(()=>pending);start();
  const enabling=nodes.get('mic').onclick();
  nodes.get('stop').onclick();start();
  resolve({getTracks:()=>[track]});await enabling;
  assert.equal(track.stopped,true);
  assert.equal(nodes.get('ptt').disabled,true);
  assert.equal(nodes.get('mic').textContent,'Увімкнути мікрофон');
});

test('stopping during AudioWorklet loading does not reconnect a closed microphone',async()=>{
  let resolve;const loading=new Promise(done=>resolve=done);let connections=0;
  const track={stop(){this.stopped=true;}};
  const stream={getTracks:()=>[track],getAudioTracks:()=>[track]};
  class Context {
    constructor(){this.sampleRate=16000;this.state='running';this.audioWorklet={addModule:()=>loading};}
    async close(){this.state='closed';}
    async resume() { assert.notEqual(this.state,'closed'); }
    createMediaStreamSource(){connections++;return {connect(){},disconnect(){}};}
  }
  const {nodes,start}=setup(async()=>stream,{AudioContext:Context});start();
  const enabling=nodes.get('mic').onclick();await Promise.resolve();
  nodes.get('stop').onclick();resolve();await enabling;
  assert.equal(connections,0);assert.equal(track.stopped,true);
});
