const $=id=>document.getElementById(id);
const phrasesByLanguage={uk:[
  'Мене звати Артем, і я працюю над домашнім роботом.',
  'Розкажи, що ти бачиш на камері, але не вигадуй деталей.',
  'Я не питаю, чого ти боїшся. Я питаю, що ти бачиш.',
  'Завтра о пів на восьму потрібно вийти з дому.',
  'На столі лежать навушники, книжка та синя чашка.',
  'У мене було сім яблук, я віддав два й купив ще чотири.',
  'Поясни різницю між пам’яттю комп’ютера та відеопам’яттю.',
  'Не описуй кімнату, краще допоможи мені сформулювати ідею.',
  'Я хочу, щоб ти припустив, у якому приміщенні я перебуваю.',
  'Вимкни дрібні коментарі, але реагуй на суттєві зміни.',
  'Купи двісті п’ятдесят грамів сиру та півтора літра молока.',
  'Швидкість читання потрібно збільшити до півтора раза.'
],ru:['Меня зовут Артём, и я работаю над домашним роботом.','Расскажи, что ты видишь на камере, но не выдумывай деталей.','Завтра в половине восьмого нужно выйти из дома.','На столе лежат наушники, книга и синяя чашка.'],fr:["Je travaille sur un robot qui peut discuter avec moi.","Décris ce que tu vois sans inventer de détails.","Demain, je dois partir à sept heures et demie.","Sur la table, il y a un livre et une tasse bleue."]};
let phrases=phrasesByLanguage.uk;
let index=0, stream, context, worklet, source, chunks=[], count=0, recording=false, busy=false, timer, flushed;
let previewUrl;
const reports=[];
function preview(samples){
  const buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer);
  const ascii=(offset,text)=>{for(let i=0;i<text.length;i++)view.setUint8(offset+i,text.charCodeAt(i));};
  ascii(0,'RIFF');view.setUint32(4,36+samples.length*2,true);ascii(8,'WAVE');ascii(12,'fmt ');
  view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);ascii(36,'data');view.setUint32(40,samples.length*2,true);
  let energy=0,clipped=0;for(let i=0;i<samples.length;i++){const x=samples[i];energy+=x*x;clipped+=Math.abs(x)>=0.99;view.setInt16(44+i*2,Math.round(Math.max(-1,Math.min(1,x))*32767),true);}
  if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=URL.createObjectURL(new Blob([buffer],{type:'audio/wav'}));$('preview').src=previewUrl;$('preview').hidden=false;
  const rms=Math.sqrt(energy/samples.length);$('audioLevel').textContent=rms<0.005?'Запис дуже тихий. Прослухай його й перевір вибраний мікрофон.':clipped/samples.length>0.01?'Є ознаки перевантаження мікрофона. Прослухай запис і зменш підсилення.':'Можна прослухати саме той запис, який отримали всі моделі.';
}
function showPhrase(){$('reference').value=phrases[index];$('phraseNumber').textContent=`${index+1}/${phrases.length}`;}
async function devices(){const selected=$('testMic').value;const list=await navigator.mediaDevices.enumerateDevices();$('testMic').replaceChildren(new Option('Типовий мікрофон',''));list.filter(d=>d.kind==='audioinput').forEach((d,i)=>$('testMic').add(new Option(d.label||`Мікрофон ${i+1}`,d.deviceId)));$('testMic').value=selected;}
async function cleanup(){clearTimeout(timer);recording=false;stream?.getTracks().forEach(t=>t.stop());source?.disconnect();worklet?.disconnect();if(context&&context.state!=='closed')await context.close();stream=context=worklet=source=null;}
async function start(){
  busy=true;$('record').disabled=true;$('nextPhrase').disabled=true;$('testLanguage').disabled=true;
  try{
    stream=await navigator.mediaDevices.getUserMedia({audio:{deviceId:$('testMic').value?{exact:$('testMic').value}:undefined,echoCancellation:true,noiseSuppression:true,channelCount:1},video:false});
    context=new AudioContext({sampleRate:16000});if(context.sampleRate!==16000)throw Error('Потрібен аудіоконтекст 16 кГц.');
    await context.audioWorklet.addModule('/static/audio-worklet.js');await context.resume();
    chunks=[];count=0;source=context.createMediaStreamSource(stream);worklet=new AudioWorkletNode(context,'capture');
    worklet.port.onmessage=e=>{if(e.data?.type==='flushed'){flushed?.();return;}if(!recording)return;const chunk=new Float32Array(e.data);const remaining=240000-count;if(remaining>0){chunks.push(chunk.slice(0,remaining));count+=Math.min(chunk.length,remaining);}};
    source.connect(worklet);worklet.connect(context.destination);recording=true;busy=false;
    $('record').disabled=false;$('record').textContent='Зупинити й порівняти';$('testStatus').textContent='Запис іде — прочитай фразу, потім натисни «Зупинити й порівняти».';
    timer=setTimeout(stop,15000);await devices();
  }catch(error){await cleanup();busy=false;$('record').disabled=false;$('nextPhrase').disabled=false;$('testLanguage').disabled=false;$('testStatus').textContent=error.message;}
}
async function stop(){
  if(!recording||busy)return;busy=true;clearTimeout(timer);$('record').disabled=true;
  const reference=$('reference').value.trim();
  await new Promise(resolve=>{const timeout=setTimeout(resolve,500);flushed=()=>{clearTimeout(timeout);resolve();};worklet.port.postMessage({type:'flush',id:1});});flushed=null;
  await cleanup();
  try{
    if(!count||!reference)throw Error('Потрібні запис і точний текст прочитаної фрази.');
    const samples=new Float32Array(count);let offset=0;for(const chunk of chunks){samples.set(chunk,offset);offset+=chunk.length;}
    preview(samples);
    const bytes=new Uint8Array(samples.buffer);let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
    $('testStatus').textContent='Порівнюю завантажені моделі на одному записі…';
    const response=await fetch('/api/asr/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({audio:btoa(binary),reference,language:$('testLanguage').value})});
    const result=await response.json();if(!response.ok)throw Error(result.detail||'Не вдалося порівняти моделі.');
    reports.push(result);$('exportResults').disabled=false;
    const block=document.createElement('div');block.className='message';const title=document.createElement('p');title.textContent='Прочитано: '+reference;block.append(title);
    for(const item of result.results){const text=document.createElement('p');text.textContent=`${item.model}: ${item.text||'(мовлення не розпізнано)'}\nПомилки слів: ${Math.round(item.wer*100)}% · без завантаження: ${item.warm_seconds} с · завантаження та перший прохід: ${item.load_and_first_seconds} с`;block.append(text);}
    $('testResults').prepend(block);$('testStatus').textContent=`Готово. Перевірено фраз: ${reports.length}. Менший відсоток помилок — кращий результат.`;
  }catch(error){$('testStatus').textContent=error.message;}
  finally{chunks=[];count=0;busy=false;$('record').disabled=false;$('record').textContent='Записати фразу';$('nextPhrase').disabled=false;$('testLanguage').disabled=false;}
}
$('testLanguage').onchange=()=>{if(recording||busy)return;phrases=phrasesByLanguage[$('testLanguage').value];index=0;showPhrase();};
$('record').onclick=()=>{if(recording)stop();else if(!busy)start();};
$('nextPhrase').onclick=()=>{index=(index+1)%phrases.length;showPhrase();};
$('exportResults').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(reports,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='asr-comparison.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
window.addEventListener('beforeunload',()=>stream?.getTracks().forEach(t=>t.stop()));
showPhrase();devices().catch(()=>{});
