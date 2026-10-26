let socket = null, selectedTab = null, keepalive = null;
const isShopee = value => { try { const u = new URL(value); return u.protocol === 'https:' && u.hostname === 'shopee.co.id'; } catch { return false; } };

// Fixed DOM operations only: no eval, cookies API, or arbitrary browser commands.
function executeDom(request) {
  if (Date.now() >= request.expiresAt) throw new Error('Permintaan kedaluwarsa sebelum dijalankan. Tidak diulang otomatis.');
  const visible = e => {
    if (!e || ![...e.getClientRects()].some(r => r.width > 0 && r.height > 0)) return false;
    for (let node = e; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (node.hidden || style.display === 'none' ||
          style.visibility === 'hidden' || style.visibility === 'collapse') return false;
    }
    return true;
  };
  // Transparent native inputs remain interactive behind Shopee's custom checkbox skin.
  // Opacity/aria-hidden only decide whether challenge content is actually presented.
  const challengeVisible = e => {
    if (!visible(e)) return false;
    for (let node = e; node; node = node.parentElement) {
      if (node.getAttribute('aria-hidden') === 'true' || Number(getComputedStyle(node).opacity) === 0) return false;
    }
    return true;
  };
  const normal = x => String(x || '').replace(/\s+/g, ' ').trim();
  const matches = (value, spec, exact) => !spec || (spec.regex !== undefined
    ? new RegExp(spec.regex, spec.flags || '').test(normal(value))
    : exact ? normal(value) === normal(spec.text) : normal(value).includes(normal(spec.text)));
  const name = e => e.getAttribute('aria-label') ||
    (e.getAttribute('aria-labelledby') || '').split(' ').map(id => document.getElementById(id)?.textContent || '').join(' ').trim() ||
    (e.labels ? [...e.labels].map(x => x.innerText).join(' ') : '') || e.innerText || e.value || '';
  function resolve(q) {
    if (q.kind === 'css') return [...document.querySelectorAll(q.css)];
    if (q.kind === 'nth') return resolve(q.base).slice(q.index, q.index + 1);
    if (q.kind === 'sibling') return resolve(q.base).map(e => e.nextElementSibling).filter(Boolean);
    if (q.kind === 'child') return [...new Set(resolve(q.base).flatMap(e => q.css === '..' ? [e.parentElement] : [...e.querySelectorAll(q.css)]))].filter(Boolean);
    if (q.kind === 'filter') return resolve(q.base).filter(e => matches(e.innerText, q.name, false));
    if (q.kind === 'role') {
      const selectors = {button:'button,[role="button"]', radio:'input[type="radio"],[role="radio"]', checkbox:'input[type="checkbox"],[role="checkbox"]', link:'a[href],[role="link"]', spinbutton:'input[type="number"],[role="spinbutton"]'};
      if (!selectors[q.role]) throw new Error('Role tidak didukung.');
      return [...document.querySelectorAll(selectors[q.role])].filter(e => matches(name(e), q.name, q.exact));
    }
    if (q.kind === 'text') {
      const all = [...document.querySelectorAll('body *')].filter(e => matches(e.innerText, q.name, q.exact));
      return all.filter(e => ![...e.children].some(c => matches(c.innerText, q.name, q.exact)));
    }
    throw new Error('Query tidak didukung.');
  }
  if (request.operation === 'state') {
    return {url:location.href, complete:document.readyState === 'complete',
      challenge:/(?:^|\/)(?:captcha|verify|verification)(?:\/|$)/i.test(location.pathname) ||
        [...document.querySelectorAll('[class*="captcha"], [id*="captcha"], iframe[src*="captcha"]')].some(root => {
          // Shopee mounts an empty, zero-size anti_fraud_captcha host on normal checkout.
          // Require rendered challenge content, not merely a DOMRect entry for that host.
          const content = [root, ...root.querySelectorAll('iframe,img,canvas,input,button,[role="checkbox"]')];
          return content.some(e => challengeVisible(e) && (e.matches('iframe,img,canvas,input,button,[role="checkbox"]') || normal(e.innerText)));
        })};
  }
  if (request.operation === 'groups') {
    const all = [...document.querySelectorAll('button.product-variation, button[class*="selection-box-"]')];
    const groups = [], seen = new Set();
    for (const button of all.filter(visible)) {
      let root = button.closest('section,[role="group"]') || button.parentElement;
      if (root.querySelectorAll('input[role="spinbutton"],input[type="number"]').length || root.querySelectorAll('button').length > 100) root = button.parentElement;
      if (seen.has(root)) continue;
      seen.add(root);
      const options = [...root.querySelectorAll('button.product-variation,button[class*="selection-box-"]')].filter(visible)
        .map(e => ({label:normal(e.getAttribute('aria-label') || e.innerText), disabled:e.disabled || e.getAttribute('aria-disabled') === 'true'}));
      if (!options.length) continue;
      let levels=0,node=button;
      while(node && node!==root){levels++;node=node.parentElement;}
      const heading=root.querySelector('h2,h3,label,[class*="label"]');
      const label=normal(heading?.innerText || root.previousElementSibling?.innerText || 'Varian');
      groups.push({name:label.length<=50?label:'Varian',button_index:all.indexOf(button),levels,options});
    }
    return groups;
  }
  if (request.operation === 'checkout') {
    const images=[...document.querySelectorAll('img[alt="product image"]')].filter(visible);
    const headings=value=>[...document.querySelectorAll('h2,h3')].filter(e=>visible(e)&&normal(e.innerText)===value);
    const totals=[...document.querySelectorAll('h3')].filter(e=>visible(e)&&normal(e.innerText)==='Total Pembayaran');
    const buttons=[...document.querySelectorAll('button,[role="button"]')].filter(e=>visible(e)&&normal(name(e)).toLowerCase()==='buat pesanan');
    let row=images.length===1?images[0]:null;
    while(row && !(row.children.length===5 && row.children[0].contains(images[0]))) row=row.parentElement;
    return {url:location.href,complete:headings('Produk Dipesan').length===1&&headings('Metode Pembayaran').length===1&&totals.length===1&&buttons.length===1,
      image_count:images.length,columns:row?[...row.children].map(e=>normal(e.innerText)):null,
      total:totals.length===1?normal(totals[0].nextElementSibling?.innerText):null,
      submit_enabled:buttons.length===1&&!buttons[0].disabled&&buttons[0].getAttribute('aria-disabled')!=='true'};
  }
  if (request.operation === 'promotion') {
    const title=document.querySelector('h1');
    let root=title?.parentElement;
    for(let i=0;root&&i<7;i++){
      if(root.querySelector('input[role="spinbutton"],.shopee-input-quantity')) break;
      root=root.parentElement;
    }
    const lines=(root?.innerText||'').split('\n').map(normal).filter(Boolean);
    const evidence=lines.filter(t=>t.length<300&&/flash\s*sale|mulai|berakhir|\b\d{1,2}:\d{2}\b|Rp\s*[\d.]/i.test(t)).slice(0,40);
    const campaigns=[...document.querySelectorAll('a[href]')].filter(a=>visible(a)).flatMap(a=>{
      try {const u=new URL(a.getAttribute('href'),location.href);
        if(u.origin!==location.origin||u.pathname.replace(/\/$/,'')!=='/flash_sale'||!u.searchParams.get('promotionId'))return [];
        return [{url:u.href,item_id:u.searchParams.get('fromItem')||'',promotion_id:u.searchParams.get('promotionId'),announcement:normal(a.innerText)}];
      } catch{return [];}
    }).slice(0,20);
    // Read only the product subtree, never account/session/tracking fields.
    const bootstrap={models:[],preview:null};
    const productMatch=location.pathname.match(/(?:product\/(\d+)\/(\d+)|i\.(\d+)\.(\d+))$/);
    if(productMatch){
      const shop=productMatch[1]||productMatch[3], item=productMatch[2]||productMatch[4];
      for(const script of document.querySelectorAll('script[type="text/mfe-initial-data"]')){
        try{
          if(script.textContent.length>2000000)continue;
          const data=JSON.parse(script.textContent)?.initialState?.DOMAIN_PDP?.data?.PDP_BFF_DATA?.cachedMap?.[shop+'/'+item];
          if(!data||String(data.item?.item_id??data.item?.itemid)!==item||String(data.item?.shop_id??data.item?.shopid)!==shop)continue;
          const tiers=data.item.tier_variations||[];
          bootstrap.models=(data.item.models||[]).slice(0,300).map(m=>{
            const indices=m.extinfo?.tier_index||[];
            return {model_id:String(m.model_id??m.modelid??''),name:normal(m.name),
              labels:indices.map((v,i)=>normal(tiers[i]?.options?.[v])).filter(Boolean),
              promotion_id:m.promotion_id??m.promotionid??null,
              clickable:m.is_clickable??null,has_stock:m.has_stock??null};
          });
          const preview=data.bottom_banner?.flash_sale_preview||data.flash_sale_preview;
          if(preview)bootstrap.preview={promotion_id:String(preview.promotion_id??''),start_time:preview.start_time??null};
          break;
        }catch{}
      }
    }
    const published=[];
    const list=x=>Array.isArray(x)?x:x?[x]:[];
    function collect(node){
      if(!node||typeof node!=='object')return;
      if(Array.isArray(node)){node.forEach(collect);return;}
      const type=list(node['@type']);
      if(type.includes('ProductGroup')||type.includes('ProductModel')||type.includes('Product')){
        for(const variant of node.hasVariant?list(node.hasVariant):[node]){
          const labels=[variant.color,variant.size,typeof variant.model==='string'?variant.model:variant.model?.name,
            ...list(variant.additionalProperty).map(p=>p?.value)].filter(x=>typeof x==='string');
          for(const offer of list(variant.offers))published.push({parent_name:normal(node.name),parent_url:node.url||'',
            sku:normal(variant.sku),labels:labels.map(normal),name:normal(offer.name),description:normal(offer.description),
            price:offer.price,currency:offer.priceCurrency,valid_from:offer.validFrom||'',availability:offer.availability||''});
        }
      }
      if(node['@graph'])collect(node['@graph']);
    }
    for(const script of document.querySelectorAll('script[type="application/ld+json"]')){
      try{if(script.textContent.length<500000)collect(JSON.parse(script.textContent));}catch{}
    }
    return {url:location.href,title:normal(title?.innerText),evidence,campaigns,bootstrap,published:published.slice(0,300)};
  }

  const elements = resolve(request.query);
  if (request.action === 'count') return elements.length;
  if (request.action === 'visible') return visible(elements[0]);
  if (!elements.length) throw new Error('Elemen Shopee tidak ditemukan.');
  if (request.action !== 'enabled' && request.action !== 'checked' && elements.length !== 1) throw new Error('Elemen Shopee tidak unik.');
  const e = elements[0];
  if (request.action === 'text') return e.innerText;
  if (request.action === 'attribute') {
    if (!['aria-checked','aria-pressed','aria-selected','class','disabled'].includes(request.name) && !(request.name === 'href' && e.tagName === 'A')) throw new Error('Atribut tidak didukung.');
    return e.getAttribute(request.name);
  }
  if (request.action === 'value') return String(e.value ?? '');
  if (request.action === 'enabled') return !e.disabled && e.getAttribute('aria-disabled') !== 'true';
  if (request.action === 'checked') return e.checked === true || e.getAttribute('aria-checked') === 'true';
  if (!visible(e) || e.disabled || e.getAttribute('aria-disabled') === 'true') throw new Error('Elemen belum siap digunakan.');
  if (request.action === 'click') {
    if (Date.now() >= request.expiresAt) throw new Error('Klik kedaluwarsa.');
    e.scrollIntoView({block:'center',inline:'nearest'});
    e.click(); return true;
  }
  if (request.action === 'fill') {
    if (!(e instanceof HTMLInputElement || e instanceof HTMLTextAreaElement)) throw new Error('Elemen bukan kolom input.');
    if (e.type === 'password' || /otp|password|verification|captcha/i.test(`${e.name} ${e.id} ${e.placeholder}`)) throw new Error('Input keamanan harus diisi pengguna.');
    const proto = e instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype;
    e.focus({preventScroll:true});
    Object.getOwnPropertyDescriptor(proto,'value').set.call(e,String(request.value));
    e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true}));
    e.blur();
    return true;
  }
  throw new Error('Aksi tidak didukung.');
}

