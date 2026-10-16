import {PlaybackQueue} from './playback.mjs';
const $ = id => document.getElementById(id);
let ws, camera, microphone, context, worklet, source, timer;
let mediaEpoch = 0, micPending = false, cameraPending = false;
let cameraCanvas, cameraContext;
let flushId=0, pendingFlush=null, utteranceId=0;
function flushAudio(){
  if(!worklet)return Promise.resolve();
  return new Promise(resolve=>{const id=++flushId;const timeout=setTimeout(()=>{if(pendingFlush?.id===id)pendingFlush=null;resolve();},500);pendingFlush={id,done:()=>{clearTimeout(timeout);pendingFlush=null;resolve();}};worklet.port.postMessage({type:'flush',id});});
}
let currentTurn = 0, partial = null, recording = false, active = false;
let pendingText='', spokenText='', syncCurrent=true;
function resetTranscript(){partial=null;pendingText='';spokenText='';syncCurrent=$('voice').checked&&$('syncText').checked;}
function showResponse(text){if(!text)return;if(!partial)partial=message('');partial.textContent=text;$('messages').scrollTop=$('messages').scrollHeight;}
function revealResponse(){syncCurrent=false;showResponse(pendingText);}
try{const saved=localStorage.getItem('assistantVolume');if(saved!==null&&Number.isFinite(Number(saved)))$('volume').value=String(Math.max(0,Math.min(100,Number(saved))));}catch{}
try{const saved=localStorage.getItem('assistantRate');if(saved!==null&&Number.isFinite(Number(saved)))$('speechRate').value=String(Math.max(0.5,Math.min(2,Number(saved))));$('handsFree').checked=localStorage.getItem('assistantHandsFree')==='true';}catch{}
try{const saved=localStorage.getItem('assistantASR');$('asrModel').value=['small','turbo','parakeet'].includes(saved)?saved:'parakeet';}catch{}
function volume(){const value=Number($('volume').value);$('volumeValue').textContent=value+'%';playback.setVolume(value/100);try{localStorage.setItem('assistantVolume',String(value));}catch{}}
function speechRate(){const value=Number($('speechRate').value)||1;$('rateValue').textContent=value.toFixed(2)+'×';playback.setRate(value);try{localStorage.setItem('assistantRate',String(value));}catch{}}
function inputHint(){$('bargeIn').disabled=!$('handsFree').checked;$('inputHint').textContent=$('handsFree').checked?($('bargeIn').checked?'Розмова без кнопки: мікрофон слухає також під час відповіді. Використовуй навушники, щоб уникнути відлуння.':'Розмова без кнопки: відповідаю після паузи. Під час озвучування слухання призупинене; кнопка перериває відповідь.'):'Кнопка перериває відповідь. Під час озвучування фонове слухання призупинене.';}
const playback=new PlaybackQueue({
  createAudio(wav){const bytes=Uint8Array.from(atob(wav),c=>c.charCodeAt(0));const url=URL.createObjectURL(new Blob([bytes],{type:'audio/wav'}));return {audio:new Audio(url),dispose:()=>URL.revokeObjectURL(url)};},
  onPlaying:(value,turn)=>send({type:'playing',value,turn:turn??currentTurn}),
  onError:text=>{revealResponse();error(text);},getVolume:()=>Number($('volume').value)/100,getRate:()=>Number($('speechRate').value)||1,
  onChunk:(text,turn)=>{if(turn!==currentTurn||!syncCurrent)return;spokenText+=(spokenText?' ':'')+text;showResponse(spokenText);},
  onDrained:turn=>{if(turn===currentTurn)showResponse(pendingText);}
});
$('volume').oninput=volume;volume();
$('speechRate').oninput=speechRate;speechRate();inputHint();
const send = data => { if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(data)); };
function error(text) { $('error').textContent = text; $('error').hidden = false; }
$('error').onclick = () => $('error').hidden = true;
try{const saved=localStorage.getItem('assistantASRLanguage');$('asrLanguage').value=['uk','ru','fr'].includes(saved)?saved:'auto';}catch{}
const ttsLanguages=['auto','uk','ru','fr','en','de','es','it','pl','pt','ja','ko','ar','bg','cs','da','el','et','fi','hi','hr','hu','id','lt','lv','nl','ro','sk','sl','sv','tr','vi'];
for(const [id,choices,fallback] of [['ttsBackend',['supertonic','piper'],'supertonic'],['ttsVoice',['M1','M2','M3','M4','M5'],'M1'],['ttsLanguage',ttsLanguages,'auto']]){
  let saved;try{saved=localStorage.getItem('assistant'+id);}catch{}$(id).value=choices.includes(saved)?saved:fallback;
}
function voiceControls(){const old=$('ttsBackend').value==='piper';$('ttsVoice').disabled=old;$('ttsLanguage').disabled=old;}
voiceControls();
function settings() { send({type:'settings', initiative:$('initiative').checked, chatty:$('chatty').checked, memory:$('remember').checked, voice:$('voice').checked, hands_free:$('handsFree').checked, barge_in:$('bargeIn').checked, asr_model:$('asrModel').value, asr_language:$('asrLanguage').value, tts_backend:$('ttsBackend').value, tts_language:$('ttsLanguage').value, tts_voice:$('ttsVoice').value}); }
function message(text, role='assistant', proactive=false) {
  $('messages').querySelector('.welcome')?.remove();
  const el = document.createElement('div'); el.className = `message ${role} ${proactive?'proactive':''}`;
  const label = document.createElement('small'); label.textContent = role==='user'?'ТИ':proactive?'ПОРУЧ · СПОСТЕРЕЖЕННЯ':'ПОРУЧ';
  const body = document.createElement('span'); body.textContent = text; el.append(label,body);
  $('messages').append(el);
  while($('messages').children.length>100)$('messages').firstElementChild.remove();
  $('messages').scrollTop = $('messages').scrollHeight; return body;
}
function stopAudio() {
  playback.stop();
}
async function refreshMemory() {
  try {
    const [facts,summaries]=await Promise.all([fetch('/api/memory'),fetch('/api/summaries')]);
    if(!facts.ok||!summaries.ok)throw Error('Не вдалося прочитати пам’ять');
    renderMemory(await facts.json());renderSummaries(await summaries.json());
  } catch(e){error(e.message);}
}
function renderSummaries(summaries){
  $('summaries').replaceChildren();
  if(!summaries.length){$('summaries').textContent='Ще немає підсумків.';return;}
  for(const s of summaries){
    const row=document.createElement('div');row.className='fact';
    const body=document.createElement('div');body.className='fact-text';
    const text=document.createElement('div');text.textContent=s.text;
    const meta=document.createElement('small');meta.textContent=new Date(s.updated).toLocaleString('uk-UA')+' · '+s.source;
    body.append(text,meta);
    const del=document.createElement('button');del.textContent='×';del.title='Видалити підсумок';
    del.onclick=async()=>{try{stopAudio();const r=await fetch('/api/summaries/'+s.id,{method:'DELETE'});if(!r.ok)throw Error('Не вдалося видалити підсумок');renderSummaries(await r.json());}catch(e){error(e.message);}};
    row.append(body,del);$('summaries').append(row);
  }
}
function renderMemory(facts) {
  $('memories').replaceChildren();
  if(!facts.length){$('memories').textContent='Ще немає збережених фактів.';return;}
  for(const f of facts){
    const row=document.createElement('div');row.className='fact';
    const text=document.createElement('div');text.className='fact-text';
    const value=document.createElement('div');value.textContent=f.text;
    const meta=document.createElement('small');meta.textContent=`${f.topic} · ${f.active?'актуально':'неактуально'} · ${Math.round(f.confidence*100)}%`;
    text.append(value,meta);text.title=f.source+' · '+new Date(f.updated).toLocaleString('uk-UA');
    text.onclick=()=>{$('topic').value=f.topic;$('fact').value=f.text;$('factKind').value=f.kind;$('factActive').checked=!!f.active;};
    const del=document.createElement('button');del.textContent='×';del.title='Забути факт';
    del.onclick=async()=>{try{stopAudio();const r=await fetch('/api/memory/'+f.id,{method:'DELETE'});if(!r.ok)throw Error('Не вдалося видалити факт');await refreshMemory();}catch(e){error(e.message);}};
    row.append(text,del);$('memories').append(row);
  }
}
$('memoryForm').onsubmit=async e=>{e.preventDefault();try{stopAudio();const r=await fetch('/api/memory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:$('topic').value,text:$('fact').value,kind:$('factKind').value,active:$('factActive').checked})});if(!r.ok)throw Error('Не вдалося зберегти факт');await refreshMemory();$('memoryForm').reset();}catch(e){error(e.message);}};
$('profileForm').onsubmit=async e=>{e.preventDefault();try{stopAudio();const r=await fetch('/api/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:$('profileName').value,address:$('profileAddress').value,room:$('profileRoom').value,interests:$('profileInterests').value})});if(!r.ok)throw Error('Не вдалося зберегти знайомство');await refreshMemory();$('onboarding').open=false;$('profileForm').reset();}catch(e){error(e.message);}};
function state(enabled){active=enabled;for(const id of ['stop','text','send','camera','mic'])$(id).disabled=!enabled;$('start').disabled=enabled;$('ptt').disabled=!enabled||!microphone;}
async function devices(){
  const all=await navigator.mediaDevices.enumerateDevices();
  for(const [id,kind]of [['cameraDevice','videoinput'],['micDevice','audioinput']]){
    const selected=$(id).value;$(id).replaceChildren(new Option('Типовий пристрій',''));
    all.filter(d=>d.kind===kind).forEach((d,i)=>$(id).add(new Option(d.label||`Пристрій ${i+1}`,d.deviceId)));$(id).value=selected;
  }
}
$('start').onclick=()=>{
  if(ws && (ws.readyState===WebSocket.OPEN || ws.readyState===WebSocket.CONNECTING))return;
  $('start').disabled=true;const socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);ws=socket;
  socket.onopen=()=>{if(ws!==socket)return;state(true);currentTurn=0;resetTranscript();settings();if($('handsFree').checked&&!microphone)enableMicrophone();};
  socket.onmessage=e=>{if(ws!==socket)return;const m=JSON.parse(e.data);
    if(m.type==='status')$('status').textContent=m.text;
    if(m.type==='error'){revealResponse();error(m.text);}
    if(m.type==='cancel'){currentTurn=m.turn;resetTranscript();stopAudio();}
    if(m.type==='user')message(m.text,'user');
    if(m.type==='heard')$('heard').textContent='Почув: '+m.text;
    if(m.type==='delta'&&m.turn===currentTurn){pendingText+=m.text;if(!syncCurrent)showResponse(pendingText);}
    if(m.type==='reply'&&m.turn===currentTurn){if(m.proactive){resetTranscript();partial=message('','assistant',true);}pendingText=m.text;if(!syncCurrent)showResponse(pendingText);if(m.seconds)$('status').textContent=`Відповідь: ${m.seconds} с`;}
    if(m.type==='audio_start'&&m.turn===currentTurn&&active&&$('voice').checked)playback.start(m.turn);
    if(m.type==='audio'&&m.turn===currentTurn&&active&&$('voice').checked)playback.enqueue(m.wav,m.turn,m.text);
    if(m.type==='audio_end')playback.finish(m.turn);
    if(m.type==='scene'&&camera){$('scene').textContent=m.text;$('sceneTime').textContent=new Date(m.at).toLocaleTimeString('uk-UA');}
    if(m.type==='memory')renderMemory(m.facts);
    if(m.type==='preferences'&&typeof m.chatty==='boolean')$('chatty').checked=m.chatty;
    if(m.type==='summaries')renderSummaries(m.summaries);
  };
  socket.onerror=()=>{if(ws===socket)error('Немає зв’язку з локальним сервером.');};
  socket.onclose=()=>{if(ws!==socket)return;ws=null;cleanup();$('status').textContent='Сесію завершено';};
};
function cameraOff(){camera?.getTracks().forEach(t=>{t.onended=null;t.stop();});camera=null;clearInterval(timer);$('video').srcObject=null;$('cameraPlaceholder').hidden=false;$('camera').textContent='Увімкнути камеру';send({type:'camera_off'});$('scene').textContent='Камера вимкнена.';$('sceneTime').textContent='';}
function sendFrame(){
  const video=$('video');
  if(!active||!camera||!video.videoWidth||ws?.readyState!==WebSocket.OPEN||ws.bufferedAmount>100000)return false;
  cameraCanvas??=document.createElement('canvas');cameraContext??=cameraCanvas.getContext('2d');
  const scale=Math.min(1,640/Math.max(video.videoWidth,video.videoHeight));
  cameraCanvas.width=Math.round(video.videoWidth*scale);cameraCanvas.height=Math.round(video.videoHeight*scale);
  cameraContext.drawImage(video,0,0,cameraCanvas.width,cameraCanvas.height);
  send({type:'frame',image:cameraCanvas.toDataURL('image/jpeg',.7).split(',')[1]});return true;
}
async function micOff(){utteranceId++;pendingFlush?.done();microphone?.getTracks().forEach(t=>{t.onended=null;t.stop();});microphone=null;source?.disconnect();source=null;worklet?.disconnect();worklet=null;const oldContext=context;context=null;send({type:'mic_off'});recording=false;$('ptt').textContent='Утримуй, щоб звернутися';$('mic').textContent='Увімкнути мікрофон';$('ptt').disabled=true;if(oldContext&&oldContext.state!=='closed')await oldContext.close().catch(()=>{});}
function cleanup(){mediaEpoch++;state(false);cameraOff();micOff();stopAudio();}
$('stop').onclick=()=>{send({type:'stop'});const socket=ws;ws=null;socket?.close();cleanup();$('status').textContent='Сесію завершено';};
$('camera').onclick=async()=>{if(camera){cameraOff();return;}if(cameraPending||!active)return;cameraPending=true;const epoch=mediaEpoch;try{
  const stream=await navigator.mediaDevices.getUserMedia({video:{deviceId:$('cameraDevice').value?{exact:$('cameraDevice').value}:undefined,width:{ideal:640},height:{ideal:480}},audio:false});
  if(!active||epoch!==mediaEpoch){stream.getTracks().forEach(t=>t.stop());return;}
  camera=stream;$('video').srcObject=stream;await $('video').play();
  if(camera!==stream||!active)return;
  $('cameraPlaceholder').hidden=true;$('camera').textContent='Вимкнути камеру';
  $('scene').textContent='Камера працює. Очікую опису кадру…';$('sceneTime').textContent='';
  stream.getVideoTracks().forEach(track=>{track.onended=()=>{if(camera===stream){cameraOff();error('Камеру від’єднано або доступ припинено.');}};});
  await devices().catch(()=>{});
  if(camera!==stream||!active)return;
  sendFrame();timer=setInterval(sendFrame,1000);
}catch(e){if(epoch===mediaEpoch){cameraOff();error('Камера: '+e.message);}}finally{cameraPending=false;}};
async function enableMicrophone(){if(!active||microphone||micPending)return;micPending=true;const epoch=mediaEpoch;let stream,ownContext;try{
  stream=await navigator.mediaDevices.getUserMedia({audio:{deviceId:$('micDevice').value?{exact:$('micDevice').value}:undefined,echoCancellation:true,noiseSuppression:true,channelCount:1},video:false});
  if(!active||epoch!==mediaEpoch){stream.getTracks().forEach(t=>t.stop());return;}microphone=stream;
  ownContext=new AudioContext({sampleRate:16000});context=ownContext;if(ownContext.sampleRate!==16000)throw Error('Потрібна підтримка аудіоконтексту 16 кГц');
  await ownContext.audioWorklet.addModule('/static/audio-worklet.js');
  if(!active||epoch!==mediaEpoch||microphone!==stream)return;
  await ownContext.resume();
  if(!active||epoch!==mediaEpoch||microphone!==stream)return;
  source=ownContext.createMediaStreamSource(stream);worklet=new AudioWorkletNode(ownContext,'capture');
  worklet.port.onmessage=e=>{if(epoch!==mediaEpoch)return;if(e.data?.type==='flushed'){if(pendingFlush?.id===e.data.id)pendingFlush.done();return;}if(active&&ws?.readyState===1&&ws.bufferedAmount<64000)ws.send(e.data);};source.connect(worklet);worklet.connect(ownContext.destination);
  stream.getAudioTracks().forEach(track=>{track.onended=()=>{if(microphone===stream){micOff();error('Мікрофон від’єднано або доступ припинено.');}};});
  $('mic').textContent='Вимкнути мікрофон';$('ptt').disabled=false;await devices();
}catch(e){if(epoch===mediaEpoch){await micOff();error('Мікрофон: '+e.message);}}finally{micPending=false;if(epoch!==mediaEpoch||microphone!==stream){stream?.getTracks().forEach(t=>t.stop());if(ownContext&&ownContext.state!=='closed')await ownContext.close().catch(()=>{});}}}
$('mic').onclick=async()=>{if(microphone)await micOff();else await enableMicrophone();};
$('handsFree').onchange=()=>{settings();inputHint();try{localStorage.setItem('assistantHandsFree',String($('handsFree').checked));}catch{}if($('handsFree').checked&&active&&!microphone)enableMicrophone();};
$('bargeIn').onchange=()=>{settings();inputHint();};
$('asrModel').onchange=()=>{settings();try{localStorage.setItem('assistantASR',$('asrModel').value);}catch{}};
$('ptt').onpointerdown=e=>{if(!active||!microphone)return;e.preventDefault();$('ptt').setPointerCapture(e.pointerId);utteranceId++;recording=true;stopAudio();send({type:'ptt_start'});$('ptt').textContent='Говори… відпусти для відповіді';};
async function release(){if(!recording)return;recording=false;const id=utteranceId;await flushAudio();if(!active||!microphone||id!==utteranceId)return;sendFrame();send({type:'ptt_end'});$('ptt').textContent='Утримуй, щоб звернутися';}
$('ptt').onpointerup=release;$('ptt').onpointercancel=release;
$('chat').onsubmit=e=>{e.preventDefault();const text=$('text').value.trim();if(text){stopAudio();sendFrame();send({type:'text',text});$('text').value='';}};
for(const id of ['initiative','chatty','remember','voice'])$(id).onchange=()=>{settings();if(!$('voice').checked){revealResponse();stopAudio();}};
$('syncText').onchange=()=>{if(!$('syncText').checked)revealResponse();};
window.addEventListener('beforeunload',()=>{send({type:'stop'});camera?.getTracks().forEach(t=>t.stop());microphone?.getTracks().forEach(t=>t.stop());});
async function health(){try{const h=await(await fetch('/api/health')).json();const processor={gpu:' · GPU',cpu:' · CPU — повільно',mixed:' · CPU/GPU'}[h.ollama.processor]||'';$('health').textContent=`${h.ollama.available?'●':'○'} ${h.ollama.display_name||h.ollama.model}${processor} · ${h.whisper?'●':'○'} Розпізнавання · ${h.voice?'●':'○'} Голос`;}catch{$('health').textContent='Сервер недоступний';}}
health();setInterval(health,30000);refreshMemory();devices().catch(()=>{});

$('asrLanguage').onchange=()=>{settings();try{localStorage.setItem('assistantASRLanguage',$('asrLanguage').value);}catch{}};

for(const id of ['ttsBackend','ttsVoice','ttsLanguage'])$(id).onchange=()=>{voiceControls();settings();try{localStorage.setItem('assistant'+id,$(id).value);}catch{}};
