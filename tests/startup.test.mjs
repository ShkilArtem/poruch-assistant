import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {PlaybackQueue} from '../static/playback.mjs';

test('page initialization installs the Start handler and starts health checks',async()=>{
  const html=readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
  const nodes=new Map([...html.matchAll(/id="([^"]+)"/g)].map(([,id])=>[id,{
    value:id==='volume'?'80':'',checked:true,textContent:'',replaceChildren(){},add(){}
  }]));
  const requests=[];
  const code=readFileSync(new URL('../static/app.js',import.meta.url),'utf8').replace(/^import .*;\r?\n/,'');
  vm.runInNewContext(code,{
    PlaybackQueue,
    document:{getElementById(id){assert.ok(nodes.has(id),'Missing page element: '+id);return nodes.get(id);}},
    localStorage:{getItem:key=>key==='assistantRate'?'1.4':null,setItem(){}},
    WebSocket:{OPEN:1},window:{addEventListener(){}},setInterval(){},
    Option:class {},navigator:{mediaDevices:{enumerateDevices:async()=>[]}},
    fetch:async url=>{requests.push(url);return {ok:true,json:async()=>url==='/api/health'?{
      ollama:{available:true,model:'test',processor:'gpu'},whisper:true,voice:true
    }:[]};}
  });
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(typeof nodes.get('start').onclick,'function');
  assert.ok(requests.includes('/api/health'));
  assert.match(nodes.get('health').textContent,/GPU/);
  assert.equal(nodes.get('speechRate').value,'1.4');
  assert.equal(nodes.get('rateValue').textContent,'1.40×');
  assert.equal(nodes.get('ttsBackend').value,'supertonic');
  assert.equal(nodes.get('ttsVoice').value,'M1');
  assert.equal(nodes.get('ttsLanguage').value,'auto');
  nodes.get('ttsBackend').value='piper';nodes.get('ttsBackend').onchange();
  assert.equal(nodes.get('ttsLanguage').disabled,true);
  assert.equal(nodes.get('ttsVoice').disabled,true);
});

test('camera start clears both disabled-camera labels and handles disconnection',async()=>{
  const html=readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
  const nodes=new Map([...html.matchAll(/id="([^"]+)"/g)].map(([,id])=>[id,{
    value:id==='volume'?'80':'',checked:true,textContent:'',replaceChildren(){},add(){},play:async()=>{}
  }]));
  const sockets=[],sent=[];
  const track={stop(){this.stopped=true;}};
  const stream={getTracks:()=>[track],getVideoTracks:()=>[track]};
  const code=readFileSync(new URL('../static/app.js',import.meta.url),'utf8').replace(/^import .*;\r?\n/,'');
  class Socket{static OPEN=1;constructor(){this.readyState=1;this.bufferedAmount=0;sockets.push(this);}send(data){sent.push(JSON.parse(data));}}
  vm.runInNewContext(code,{
    PlaybackQueue,WebSocket:Socket,location:{host:'127.0.0.1:8765'},
    document:{getElementById:id=>nodes.get(id),createElement:()=>({getContext:()=>({drawImage(){}}),toDataURL:()=> 'data:image/jpeg;base64,fresh-frame'})},
    localStorage:{getItem:()=>null,setItem(){}},window:{addEventListener(){}},setInterval(){},clearInterval(){},
    Option:class {},navigator:{mediaDevices:{enumerateDevices:async()=>[],getUserMedia:async()=>stream}},
    fetch:async url=>({ok:true,json:async()=>url==='/api/health'?{ollama:{available:true,model:'test'}}:[]})
  });
  nodes.get('start').onclick();sockets[0].onopen();
  nodes.get('video').videoWidth=640;nodes.get('video').videoHeight=480;
  await nodes.get('camera').onclick();
  assert.equal(nodes.get('cameraPlaceholder').hidden,true);
  assert.match(nodes.get('scene').textContent,/Камера працює/);
  assert.equal(nodes.get('video').srcObject,stream);
  nodes.get('text').value='Що ти бачиш?';
  nodes.get('chat').onsubmit({preventDefault(){}});
  assert.equal(sent.at(-2).type,'frame');
  assert.equal(sent.at(-2).image,'fresh-frame');
  assert.equal(sent.at(-1).type,'text');
  track.onended();
  assert.equal(nodes.get('cameraPlaceholder').hidden,false);
  assert.equal(nodes.get('video').srcObject,null);
  assert.match(nodes.get('scene').textContent,/Камера вимкнена/);
  assert.equal(track.stopped,true);
  const css=readFileSync(new URL('../static/style.css',import.meta.url),'utf8');
  assert.match(css,/\[hidden\]\s*\{\s*display\s*:\s*none\s*!important/);
});

test('voice captions do not reveal the entire generated answer before audio playback',async()=>{
  const html=readFileSync(new URL('../static/index.html',import.meta.url),'utf8');
  const element=()=>({value:'',checked:true,textContent:'',children:[],replaceChildren(){this.children=[];},
    add(){},querySelector:()=>null,append(...children){this.children.push(...children);}});
  const nodes=new Map([...html.matchAll(/id="([^"]+)"/g)].map(([,id])=>[id,element()]));
  nodes.get('volume').value='80';const sockets=[],sounds=[];
  class Socket{static OPEN=1;constructor(){this.readyState=1;sockets.push(this);}send(){}}
  class Audio{constructor(){sounds.push(this);}play(){return Promise.resolve();}pause(){}}
  const code=readFileSync(new URL('../static/app.js',import.meta.url),'utf8').replace(/^import .*;\r?\n/,'');
  vm.runInNewContext(code,{
    PlaybackQueue,WebSocket:Socket,Audio,Blob:class {},URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},atob:()=> 'abc',
    location:{host:'127.0.0.1:8765'},document:{getElementById:id=>nodes.get(id),createElement:element},
    localStorage:{getItem:()=>null,setItem(){}},window:{addEventListener(){}},setInterval(){},
    Option:class {},navigator:{mediaDevices:{enumerateDevices:async()=>[]}},
    fetch:async url=>({ok:true,json:async()=>url==='/api/health'?{ollama:{available:true,model:'test'}}:[]})
  });
  nodes.get('start').onclick();sockets[0].onopen();
  const receive=data=>sockets[0].onmessage({data:JSON.stringify(data)});
  receive({type:'delta',turn:0,text:'Перша фраза. Друга фраза.'});
  receive({type:'reply',turn:0,text:'Перша фраза. Друга фраза.'});
  assert.equal(nodes.get('messages').children.length,0);
  receive({type:'audio_start',turn:0});
  receive({type:'audio',turn:0,wav:'one',text:'Перша фраза.'});await Promise.resolve();
  const body=nodes.get('messages').children[0].children[1];assert.equal(body.textContent,'Перша фраза.');
  receive({type:'audio',turn:0,wav:'two',text:'Друга фраза.'});receive({type:'audio_end',turn:0});
  assert.equal(body.textContent,'Перша фраза.');
  sounds[0].onended();await Promise.resolve();assert.equal(body.textContent,'Перша фраза. Друга фраза.');
});
