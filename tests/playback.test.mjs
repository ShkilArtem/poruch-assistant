import test from 'node:test';
import assert from 'node:assert/strict';
import {PlaybackQueue} from '../static/playback.mjs';

function fixture(){
  const created=[],states=[];
  const player=new PlaybackQueue({
    createAudio(wav){const entry={wav,disposed:false,audio:{play:()=>Promise.resolve(),pause(){this.paused=true;}},dispose(){this.disposed=true;}};created.push(entry);return entry;},
    onPlaying:(value,turn)=>states.push({value,turn}),onError:()=>{},getVolume:()=>0.8
  });
  return {player,created,states};
}

test('chunks play sequentially and microphone stays muted across synthesis gaps',()=>{
  const {player,created,states}=fixture();player.start(1);states.length=0;
  player.enqueue('one',1);player.enqueue('two',1);
  assert.equal(created.length,1);
  created[0].audio.onended();assert.equal(created.length,2);
  assert.equal(created[0].disposed,true);
  created[1].audio.onended();assert.deepEqual(states,[]);
  player.enqueue('three',1);player.finish(1);
  assert.deepEqual(states,[]);
  created[2].audio.onended();assert.deepEqual(states,[{value:false,turn:1}]);
});

test('interruption discards queued chunks and ignores old completion callbacks',()=>{
  const {player,created}=fixture();player.start(1);player.enqueue('one',1);player.enqueue('two',1);
  const oldEnded=created[0].audio.onended;player.stop();player.start(2);player.enqueue('new',2);
  oldEnded();player.enqueue('stale',1);player.finish(1);
  assert.equal(created.length,2);assert.equal(created[1].wav,'new');assert.equal(player.streaming,true);
  assert.equal(created[0].audio.paused,true);assert.equal(created[0].disposed,true);
  player.setVolume(0.3);assert.equal(created[1].audio.volume,0.3);
});

test('caption chunks are delivered when playback starts, before the queue finishes',async()=>{
  const {player,created}=fixture();const captions=[];let drained=false;
  player.onChunk=text=>captions.push(text);player.onDrained=()=>{drained=true;};
  player.start(1);player.enqueue('one',1,'Перша фраза');player.enqueue('two',1,'Друга фраза');player.finish(1);
  await Promise.resolve();assert.deepEqual(captions,['Перша фраза']);assert.equal(drained,false);
  created[0].audio.onended();await Promise.resolve();assert.deepEqual(captions,['Перша фраза','Друга фраза']);
  created[1].audio.onended();assert.equal(drained,true);
});

test('speech rate updates the current chunk and following chunks without changing pitch',()=>{
  const {player,created}=fixture();let rate=1.25;player.getRate=()=>rate;
  player.start(1);player.enqueue('one',1);player.enqueue('two',1);
  assert.equal(created[0].audio.playbackRate,1.25);assert.equal(created[0].audio.preservesPitch,true);
  rate=1.75;player.setRate(rate);assert.equal(created[0].audio.playbackRate,1.75);
  created[0].audio.onended();assert.equal(created[1].audio.playbackRate,1.75);
});
