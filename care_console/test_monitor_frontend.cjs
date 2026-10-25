'use strict';
const {test,afterEach}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const active=[];
afterEach(()=>{for(const h of active.splice(0))h.window.close();});
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function until(fn,message='condition did not become true'){
  const start=Date.now();while(!fn()){if(Date.now()-start>1800)assert.fail(message);await tick();}
}
function payload(status='open',marker='初始',overrides={}){
  const actual=status==='open'||status==='all'?'pending':status;
  return {cases:[{id:1,status:actual,resident:{id:'R001',label:marker,bed_id:'A101'},contact:{name:'虛構家屬',active:true},
    owner:actual==='pending'?null:{id:'nurse',name:'護理師',valid:true},message_risk:'中',progress:{next_action:'虛構下一步',waiting_for:''},
    handoff:null,created_at:'2026-10-25T00:00:00Z',due_at:null}],
    stats:{total_cases:1,open_cases:actual==='closed'?0:1,pending_cases:actual==='pending'?1:0,claimed_cases:actual==='claimed'?1:0,
      pending_handoffs:0,closed_cases:actual==='closed'?1:0,stale_handoffs:0},
    owners:[{id:'nurse',name:'護理師'},{id:'nurse2',name:'接班護理師'}],scope_resident_ids:['R001','R002'],
    filters:{status,owner_id:'',from:'',to:'',limit:10},next_cursor:'signed-next',updated_at:'2026-10-25T00:00:00Z',...overrides};
}
async function boot(){
  const dom=new JSDOM(fs.readFileSync(path.join(__dirname,'templates/index.html'),'utf8'),{url:'http://127.0.0.1:9465/',runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window,requests=[],polls=[];
  const h={window:w,document:w.document,requests,polls,session:{id:'head_nurse',role:'head_nurse',display_name:'護理長'}};
  active.push(h);
  w.AbortController=AbortController;
  w.setInterval=(fn,ms)=>{if(ms===15000)polls.push(fn);return 1;};
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  w.HTMLDialogElement.prototype.close=function(){if(this.open){this.open=false;this.dispatchEvent(new w.Event('close'));}};
  const response=(status,data)=>({ok:status>=200&&status<300,status,json:async()=>data});
  w.fetch=(url,options={})=>{
    const target=new URL(url,w.location.href),body=options.body?JSON.parse(options.body):{};
    if(target.pathname==='/api/session')return Promise.resolve(response(200,{user:h.session,csrf:'test-token'}));
    if(target.pathname==='/api/logout'){h.session=null;return Promise.resolve(response(200,{ok:true}));}
    if(target.pathname==='/api/login'){h.session={id:body.username,role:body.username,display_name:body.username};return Promise.resolve(response(200,{user:h.session,csrf:'next-token'}));}
    if(target.pathname==='/api/bindings')return Promise.resolve(response(200,{users:[],access:[],line_links:[],residents:[],beds:[]}));
    if(target.pathname==='/api/knowledge'){h.knowledgeLoads=(h.knowledgeLoads||0)+1;return Promise.resolve(response(200,{sources:[]}));}
    assert.match(target.pathname,/^\/api\/case-monitor/,'unexpected endpoint');
    // Deliberately ignore abort: a transport/server may already have delivered an old response.
    return new Promise((resolve,reject)=>requests.push({url:target,options,complete:(status,data)=>resolve(response(status,data)),fail:reject}));
  };
  w.eval(fs.readFileSync(path.join(__dirname,'static/app.js'),'utf8')+'\nwindow.__uatTestToast=toast;');
  await until(()=>requests.length===1,'initial query missing');requests[0].complete(200,payload());
  await until(()=>w.document.querySelector('#monitor-rows').textContent.includes('初始'));
  h.rowText=()=>w.document.querySelector('#monitor-rows').textContent;
  h.result=()=>w.document.querySelector('#monitor-result').textContent;
  h.background=async()=>{const count=requests.length;polls[0]();await until(()=>requests.length===count+1,'background query missing');return requests.at(-1);};
  h.submit=async(status)=>{w.document.querySelector('#monitor-status').value=status;w.document.querySelector('#monitor-filters').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();};
  return h;
}

test('manual filter supersedes delayed background; old response cannot overwrite',async()=>{
  const h=await boot(),old=await h.background();await h.submit('claimed');
  assert.equal(h.requests.length,3,'new filter must not be dropped while background is loading');
  h.requests[2].complete(200,payload('claimed','最新已接手'));await until(()=>h.rowText().includes('最新已接手'));
  old.complete(200,payload('open','過期背景'));await tick();await tick();
  assert.match(h.rowText(),/最新已接手/);assert.doesNotMatch(h.rowText(),/過期背景/);
});
test('three rapid filter submissions keep only newest result even in reverse completion order',async()=>{
  const h=await boot();await h.submit('pending');await h.submit('claimed');await h.submit('closed');
  assert.equal(h.requests.length,4,'all three explicit searches must be accepted');
  h.requests[3].complete(200,payload('closed','第三次'));await until(()=>h.rowText().includes('第三次'));
  h.requests[2].complete(200,payload('claimed','第二次'));h.requests[1].complete(200,payload('pending','第一次'));
  await tick();await tick();assert.match(h.rowText(),/第三次/);assert.doesNotMatch(h.rowText(),/第一次|第二次/);
  assert.equal(h.document.querySelector('#monitor-status').value,'closed');
});
test('polling deduplicates in-flight queries and does not erase an unresolved error',async()=>{
  const h=await boot(),request=await h.background();h.polls[0]();h.polls[0]();await tick();assert.equal(h.requests.length,2);
  request.complete(500,{error:'伺服器暫時失敗'});await until(()=>h.result().includes('伺服器暫時失敗'));
  h.polls[0]();await tick();assert.equal(h.requests.length,2,'poll must not clear error or retry without a user action');
  assert.match(h.result(),/伺服器暫時失敗/);
});
test('background response preserves an owner filter that is being edited',async()=>{
  const h=await boot(),old=await h.background();const owner=h.document.querySelector('#monitor-owner');
  owner.value='nurse2';owner.dispatchEvent(new h.window.Event('change',{bubbles:true}));
  old.complete(200,payload('open','背景資料',{owners:[{id:'nurse',name:'護理師'}]}));await until(()=>h.rowText().includes('背景資料'));
  assert.equal(owner.value,'nurse2','unsubmitted owner selection must survive rendering');
});
test('logout while query is delayed clears all protected data despite late completion',async()=>{
  const h=await boot(),old=await h.background();h.document.querySelector('#logout').click();
  await until(()=>!h.document.querySelector('#login-view').hidden);old.complete(200,payload('open','不可恢復的家屬資料'));
  await tick();await tick();assert.equal(h.rowText(),'');assert.equal(h.document.querySelector('#monitor-events').textContent,'');
});
test('head nurse can switch to IT while old monitor request remains in flight',async()=>{
  const h=await boot(),old=await h.background();h.document.querySelector('#logout').click();await until(()=>!h.document.querySelector('#login-view').hidden);
  h.document.querySelector('#username').value='admin';h.document.querySelector('#password').value='test-only';
  h.document.querySelector('#login-form').dispatchEvent(new h.window.Event('submit',{cancelable:true,bubbles:true}));
  await until(()=>!h.document.querySelector('#accounts-page').hidden);old.complete(200,payload('open','舊護理長受限內容'));
  await tick();await tick();assert.equal(h.rowText(),'');assert.equal(h.document.querySelector('#monitor-title').textContent,'');
});
test('known revocation response wins over an older authorized response',async()=>{
  const h=await boot(),old=await h.background();await h.submit('claimed');assert.equal(h.requests.length,3);
  h.requests[2].complete(200,payload('claimed','',{cases:[],owners:[],scope_resident_ids:['R002'],next_cursor:null,
    stats:{total_cases:0,open_cases:0,pending_cases:0,claimed_cases:0,pending_handoffs:0,closed_cases:0,stale_handoffs:0}}));
  await until(()=>h.document.querySelector('#monitor-scope').textContent.includes('R002'));
  old.complete(200,payload('open','已撤權 R001'));await tick();await tick();assert.doesNotMatch(h.rowText(),/已撤權/);
  assert.doesNotMatch(h.document.querySelector('#monitor-scope').textContent,/R001/);
});
test('obsolete 401 does not sign out a newer successful query',async()=>{
  const h=await boot(),old=await h.background();await h.submit('claimed');assert.equal(h.requests.length,3);
  h.requests[2].complete(200,payload('claimed','目前有效'));await until(()=>h.rowText().includes('目前有效'));
  h.session=null;old.complete(401,{error:'舊請求失效'});await tick();await tick();
  assert.equal(h.document.querySelector('#login-view').hidden,true);assert.match(h.rowText(),/目前有效/);
});
test('409 on a page automatically reloads page one once with the same filters',async()=>{
  const h=await boot();h.document.querySelector('#monitor-next').click();await until(()=>h.requests.length===2);
  assert.equal(h.requests[1].url.searchParams.get('cursor'),'signed-next');h.requests[1].complete(409,{error:'資料已變更'});
  await until(()=>h.requests.length===3,'409 must trigger a bounded first-page fetch');
  assert.equal(h.requests[2].url.searchParams.has('cursor'),false);assert.equal(h.requests[2].url.searchParams.get('status'),'open');
  h.requests[2].complete(200,payload('open','重新第一頁'));await until(()=>h.rowText().includes('重新第一頁'));
  assert.match(h.result(),/案件資料已更新，已重新載入第一頁/);
});
test('409 recovery cannot retry forever when the first page also fails',async()=>{
  const h=await boot();h.document.querySelector('#monitor-next').click();await until(()=>h.requests.length===2);
  h.requests[1].complete(409,{error:'游標過期'});await until(()=>h.requests.length===3);
  h.requests[2].complete(409,{error:'查詢仍不一致'});await until(()=>h.result().includes('查詢仍不一致'));
  h.polls[0]();await tick();assert.equal(h.requests.length,3);assert.equal(h.rowText(),'');
});
test('400 tampered cursor is not silently retried; 500 and network errors retain filters',async()=>{
  for(const status of [400,500,'network']){
    const h=await boot();await h.submit('closed');const request=h.requests.at(-1);
    if(status==='network')request.fail(new TypeError('network disconnected'));else request.complete(status,{error:'明確的查詢錯誤'});
    await until(()=>h.result().includes('讀取失敗'));
    assert.equal(h.requests.length,2);assert.equal(h.document.querySelector('#monitor-status').value,'closed');assert.equal(h.rowText(),'');
  }
});
test('401 clears login data and 403 switches to current IT role without retry',async()=>{
  for(const status of [401,403]){
    const h=await boot(),request=await h.background();h.session=status===401?null:{id:'admin',role:'admin',display_name:'IT'};
    request.complete(status,{error:'權限已失效'});await until(()=>status===401?!h.document.querySelector('#login-view').hidden:!h.document.querySelector('#accounts-page').hidden);
    assert.equal(h.rowText(),'');assert.equal(h.document.querySelector('#monitor-events').textContent,'');assert.equal(h.requests.length,2);
  }
});
test('404 timeline clears the inaccessible case without turning into a cursor retry',async()=>{
  const h=await boot();h.document.querySelector('[data-monitor-case]').click();await until(()=>h.requests.length===2);
  h.requests[1].complete(404,{error:'案件不存在或不在授權範圍內。'});
  await until(()=>h.document.querySelector('#monitor-events').textContent.includes('不在授權範圍'));
  assert.equal(h.document.querySelector('#monitor-case').textContent,'');assert.equal(h.requests.length,2);
});

test('403 with unchanged role preserves error and draft without a reload loop',async()=>{
  const h=await boot(),request=await h.background();h.document.querySelector('#monitor-owner').value='nurse2';
  request.complete(403,{error:'目前暫不允許此查詢'});await until(()=>h.result().includes('目前暫不允許此查詢'));
  await tick();await tick();assert.equal(h.requests.length,2);
  assert.equal(h.document.querySelector('#monitor-owner').value,'nurse2');assert.equal(h.rowText(),'');
});

function history(marker,next='older-token'){
  return {case:payload('claimed').cases[0],events:[{id:1,case_id:1,action:'case_progress_saved',payload:{summary:marker},created_at:'2026-10-25T00:00:00Z'}],next_cursor:next,history_note:'虛構歷程',updated_at:'2026-10-25T00:00:00Z'};
}
test('history 409 replaces old events and retries page one only once',async()=>{
  const h=await boot();h.document.querySelector('[data-monitor-case]').click();await until(()=>h.requests.length===2);
  h.requests[1].complete(200,history('過期歷程'));await until(()=>!h.document.querySelector('#monitor-older').disabled);
  h.document.querySelector('#monitor-older').click();await until(()=>h.requests.length===3);
  h.requests[2].complete(409,{error:'案件版本已更新'});await until(()=>h.requests.length===4);
  assert.equal(h.requests[3].url.searchParams.has('cursor'),false);
  h.requests[3].complete(200,history('新的歷程',null));await until(()=>h.document.querySelector('#monitor-events').textContent.includes('新的歷程'));
  assert.doesNotMatch(h.document.querySelector('#monitor-events').textContent,/過期歷程/);
});
test('timeline 404 invalidates an older list that has not finished',async()=>{
  const h=await boot();h.document.querySelector('[data-monitor-case]').click();await until(()=>h.requests.length===2);
  h.requests[1].complete(200,history('原本歷程'));await until(()=>!h.document.querySelector('#monitor-older').disabled);
  const old=await h.background();h.document.querySelector('#monitor-older').click();await until(()=>h.requests.length===4);
  h.requests[3].complete(404,{error:'案件不在授權範圍'});await until(()=>h.document.querySelector('#monitor-events').textContent.includes('不在授權範圍'));
  old.complete(200,payload('open','不可恢復的資料'));await tick();await tick();assert.equal(h.rowText(),'');
});
test('login initial monitor read does not block logout while the response is delayed',async()=>{
  const h=await boot();h.document.querySelector('#logout').click();await until(()=>!h.document.querySelector('#login-view').hidden);
  h.document.querySelector('#username').value='head_nurse';h.document.querySelector('#password').value='test-only';
  h.document.querySelector('#login-form').dispatchEvent(new h.window.Event('submit',{cancelable:true,bubbles:true}));
  await until(()=>h.requests.length===2);await tick();h.document.querySelector('#logout').click();
  await until(()=>!h.document.querySelector('#login-view').hidden,'a read after login must not block logout');
  h.requests[1].complete(200,payload('open','已登出的初始資料'));await tick();await tick();assert.equal(h.rowText(),'');
});
test('head nurse refresh on service information reloads that page',async()=>{
  const h=await boot();h.document.querySelector('[data-page="knowledge"]').click();
  await until(()=>h.knowledgeLoads===1);h.document.querySelector('#refresh').click();
  await until(()=>h.knowledgeLoads===2);assert.equal(h.requests.length,1);
});
test('unresolved timeline errors survive background polling until explicit user action',async()=>{
  for(const status of [400,403,500,'network']){
    const h=await boot();h.document.querySelector('[data-monitor-case]').click();await until(()=>h.requests.length===2);
    if(status==='network')h.requests[1].fail(new TypeError('歷程網路中斷'));
    else h.requests[1].complete(status,{error:'歷程未解決的錯誤 '+status});
    await until(()=>/歷程未解決的錯誤|歷程網路中斷/.test(h.document.querySelector('#monitor-events').textContent));
    await tick();await tick();const error=h.document.querySelector('#monitor-events').textContent;
    h.polls[0]();await tick();assert.equal(h.requests.length,2,'poll must not replace a timeline error');
    assert.equal(h.document.querySelector('#monitor-events').textContent,error);
    h.document.querySelector('#monitor-close').click();
    h.polls[0]();await tick();assert.equal(h.requests.length,3,'closing the error explicitly may resume polling');
  }
});
test('background polling does not restart a delayed timeline read',async()=>{
  const h=await boot();h.document.querySelector('[data-monitor-case]').click();await until(()=>h.requests.length===2);
  h.polls[0]();h.polls[0]();await tick();assert.equal(h.requests.length,2);
  h.requests[1].complete(200,history('延遲歷程完成'));await until(()=>h.document.querySelector('#monitor-events').textContent.includes('延遲歷程完成'));
});
test('second history 409 stops recovery and keeps the error across polling',async()=>{
  const h=await boot();h.document.querySelector('[data-monitor-case]').click();await until(()=>h.requests.length===2);
  h.requests[1].complete(200,history('原本歷程'));await until(()=>!h.document.querySelector('#monitor-older').disabled);
  h.document.querySelector('#monitor-older').click();await until(()=>h.requests.length===3);
  h.requests[2].complete(409,{error:'第一次409'});await until(()=>h.requests.length===4);
  h.requests[3].complete(409,{error:'第二次409停止重查'});await until(()=>h.document.querySelector('#monitor-events').textContent.includes('第二次409'));
  h.polls[0]();await tick();assert.equal(h.requests.length,4);
  assert.match(h.document.querySelector('#monitor-events').textContent,/第二次409停止重查/);
});

test('rejected action feedback stays inside the open resident modal accessibility scope',async()=>{
  const h=await boot(),dialog=h.document.querySelector('#resident-dialog');
  dialog.showModal();
  const reason='交班提出後有新訊息或回覆，請原接手者更新內容並重新提出交班。';
  h.window.__uatTestToast(reason,true);
  const notice=dialog.querySelector('[role="status"]');
  assert.ok(notice,'modal feedback must not be in the inert document behind its backdrop');
  assert.equal(notice.textContent,reason);
  assert.equal(notice.hidden,false);
  assert.equal(h.document.querySelectorAll('#notice').length,1);
});

test('feedback follows nested discard modal then returns to the remaining modal or page',async()=>{
  const h=await boot(),resident=h.document.querySelector('#resident-dialog'),discard=h.document.querySelector('#discard-dialog');
  resident.showModal();discard.showModal();h.window.__uatTestToast('請先處理尚未保存內容',true);
  assert.ok(discard.contains(h.document.querySelector('#notice')));
  discard.close();h.window.__uatTestToast('虛構：<img src=x onerror=alert(1)>',true);
  const notice=h.document.querySelector('#notice');
  assert.ok(resident.contains(notice));
  assert.equal(notice.querySelector('img'),null,'feedback must remain text');
  resident.close();h.window.__uatTestToast('已回到工作台');
  assert.equal(notice.parentElement,h.document.body);
  assert.equal(notice.textContent,'已回到工作台');
});

test('closing and reopening a modal cannot revive the previous case success notice',async()=>{
  const h=await boot(),dialog=h.document.querySelector('#resident-dialog');
  dialog.showModal();h.window.__uatTestToast('案件已結案。');dialog.close();
  h.document.querySelector('#resident-title').textContent='另一位虛構住民';dialog.showModal();
  const notice=h.document.querySelector('#notice');
  assert.equal(notice.hidden,true);
  assert.equal(notice.textContent,'');
  assert.equal(dialog.contains(notice),false);
});

test('closing discard clears its own message without clearing a newer message in another host',async()=>{
  const h=await boot(),resident=h.document.querySelector('#resident-dialog'),discard=h.document.querySelector('#discard-dialog');
  resident.showModal();discard.showModal();h.window.__uatTestToast('舊確認框訊息');discard.close();
  discard.showModal();assert.equal(h.document.querySelector('#notice').hidden,true);discard.close();
  h.window.__uatTestToast('目前住民的新訊息');
  discard.dispatchEvent(new h.window.Event('close'));
  assert.equal(h.document.querySelector('#notice').textContent,'目前住民的新訊息');
  assert.equal(h.document.querySelector('#notice').hidden,false);
});