async function run(request) {
  if (Date.now() >= request.expiresAt) throw new Error('Permintaan browser kedaluwarsa.');
  const tab = await chrome.tabs.get(selectedTab);
  // Return to the already permitted Shopee order list after a payment redirect.
  // No DOM injection or additional host permission for the payment site.
  const recoverOrders = request.operation === 'orders';
  if (recoverOrders) request = {...request,operation:'navigate',url:'https://shopee.co.id/user/purchase/list/?type=9'};
  if (request.operation === 'info') {
    const u = new URL(tab.url);
    if (u.protocol !== 'https:' || !['shopee.co.id','id.shp.ee','shope.ee'].includes(u.hostname)) throw new Error('Tab pilihan tidak lagi berada di Shopee.');
    return {url:tab.url, complete:tab.status === 'complete'};
  }
  if (!isShopee(tab.url) && !recoverOrders) throw new Error('Tab pilihan tidak lagi berada di Shopee Indonesia.');
  if (request.operation === 'focus') { await chrome.tabs.update(tab.id,{active:true}); await chrome.windows.update(tab.windowId,{focused:true}); return true; }
  if (request.operation === 'navigate') {
    const u = new URL(request.url);
    if (u.protocol !== 'https:' || u.username || u.password || !['shopee.co.id','id.shp.ee','shope.ee'].includes(u.hostname)) throw new Error('Tujuan navigasi bukan Shopee.');
    return await new Promise((resolve,reject) => {
      let started = false;
      const finish = (error, value) => {clearTimeout(timer);chrome.tabs.onUpdated.removeListener(listener); error ? reject(error) : resolve(value);};
      const listener = (id, change, updated) => {
        if (id !== tab.id) return;
        if (change.status === 'loading' || change.url) started = true;
        if (started && change.status === 'complete') finish(null,{url:updated.url,complete:true});
      };
      const timer = setTimeout(() => finish(new Error('Navigasi belum selesai dalam 45 detik.')),Math.min(45000,Math.max(1,request.expiresAt-Date.now())));
      chrome.tabs.onUpdated.addListener(listener);
      chrome.tabs.update(tab.id,{url:u.href}).catch(error => finish(error));
    });
  }
  if (request.operation === 'screenshot') {
    if (!tab.active) throw new Error('Aktifkan tab Shopee untuk monitoring gambar.');
    const image = await chrome.tabs.captureVisibleTab(tab.windowId,{format:'jpeg',quality:65});
    const [after] = await chrome.tabs.query({active:true,windowId:tab.windowId});
    if (after?.id !== tab.id || !isShopee(after.url)) throw new Error('Tab berubah saat mengambil gambar.');
    return image;
  }
  if (!['groups','dom','state','checkout','promotion'].includes(request.operation)) throw new Error('Operasi tidak didukung.');
  const results = await chrome.scripting.executeScript({target:{tabId:tab.id},func:executeDom,args:[request]});
  if (!results.length || !Object.prototype.hasOwnProperty.call(results[0], 'result')) throw new Error('Pembacaan DOM gagal. Selector halaman perlu diperiksa.');
  return results[0].result;
}

