import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

test('capture flush sends the unfinished audio tail before acknowledgement',()=>{
  let Capture;const output=[];
  class Processor{constructor(){this.port={postMessage:data=>output.push(data)};}}
  vm.runInNewContext(readFileSync(new URL('../static/audio-worklet.js',import.meta.url),'utf8'),{
    AudioWorkletProcessor:Processor,Float32Array,registerProcessor:(name,ctor)=>{Capture=ctor;}
  });
  const capture=new Capture();const samples=Float32Array.from([0.1,0.2,0.3]);
  capture.process([[samples]]);assert.equal(output.length,0);
  capture.port.onmessage({data:{type:'flush',id:7}});
  assert.deepEqual(new Float32Array(output[0]),samples);
  assert.equal(output[1].type,'flushed');assert.equal(output[1].id,7);
  capture.port.onmessage({data:{type:'flush',id:8}});
  assert.equal(output.length,3);assert.equal(output[2].type,'flushed');
});
