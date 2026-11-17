// Synthetic client-store contract tests; not native browser acceptance.
const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');
function setup(){
 const messages=[];let plugin,listener,cleanup,scheduled,byId={};
 vm.runInNewContext(fs.readFileSync('harness-navigation/client.js','utf8'),{
   window:{__ModuleLoader__:{load:p=>plugin=p.factory()},parent:{postMessage:(m,o)=>messages.push({m,o})}},
   setTimeout:f=>(scheduled=f,1),clearTimeout:()=>{scheduled=null}
 });
 plugin.apply({effect:f=>cleanup=f(),sessions:{list:{getSnapshot:()=>({byId}),subscribe:f=>(listener=f,()=>{listener=null})}}});
 return {messages,set(rows){byId=rows;listener();scheduled();},stop(){cleanup();return {listener,scheduled}}};
}
test('only foreground mainView selects a study; repeated catalog edits do not navigate',()=>{
 const s=setup();s.set({a:{id:'session-a',retainedBy:{mainView:1}},b:{id:'session-b',retainedBy:{sidebar:1}}});
 assert.equal(s.messages[0].m.session_id,'session-a');assert.equal(s.messages[0].o,'http://127.0.0.1:8765');
 s.set({a:{id:'session-a',retainedBy:{mainView:1}}});assert.equal(s.messages.length,1);
 s.set({b:{id:'session-b',retainedBy:{mainView:1}}});assert.equal(s.messages[1].m.session_id,'session-b');
});
test('no foreground or ambiguous foreground clears old research',()=>{
 const s=setup();s.set({});assert.equal(s.messages[0].m.session_id,null);
 s.set({a:{id:'a',retainedBy:{mainView:1}},b:{id:'b',retainedBy:{mainView:1}}});assert.equal(s.messages.length,1);
});
test('disposal cancels timers and unsubscribes',()=>{
 const s=setup();assert.deepEqual(s.stop(),{listener:null,scheduled:null});
});
test('host contributes native session/turn identity only to ordinary model calls',async()=>{
 const {apply}=await import('../../harness_session_bridge.mjs');let provider;
 apply({deepseekLlmApiExtensions:{register:(field,p)=>{assert.equal(field,'eventlens_context');provider=p}},
   sessions:{get:id=>id==='session-a'?{id,snapshotEvents:()=>[
     {type:'user/message',seq:8,data:{source:{kind:'user'}}},
     {type:'tool/result',seq:9,data:{}}]}:undefined},on:()=>{}});
 assert.deepEqual(provider.prepare({sessionId:'session-a'}),{value:{session_id:'session-a',user_seq:8}});
 assert.equal(provider.prepare({sessionId:'session-a',purpose:'title'}),undefined);
 assert.equal(provider.prepare({sessionId:'missing'}),undefined);
});