function disconnect() {
  if (keepalive) clearInterval(keepalive);
  if (socket) socket.close();
  socket = null; selectedTab = null;
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== chrome.runtime.id) return;
  if (message.type === 'disconnect') { disconnect(); reply({ok:true}); return; }
  if (message.type !== 'connect') return;
  disconnect(); selectedTab = message.tabId;
  const ws = new WebSocket('ws://127.0.0.1:8765'); socket = ws;
  let replied = false, chain = Promise.resolve();
  const respond = value => { if (!replied) { replied = true; reply(value); } };
  ws.onopen = () => ws.send(JSON.stringify({token:message.token,protocol:8}));
  ws.onerror = () => respond({error:'Dashboard lokal belum tersedia atau koneksi ditolak.'});
  ws.onclose = () => { if (socket === ws) { clearInterval(keepalive); socket = null; } respond({error:'Kode pairing tidak valid atau koneksi berakhir.'}); };
  ws.onmessage = event => {
    const request = JSON.parse(event.data);
    if (request.type === 'paired') {
      keepalive = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send('{"type":"ping"}'); },20000);
      respond({ok:true}); return;
    }
    if (!request.id) return;
    chain = chain.then(async () => {
      try { ws.send(JSON.stringify({id:request.id,result:await run(request)})); }
      catch (error) { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({id:request.id,error:error.message})); }
    });
  };
  return true;
});
chrome.tabs.onRemoved.addListener(tabId => { if (tabId === selectedTab) disconnect(); });
