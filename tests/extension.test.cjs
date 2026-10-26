const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function runtime(tabUrl='https://shopee.co.id/') {
  const listeners = new Set();
  let tabReads = 0;
  const chrome = {
    runtime:{id:'test',onMessage:{addListener(){}}},
    tabs:{onRemoved:{addListener(){}},onUpdated:{addListener(fn){listeners.add(fn)},removeListener(fn){listeners.delete(fn)}},
      async get(){tabReads++;return {id:1,url:tabUrl,windowId:1,active:true}},
      async update(id, config){queueMicrotask(()=>{for(const fn of [...listeners])fn(1,{status:'loading'},{url:config.url});for(const fn of [...listeners])fn(1,{status:'complete'},{url:config.url})});return {id}},
    }
  };
  const context = vm.createContext({chrome,URL,Date,Promise,setTimeout,clearTimeout,setInterval,clearInterval,queueMicrotask});
  vm.runInContext(fs.readFileSync('chrome-extension/background.js','utf8'),context);
  vm.runInContext('selectedTab=1;',context);
  return {context,listeners,reads:()=>tabReads};
}

test('expired browser action is rejected before touching any tab',async()=>{
  const r=runtime();
  await assert.rejects(r.context.run({operation:'dom',expiresAt:Date.now()-1}),/kedaluwarsa/);
  assert.equal(r.reads(),0);
});

test('expired DOM action is rejected before inspecting document',()=>{
  const r=runtime();
  assert.throws(()=>r.context.executeDom({operation:'dom',expiresAt:0}),/kedaluwarsa/);
});

test('navigation resolves on completion and removes its listener',async()=>{
  const r=runtime();
  const result=await r.context.run({operation:'navigate',url:'https://shopee.co.id/product/1/2',expiresAt:Date.now()+5000});
  assert.equal(result.url,'https://shopee.co.id/product/1/2');
  assert.equal(result.complete,true);
  assert.equal(r.listeners.size,0);
});

test('quantity replacement focuses, replaces instead of appending, and commits blur',()=>{
  const r=runtime();
  const events=[];
  class Input {
    constructor(){this._value='5';this.offsetWidth=1;this.offsetHeight=1;this.disabled=false;this.type='text';this.name='quantity';this.id='qty';this.placeholder='';}
    get value(){return this._value}
    set value(value){this._value=value}
    getClientRects(){return [{width:20,height:20}]}
    getAttribute(){return null}
    focus(){events.push('focus')}
    blur(){events.push('blur')}
    dispatchEvent(event){events.push(event.type)}
  }
  const input=new Input();
  r.context.getComputedStyle=()=>({display:'block',visibility:'visible',opacity:'1'});
  r.context.HTMLInputElement=Input;
  r.context.HTMLTextAreaElement=class {};
  r.context.document={querySelectorAll:()=>[input]};
  r.context.Event=class {constructor(type){this.type=type}};
  const result=r.context.executeDom({operation:'dom',action:'fill',query:{kind:'css',css:'input'},value:'2',expiresAt:Date.now()+5000});
  assert.equal(result,true);
  assert.equal(input.value,'2');
  assert.deepEqual(events,['focus','input','change','blur']);
});


test('payment redirect recovery only navigates to the fixed Shopee order list',async()=>{
  const r=runtime('https://pay.shopee.co.id/payment-v2/payment/123');
  const result=await r.context.run({operation:'orders',url:'https://attacker.test/',expiresAt:Date.now()+5000});
  assert.equal(result.url,'https://shopee.co.id/user/purchase/list/?type=9');
});

test('payment host does not allow DOM injection',async()=>{
  const r=runtime('https://pay.shopee.co.id/payment-v2/payment/123');
  await assert.rejects(r.context.run({operation:'dom',expiresAt:Date.now()+5000}),/tidak lagi berada/);
});
