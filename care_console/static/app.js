'use strict';
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const roles = {admin:'IT 管理人員',head_nurse:'護理長',nurse:'護理師',caregiver:'照服員',family:'家屬聯絡人',resident:'住民本人'};
const states = {automatic:'自動處理',awaiting_review:'待人工確認',awaiting_takeover:'待人工接管',human_active:'人工處理中'};
const actionNames = {observation_added:'新增照護回報',message_submitted:'送出工作人員測試訊息',line_message_simulated:'模擬 LINE 傳入訊息',case_claim:'人工接手',case_reply:'人工回覆',case_resolve:'結案',case_approve:'核准草稿',case_reject:'退回草稿',access_granted:'授予查看權限',access_revoked:'取消查看權限',bed_changed:'床位異動',case_progress_saved:'保存處理進度',handoff_proposed:'提出交班',handoff_accepted:'接收交班',handoff_cancelled:'取消交班',case_progress:'更新進度',case_handoff:'交班操作',case_accept_handoff:'確認接收交班',case_cancel_handoff:'取消交班操作'};
const appState = {user:null,csrf:null,cards:[],queue:[],page:'board',rid:null,cid:null,detail:null,toastTimer:null,busy:false,refreshing:false,progressDirty:false,progressCase:null,noteRevision:0,epoch:0};
const monitorState = {filters:{status:'open',owner_id:'',from:'',to:'',limit:'10'},cursor:null,next:null,current:null,historyNext:null,sequence:0,loading:false};
const formBaselines = new WeakMap();
const discardDialog=document.createElement('dialog');
discardDialog.id='discard-dialog';discardDialog.setAttribute('aria-labelledby','discard-title');
discardDialog.setAttribute('aria-describedby','discard-description');
discardDialog.innerHTML='<h2 id="discard-title">內容尚未保存</h2><p id="discard-description"></p><div class="discard-actions"><button type="button" class="primary" id="keep-editing">繼續編輯</button><button type="button" class="secondary" id="discard-changes">放棄變更</button></div>';
document.body.append(discardDialog);
let discardDecision=null;
function confirmDiscard(message) {
  if(discardDecision)return Promise.resolve(false);
  $('#discard-description').textContent=message;discardDialog.returnValue='keep';discardDialog.showModal();
  return new Promise(resolve=>{discardDecision=resolve;});
}
$('#keep-editing').addEventListener('click',()=>discardDialog.close('keep'));
$('#discard-changes').addEventListener('click',()=>discardDialog.close('discard'));
discardDialog.addEventListener('close',()=>{const decision=discardDecision;discardDecision=null;decision?.(discardDialog.returnValue==='discard');});
function formContents(form) {
  return JSON.stringify([...form.elements].filter(el=>['INPUT','TEXTAREA','SELECT'].includes(el.tagName))
    .map(el=>[el.id||el.name,el.type==='checkbox'?el.checked:el.value]));
}
function rememberForm(form) {formBaselines.set(form,formContents(form));}
function formChanged(form) {return formBaselines.has(form)&&formBaselines.get(form)!==formContents(form);}
function unsavedResidentForms() {return $('#resident-dialog').open&&$$('#resident-dialog form').some(formChanged);}
async function allowResidentExit() {
  if(appState.busy){toast('操作處理中，請等待完成後再離開。');return false;}
  return !unsavedResidentForms()||await confirmDiscard('這位住民尚有未保存或未送出的內容。放棄變更後，這些內容不會保存。');
}
async function closeResident() {if(await allowResidentExit())$('#resident-dialog').close();}
const assessor = () => appState.user?.role==='nurse';
const staff = () => ['nurse','caregiver'].includes(appState.user?.role);
const supervisor = () => appState.user?.role==='head_nurse';
const date = value => value ? new Date(value).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}) : '尚未回報';
const duration = value => {const minutes=Math.floor(value/60);return minutes<1?'未滿 1 分鐘':minutes<60?`${minutes} 分鐘`:`${Math.floor(minutes/60)} 小時 ${minutes%60} 分鐘`;};
const short = (value,limit=110) => String(value||'').length>limit?String(value).slice(0,limit)+'…':String(value||'');
function toast(text, bad=false) {
  const box = $('#notice'); box.textContent = text; box.classList.toggle('bad',bad); box.hidden=false;
  clearTimeout(appState.toastTimer); appState.toastTimer=setTimeout(()=>box.hidden=true,6000);
}
async function api(path, data) {
  const requestEpoch=appState.epoch;
  const response = await fetch(path,{method:data===undefined?'GET':'POST',credentials:'same-origin',headers:data===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':appState.csrf},body:data===undefined?undefined:JSON.stringify(data)});
  const body = await response.json();
  if (!response.ok) {
    if (response.status===401 && path!=='/api/login' && requestEpoch===appState.epoch && appState.user) { await sessionView(); }
    const error=new Error(body.error || '操作未完成。');error.status=response.status;throw error;
  }
  return body;
}
async function perform(fn, button) {
  if (appState.busy) return;
  appState.busy=true; if(button)button.disabled=true;
  try { await fn(); } catch(error) { toast(error.message,true); }
  finally { appState.busy=false;if(button){button.disabled=false;if(button.id==='monitor-next')button.disabled=!monitorState.next;if(button.id==='monitor-first')button.disabled=!monitorState.cursor;if(button.id==='monitor-older')button.disabled=!monitorState.historyNext;} }
}
function roleVisibility() {
  $$('.admin-only').forEach(el=>el.hidden=appState.user?.role!=='admin');
  $$('.assessor-only').forEach(el=>el.hidden=!assessor());
  $$('.staff-only').forEach(el=>el.hidden=!staff());
  $$('.clinical-only').forEach(el=>el.hidden=!staff());
  $$('.monitor-only').forEach(el=>el.hidden=!supervisor());
  $('#messages-tab .info-block p').textContent='查看與此住民相關的服務訊息。接手、審閱與人工回覆請至「人工處理」。目前尚未串接真實 LINE。';
  $('#care-status').disabled=appState.user?.role==='caregiver';
  const pendingFilter=$('#board-filter option[value="pending"]');
  pendingFilter.hidden=!assessor();pendingFilter.disabled=!assessor();
  if(!assessor()&&$('#board-filter').value==='pending')$('#board-filter').value='all';
  $$('#queue-filter option[value="mine"],#queue-filter option[value="handoff"]').forEach(el=>{el.hidden=!assessor();el.disabled=!assessor();});
  if(!assessor() && ['mine','handoff'].includes($('#queue-filter').value))$('#queue-filter').value='all';
}
async function sessionView() {
  const epoch=++appState.epoch;
  const result = await api('/api/session');if(epoch!==appState.epoch)return;appState.user=result.user;appState.csrf=result.csrf;
  clearMonitor();
  if($('#resident-dialog').open)$('#resident-dialog').close();
  clearProtectedDetail();appState.rid=null;appState.cid=null;appState.detail=null;appState.cards=[];appState.queue=[];
  ['#resident-cards','#stats','#observation-list','#work-queue','#care-followups'].forEach(s=>$(s).replaceChildren());
  $('#login-view').hidden=!!result.user;$('#app-view').hidden=!result.user;
  if(!result.user){ if($('#resident-dialog').open)$('#resident-dialog').close();appState.rid=null;appState.cid=null;appState.cards=[];appState.queue=[];appState.detail=null;appState.progressDirty=false;
    clearProtectedDetail();
    ['#resident-cards','#stats','#message-list','#audit-list','#observation-list','#case-summary','#draft-list','#account-list','#line-contact-list','#work-queue','#care-followups','#case-context','#saved-progress','#handoff-status','#case-history'].forEach(s=>$(s).replaceChildren());
    return;
  }
  $('#user-name').textContent=result.user.display_name;$('#user-role').textContent=roles[result.user.role];$('#user-avatar').textContent=roles[result.user.role][0];
  roleVisibility(); await showPage(supervisor()?'monitor':result.user.role==='admin'?'accounts':'board');
}
function badge(status) {
  const kind={'一般照護':'general','需追蹤':'track','需優先確認':'priority'}[status]||'';
  return `<span class="badge ${kind}">${esc(status||'沒有回報')}</span>`;
}
function vital(label,value,unit) {
  return `<div class="vital"><span>${esc(label)}</span><strong>${esc(value??'—')}</strong><small>${esc(value==null?'':unit)}</small></div>`;
}
async function refreshBoard() {
  if(appState.refreshing || !staff())return;
  const epoch=appState.epoch;
  appState.refreshing=true;
  try {
    const body=await api('/api/board');if(epoch!==appState.epoch||!staff())return;appState.cards=body.cards;appState.queue=body.work_queue||[];
    $('#connection').textContent='最近同步 '+date(body.synchronized_at); renderBoard();
  } catch(error) {$('#connection').textContent='連線中斷 · 畫面保留上次資料';throw error;}
  finally{appState.refreshing=false;}
}
function renderBoard() {
  const cards=appState.cards;
  const metrics=assessor()?[
    ['尚未接手',appState.queue.filter(q=>q.case_status==='pending').length,'訊息案件'],
    ['由我處理',appState.queue.filter(q=>q.mine).length,'仍由我負責'],
    ['交班給我',appState.queue.filter(q=>q.handoff_to_me).length,'等待我確認接收'],
    ['照護回報需確認',cards.filter(c=>['需追蹤','需優先確認'].includes(c.assessment?.care_status)).length,'依最近已評估紀錄列出']
  ]:[['照護住民',cards.length,'依工作範圍顯示'],['最近回報待評估',cards.filter(c=>c.latest?.care_status==='尚未評估').length,'由護理師確認照護狀態'],['照護回報需確認',cards.filter(c=>['需追蹤','需優先確認'].includes(c.assessment?.care_status)).length,'依最近已評估紀錄列出'],['沒有量測回報',cards.filter(c=>!c.latest || Object.values(c.latest.values).every(v=>v==null)).length,'需要另行確認資訊']];
  $('#stats').innerHTML=metrics.map(([label,n,note])=>`<div class="stat"><span>${label}</span><strong>${n}</strong><small>${note}</small></div>`).join('');
  const filter=$('#board-filter').value;
  const shown=cards.filter(c=>filter==='all'||filter==='pending'&&c.pending_case||filter==='missing'&&(!c.latest||Object.values(c.latest.values).every(v=>v==null)));
  $('#resident-cards').innerHTML=shown.length?shown.map(c=>{
    const v=c.latest?.values||{};
    const assessment=c.assessment;
    const assessmentNote=assessment?`最近已評估紀錄：${esc(date(assessment.observed_at))} · ${esc(assessment.source)}${assessment.id!==c.latest?.id?'<br>最新回報尚未評估，前次評估紀錄仍保留。':''}`:'尚無已評估紀錄。';
    return `<article class="resident-card"><div class="card-top"><div><span class="bed">${esc(c.ward)} · ${esc(c.bed_id||'未配置床位')}</span><h3>${esc(c.label)}</h3></div><div class="status-label">最近照護評估${badge(assessment?.care_status||(c.latest?'尚未評估':null))}</div></div><div class="card-source">${c.latest?`最近回報 ${esc(date(c.latest.observed_at))}<br>${esc(c.latest.source)}`:'尚無照護回報；不能據此判斷健康狀況。'}</div><div class="vitals">${vital('體溫',v.temperature_c,'°C')}${vital('脈搏',v.pulse_bpm,'次／分')}${vital('血氧',v.spo2_pct,'%')}</div>${c.latest?.note?`<p class="card-note">回報內容：${esc(short(c.latest.note,75))}</p>`:''}<p class="assessment-note">${assessmentNote}</p><div class="card-bottom">${assessor()?`<span class="state">訊息：${esc(states[c.state]||c.state)}${c.pending_count>1?` · ${c.pending_count} 件`:``}</span>`:'<span class="state">照護紀錄與觀察回報</span>'}<button data-resident="${esc(c.id)}">查看與處理 →</button></div></article>`;
  }).join(''):'<div class="empty">目前沒有符合條件的照護住民。</div>';
  renderQueue();
}
function renderQueue() {
  const filter=$('#queue-filter').value;
  const queue=appState.queue.filter(q=>filter==='all'||filter==='pending'&&q.case_status==='pending'||filter==='mine'&&q.mine||filter==='handoff'&&q.handoff_to_me);
  $('#work-queue').innerHTML=queue.length?queue.map(q=>{
    const latest=q.context.recent_inputs.at(-1);const needsHandoff=q.handoff_to_me;
    const button=!assessor()?'查看對話':needsHandoff?'查看交班':q.mine?'繼續處理':q.case_status==='pending'?'查看並接手':'查看案件';
    return `<article class="work-item ${q.message_risk==='高'?'risk-high':''}"><div class="work-title"><div><span class="bed">${esc(q.bed_id)} · 案件 #${q.case_id}</span><h3>${esc(q.label)}</h3></div><span class="badge ${q.message_risk==='高'?'priority':'track'}">訊息風險 ${esc(q.message_risk)}</span></div><p class="work-reason">${esc(q.contact_label)}${q.contact_active?'':' · 配對已撤銷'}<br>${esc(q.context.reason)}</p><p class="work-preview">近期詢問：${esc(short(latest?.text||'無可用訊息紀錄'))}</p><div class="work-meta"><span>${esc(q.context.time_label)} ${esc(duration(q.context.elapsed_seconds))}</span><span>${q.operator?'接手者：'+esc(q.operator):'尚未有人接手'}</span>${q.handoff?`<span>交班待 ${esc(q.handoff.to_name)} 接收${q.handoff.stale?' · 內容需更新':''}</span>`:''}</div><div class="work-bottom"><p>${q.note?'下一步：'+esc(short(q.note.next_action,85)):'接手後請記錄處理進度與下一步。'}</p><button class="secondary" data-work-resident="${esc(q.id)}" data-work-conversation="${esc(q.conversation_id)}">${button} →</button></div></article>`;
  }).join(''):'<div class="empty">目前沒有符合篩選條件的訊息待辦。</div>';
  const followups=appState.cards.filter(c=>['需追蹤','需優先確認'].includes(c.assessment?.care_status)).sort((a,b)=>(a.assessment.care_status==='需優先確認'?0:1)-(b.assessment.care_status==='需優先確認'?0:1));
  $('#followup-section').hidden=!followups.length;
  $('#care-followups').innerHTML=followups.map(c=>`<article class="followup-item"><div><strong>${esc(c.bed_id)} · ${esc(c.label)}</strong> ${badge(c.assessment.care_status)}<p>${esc(c.assessment.note||'來源未提供說明，需確認原始紀錄。')}</p><small>最近已評估紀錄 ${esc(date(c.assessment.observed_at))} · ${esc(c.assessment.source)}${c.assessment.id!==c.latest?.id?'<br>另有較新的未評估回報，尚未更新此評估紀錄。':''}</small></div><button data-followup-resident="${esc(c.id)}" class="secondary">查看回報 →</button></article>`).join('');
}
const pages={board:['照護工作台','查看訊息待辦、照護回報與交班進度。'],monitor:['護理長案件監控','依授權範圍查看責任、下一步與處理歷程。此頁僅供查閱。'],knowledge:['服務資訊','查看問答使用的官方資料摘要與查核日期。'],import:['資料匯入','檢查院內回報的欄位、時間與來源。'],accounts:['人員與授權','管理工作範圍與模擬聯絡人配對；IT 身分不取得臨床內容。']};
async function showPage(page) {
  if(!pages[page] || page==='board'&&!staff() || page==='monitor'&&!supervisor() || page==='import'&&!assessor() || page==='accounts'&&appState.user.role!=='admin')page=supervisor()?'monitor':appState.user.role==='admin'?'accounts':'board';
  appState.page=page;$$('.page').forEach(el=>el.hidden=el.id!==page+'-page');$$('[data-page]').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
  $('#page-title').textContent=pages[page][0];$('#page-description').textContent=page==='board'&&!assessor()?'查看工作範圍內的照護紀錄與觀察回報。':pages[page][1];
  if(page==='board')await refreshBoard();
  if(page==='knowledge')await loadKnowledge();
  if(page==='accounts')await loadAccounts();
  if(page==='monitor')await refreshMonitor();
}
async function loadKnowledge() {
  const data=await api('/api/knowledge');
  $('#knowledge-list').innerHTML=data.sources.map(s=>{
    let link='';try{const u=new URL(s.url);if(u.protocol==='https:')link=`<a href="${esc(u.href)}" target="_blank" rel="noopener noreferrer">開啟官方來源 ↗</a>`;}catch{}
    return `<article class="knowledge-card"><span class="eyebrow">${esc(s.id)}</span><h3>${esc(s.title)}</h3><p>${esc(s.summary)}</p>${link}<small>資料查核日期：${esc(s.checked_at||'未註記')}</small></article>`;
  }).join('');
}
async function loadAccounts() {
  const epoch=appState.epoch;
  const data=await api('/api/bindings');
  if(epoch!==appState.epoch||appState.user?.role!=='admin')return;
  const renderAccount=user=>{
    const fixed=user.role==='admin';
    const linked=data.line_links.find(l=>l.user_id===user.id);
    const contact=['family','resident'].includes(user.role);
    const portal=contact?'LINE 聯絡人':'院內網頁帳號';
    const heading=contact?roles[user.role]:user.display_name;
    return `<article class="account-card"><div><h3>${esc(heading)}</h3><p>${portal}<br>${contact?'聯絡代碼':'帳號'}：${esc(user.username)}${contact?`<br>模擬 LINE 識別碼：${esc(linked?.demo_line_id||'未配對')}`:`<br>${esc(roles[user.role])}`}</p></div><div>${fixed?'<p class="muted small">IT 身分不取得住民照護與家屬案件權限。</p>':`<p class="small muted">${contact?'配對住民':'工作範圍'}</p><div class="access-grid">${data.residents.map(r=>`<label class="check"><input type="checkbox" data-access-user="${esc(user.id)}" data-access-resident="${esc(r.id)}" ${data.access.some(a=>a.user_id===user.id&&a.resident_id===r.id)?'checked':''}>${esc(r.label)}（${esc(r.id)}）</label>`).join('')}</div>`}</div></article>`;
  };
  $('#account-list').innerHTML=data.users.filter(u=>['admin','head_nurse','nurse','caregiver'].includes(u.role)).map(renderAccount).join('');
  $('#line-contact-list').innerHTML=data.users.filter(u=>['family','resident'].includes(u.role)).map(renderAccount).join('')||'<p class="muted">尚無 LINE 聯絡人配對。</p>';
}
function clearMonitor() {
  monitorState.sequence++;monitorState.current=null;monitorState.cursor=null;monitorState.next=null;monitorState.historyNext=null;monitorState.loading=false;
  monitorState.filters={status:'open',owner_id:'',from:'',to:'',limit:'10'};
  ['#monitor-stats','#monitor-rows','#monitor-case','#monitor-events','#monitor-scope','#monitor-result'].forEach(s=>$(s).replaceChildren());
  $('#monitor-filters').reset();$('#monitor-owner').innerHTML='<option value="">全部責任人</option><option value="__unassigned__">沒有責任 ID</option>';
  $('#monitor-title').textContent='';$('#monitor-next').disabled=true;$('#monitor-first').disabled=true;$('#monitor-older').disabled=true;
  if($('#monitor-dialog').open)$('#monitor-dialog').close();
}
const monitorDate=value=>value?new Date(value).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}):'—';
const monitorStatus={pending:'待接手',claimed:'已接手',closed:'已結案'};
const monitorOwner=c=>c.owner?.name||c.owner?.id||(c.status==='pending'?'尚未有人接手':'歷史責任身分待確認');
function monitorQuery(cursor=null) {
  const query=new URLSearchParams(Object.entries(monitorState.filters).filter(([,value])=>value!==''));
  if(cursor)query.set('cursor',cursor);
  return query.toString();
}
async function refreshMonitor(cursor=monitorState.cursor) {
  if(!supervisor()||monitorState.loading)return;
  monitorState.loading=true;monitorState.cursor=cursor;
  const epoch=appState.epoch,selected=monitorState.current;
  $('#monitor-result').textContent='正在載入授權範圍內的案件…';$('#monitor-rows').replaceChildren();$('#monitor-stats').replaceChildren();
  if(selected){$('#monitor-case').replaceChildren();$('#monitor-events').textContent='正在重新核對案件權限…';}
  $('#monitor-page').setAttribute('aria-busy','true');
  try {
    const data=await api('/api/case-monitor?'+monitorQuery(cursor));
    if(epoch!==appState.epoch||!supervisor())return;
    monitorState.next=data.next_cursor;
    const metrics=[['待接手',data.stats.pending_cases,'尚未有人接手'],['已接手',data.stats.claimed_cases,'按案件計算'],['交班待接受',data.stats.pending_handoffs,'包含於已接手，不重複加總'],['已結案',data.stats.closed_cases,'依目前篩選條件']];
    $('#monitor-stats').innerHTML=metrics.map(([label,n,note])=>`<div class="stat"><span>${label}</span><strong>${n}</strong><small>${note}</small></div>`).join('');
    $('#monitor-scope').textContent=`目前授權住民：${data.scope_resident_ids.join('、')||'無'} · 更新 ${monitorDate(data.updated_at)}`;
    $('#connection').textContent='最近同步 '+date(data.updated_at);
    $('#monitor-result').textContent=`符合篩選 ${data.stats.total_cases} 件，未結案 ${data.stats.open_cases} 件；本頁 ${data.cases.length} 件。${data.stats.stale_handoffs?`另有 ${data.stats.stale_handoffs} 件交班須重新確認。`:''}`;
    const chosen=monitorState.filters.owner_id;
    const choices=data.owners.some(o=>o.id===chosen)||!chosen||chosen==='__unassigned__'?data.owners:[...data.owners,{id:chosen,name:chosen}];
    $('#monitor-owner').innerHTML='<option value="">全部責任人</option><option value="__unassigned__">沒有責任 ID</option>'+choices.map(o=>`<option value="${esc(o.id)}">${esc(o.name||o.id)}（${esc(o.id)}）</option>`).join('');$('#monitor-owner').value=chosen;
    $('#monitor-rows').innerHTML=data.cases.length?data.cases.map(c=>`<tr><td><strong>案件 #${c.id} · ${esc(c.resident.label)}</strong><small>${esc(c.resident.bed_id||'未配置床位')} · ${esc(c.contact.name)}${c.contact.active?'':' · 配對停用'}</small></td><td>${esc(monitorStatus[c.status])}<small>訊息風險 ${esc(c.message_risk)}</small></td><td>${esc(monitorOwner(c))}<small>${esc(c.owner?.id||'')}${c.status==='claimed'&&c.owner&&!c.owner.valid?' · 權限待確認':''}</small></td><td>${esc(c.progress?.next_action||'尚未記錄下一步')}<small>${esc(c.progress?.waiting_for||'')}</small></td><td>${c.handoff?`${esc(c.handoff.to_name||c.handoff.to_user)}<small>${c.handoff.valid?'等待指定帳號接受':'內容或權限已變更，須重提'}</small>`:'—'}</td><td>${esc(monitorDate(c.created_at))}<small>期限：${c.due_at?'待機構確認':'未設定'}</small></td><td><button class="secondary" data-monitor-case="${c.id}">查看歷程</button></td></tr>`).join(''):'<tr><td colspan="7"><div class="empty">目前沒有符合條件的授權案件。</div></td></tr>';
    if(selected&&$('#monitor-dialog').open)await openMonitorCase(selected);
  } catch(error) {
    if(epoch!==appState.epoch)return;
    monitorState.next=null;
    if(error.status===409)monitorState.cursor=null;
    ['#monitor-stats','#monitor-rows','#monitor-case','#monitor-events','#monitor-scope'].forEach(s=>$(s).replaceChildren());
    $('#monitor-result').textContent='讀取失敗，監控資料已清除。'+error.message+' 請重新整理。';$('#connection').textContent='監控資料未同步';
    if($('#monitor-dialog').open)$('#monitor-events').textContent='未取得最新授權資料，請關閉後重新查詢。';
    if(error.status===403)await sessionView();
  } finally {
    if(epoch===appState.epoch){monitorState.loading=false;$('#monitor-page').setAttribute('aria-busy','false');$('#monitor-next').disabled=!monitorState.next;$('#monitor-first').disabled=!monitorState.cursor;}
  }
}
function monitorEvent(event) {
  const names={...actionNames,case_opened:'建立人工案件',message_received:'收到本機模擬訊息',legacy_snapshot:'升級前最新狀態快照',role_split_pending:'IT 職責分離，重新等待護理師接手'};
  const p=event.payload,progress=p.progress||p;
  const details=[progress.summary&&`已處理：${progress.summary}`,progress.next_action&&`下一步：${progress.next_action}`,progress.waiting_for&&`待確認：${progress.waiting_for}`,p.to_user&&`指定接班帳號：${p.to_user}`,p.from_user&&`原責任帳號：${p.from_user}`,p.operator_id&&`責任帳號：${p.operator_id}`,p.note&&`結案結果：${p.note}`,p.close_note&&`結案結果：${p.close_note}`].filter(Boolean);
  return `<article class="monitor-event"><header><strong>${esc(names[event.action]||event.action)}</strong><time>${esc(monitorDate(event.created_at))}</time></header><small>${esc(event.actor_name||event.actor||'系統紀錄')}${event.actor?`（${esc(event.actor)}）`:''}${p.legacy?' · 舊版紀錄':''}</small>${details.map(t=>`<p>${esc(t)}</p>`).join('')}</article>`;
}
async function openMonitorCase(caseId,older=false) {
  if(!supervisor())return;
  const epoch=appState.epoch,sequence=++monitorState.sequence;
  monitorState.current=caseId;
  if(!$('#monitor-dialog').open)$('#monitor-dialog').showModal();
  if(!older){$('#monitor-title').textContent='正在讀取案件';$('#monitor-case').replaceChildren();$('#monitor-events').textContent='正在核對權限並載入處理歷程…';}
  const params=new URLSearchParams({limit:'20'});if(older&&monitorState.historyNext)params.set('cursor',monitorState.historyNext);
  try {
    const data=await api(`/api/case-monitor/${caseId}/timeline?${params}`);
    if(epoch!==appState.epoch||sequence!==monitorState.sequence||!supervisor())return;
    const c=data.case;monitorState.historyNext=data.next_cursor;
    $('#monitor-title').textContent=`案件 #${c.id} · ${c.resident.label}`;
    $('#monitor-case').innerHTML=`<div class="info-block compact"><p>${esc(c.contact.name)} · ${esc(monitorStatus[c.status])}</p><p>責任人：${esc(monitorOwner(c))} ${esc(c.owner?.id||'')} · 期限：${c.due_at?'待機構確認':'未設定'}</p><p>已處理：${esc(c.progress?.summary||'尚未記錄')}</p><p>下一步：${esc(c.progress?.next_action||'尚未記錄')}</p>${c.close_note?`<p>結案結果：${esc(c.close_note)}</p>`:''}</div><p class="small muted">${esc(data.history_note)} · 讀取 ${esc(monitorDate(data.updated_at))}</p>`;
    const html=data.events.map(monitorEvent).join('');
    if(older)$('#monitor-events').insertAdjacentHTML('beforeend',html);else $('#monitor-events').innerHTML=html||'<p class="empty">尚無處理事件。</p>';
    $('#monitor-older').disabled=!data.next_cursor;
  } catch(error) {
    if(epoch!==appState.epoch||sequence!==monitorState.sequence)return;
    $('#monitor-title').textContent='無法讀取案件';$('#monitor-case').replaceChildren();$('#monitor-events').textContent=error.message;$('#monitor-older').disabled=true;monitorState.historyNext=null;
    if(error.status===403)await sessionView();
  }
}
function selectTab(tab) {
  if(tab!=='records'&&!assessor())tab='records';
  $$('.tab-pane').forEach(el=>el.hidden=el.id!==tab+'-tab');$$('[data-tab]').forEach(el=>{el.classList.toggle('active',el.dataset.tab===tab);el.setAttribute('aria-selected',String(el.dataset.tab===tab));});
}
async function openResident(rid,tab='records',cid=null) {
  appState.rid=rid;appState.progressDirty=false;appState.progressCase=null;selectTab(tab);$('#observation-form').reset();$('#message-form').reset();$('#human-reply-form').reset();$('#resolve-form').reset();
  $('#test-tools').open=false;
  const local = new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16);$('#observed-time').value=local;
  await loadResident(cid,true); $$('#resident-dialog form').forEach(rememberForm);if(!$('#resident-dialog').open)$('#resident-dialog').showModal();
}
async function loadResident(cid=appState.cid,resetConversation=false) {
  if(!appState.rid)return;
  const epoch=appState.epoch,rid=appState.rid;
  const data=await api('/api/residents/'+appState.rid+(assessor()&&cid?'?conversation_id='+encodeURIComponent(cid):''));
  if(epoch!==appState.epoch||rid!==appState.rid||!staff())return;
  if(assessor()&&!resetConversation && appState.detail?.selected_conversation?.id===data.selected_conversation.id &&
     appState.detail?.case?.id!==data.case?.id &&
     ['#human-reply-form','#resolve-form','#progress-form'].some(id=>formChanged($(id)))){
    throw new Error('案件已變更。本頁未保存內容仍保留，請先另存或清除，再更新紀錄；目前內容不能直接用於新案件。');
  }
  if(resetConversation){
    ['#message-form','#human-reply-form','#resolve-form','#progress-form'].forEach(id=>$(id).reset());
    appState.progressDirty=false;appState.progressCase=null;
  }
  appState.detail=data;appState.cid=data.selected_conversation?.id||null;
  $('#conversation-select').innerHTML=(data.conversations||[]).map(t=>`<option value="${esc(t.id)}">${esc(t.label)}${t.active?'':'（配對已撤銷）'}</option>`).join('');
  $('#conversation-select').value=appState.cid;
  const thread=data.selected_conversation;
  $('#conversation-recipient').textContent=!thread?'':thread.kind==='contact'
    ? `目前對話：${thread.label}。${thread.active?'人工回覆僅記錄於此聯絡人的對話；尚未傳送 LINE。':'配對已撤銷，暫停新訊息與回覆；既有紀錄保留供院內處理。'}`
    : '院內測試與舊版紀錄，沒有對外收件者。聯絡人對話請由上方選單切換。';
  $('#detail-synced').textContent='此視窗讀取於 '+date(new Date().toISOString())+'；按「更新紀錄」取得後續變更。';
  $('#resident-title').textContent=data.resident.label;$('#resident-code').textContent=`${data.resident.ward} · ${data.resident.bed_id} · ${data.resident.id}`;
  $('#observation-list').innerHTML=data.observations.length?data.observations.map(o=>`<article class="observation"><header><strong>${esc(date(o.observed_at))} · ${esc(o.source)}</strong>${badge(o.care_status)}</header><div class="vitals">${vital('體溫',o.values.temperature_c,'°C')}${vital('脈搏',o.values.pulse_bpm,'次／分')}${vital('血氧',o.values.spo2_pct,'%')}${vital('收縮壓',o.values.systolic_mmhg,'mmHg')}${vital('舒張壓',o.values.diastolic_mmhg,'mmHg')}</div><p>${esc(o.note)}</p><small>來源紀錄 ${esc(o.source_record_id)} · 入庫 ${esc(date(o.received_at))} · 記錄者 ${esc(roles[o.entered_by]||o.entered_by)}</small></article>`).join(''):'<div class="empty">尚無照護紀錄。量測缺值以「—」呈現。</div>';
  if(assessor()){renderMessages(data);renderHandling(data);}else{clearProtectedDetail();selectTab('records');}
  roleVisibility();
  if(resetConversation)['#message-form','#human-reply-form','#resolve-form','#progress-form'].forEach(id=>rememberForm($(id)));
  if(assessor()) {
    const body=await api('/api/beds');$('#move-bed').innerHTML=body.beds.filter(b=>!b.resident_id||b.resident_id===appState.rid).map(b=>`<option value="${esc(b.id)}" ${b.resident_id===appState.rid?'selected':''}>${esc(b.id)}${b.resident_id?'（目前床位）':'（空床）'}</option>`).join('');
  }
}
function clearProtectedDetail() {
  ['#conversation-select','#conversation-recipient','#line-actor','#handoff-target','#message-list','#audit-list','#case-summary','#draft-list','#case-context','#saved-progress','#handoff-status','#case-history'].forEach(s=>$(s).replaceChildren());
  ['#message-form','#human-reply-form','#resolve-form','#progress-form'].forEach(s=>$(s).reset());
  $('#test-tools').hidden=true;$('#progress-form').hidden=true;$('#human-reply-form').hidden=true;$('#resolve-form').hidden=true;
}
function renderMessages(data) {
  const thread=data.selected_conversation;
  $('#line-actor').innerHTML=(data.line_contacts||[]).map(u=>`<option value="${esc(u.id)}">${esc(u.display_name)}（${esc(roles[u.role])}）</option>`).join('');
  $('#line-actor').value=thread.contact_id||'';
  $('#message-channel').value=thread.kind==='contact'?'demo_line':'web';
  $('#message-channel').disabled=true;$('#line-actor').disabled=true;
  $('#test-tools').hidden=!thread.active || thread.kind==='contact'&&!assessor();
  messageSourceView();
  $('#message-list').innerHTML=data.messages.length?data.messages.map(m=>{
    const incoming=m.actor==='user';
    const actor=incoming?(m.author||'體驗帳號'):['operator','human'].includes(m.actor)?(m.author||'工作人員回覆'):'系統回覆';
    const channel=incoming?(m.input_channel==='demo_line'?'模擬 LINE':'網頁'):'本機訊息紀錄';
    return `<article class="message ${incoming?'incoming':''}"><div class="message-meta">${esc(actor)} · ${channel} · ${esc(date(m.created_at))}</div><p>${esc(m.text)}</p></article>`;
  }).join(''):'<div class="empty">還沒有詢問紀錄。可先用虛構訊息測試服務摘要與轉人工流程。</div>';
  $('#message-list').scrollTop=$('#message-list').scrollHeight;
}
function messageSourceView() {$('#line-actor-label').hidden=$('#message-channel').value!=='demo_line';}
function renderHandling(data) {
  const c=data.case;const owns=c?.status==='claimed'&&c.operator_id===appState.user.id;
  $('#human-reply-form').hidden=!owns||!data.selected_conversation.active;$('#resolve-form').hidden=!owns;
  $('#resolve-form button').textContent=data.selected_conversation.active?'結案並恢復自動處理':'結案並保留配對停用';
  $('#case-summary').innerHTML=c?`<div class="case-block"><span class="eyebrow">案件 #${esc(c.id)} · 訊息風險 ${esc(c.trigger_risk)}</span><h3>${esc(states[data.state])}</h3><p>${!data.selected_conversation.active?'配對已撤銷；可依權限接手、記錄進度或結案，無法送出回覆。':c.status==='pending'?'接手後可人工回覆；完成後填寫結果並結案。':`目前接手帳號：${esc(c.operator)}。此聯絡人的一般訊息會持續記錄於同一案件。`}</p>${c.status==='pending'?'<button class="primary" id="claim-case">接手此案件</button>':''}</div>`:'<div class="empty">目前沒有未結案事件。是否可自動回覆仍依聯絡人配對、風險與資料範圍判定。</div>';
  renderWorkflow(data,owns);
  $('#draft-list').innerHTML=data.drafts.filter(j=>j.status==='draft').map(j=>`<form class="draft" data-draft="${j.id}"><h3>待審草稿 #${j.id}</h3><label>核准後的回覆<textarea name="text" rows="4" maxlength="2000" required>${esc(j.response_text||'')}</textarea></label><label>審閱紀錄<input name="note" maxlength="1000" required></label><div class="draft-actions"><button class="primary" type="submit" ${owns&&data.selected_conversation.active?'':'disabled'}>核准回覆</button><button class="secondary" type="button" data-reject="${j.id}" ${owns?'':'disabled'}>退回草稿</button></div></form>`).join('');
  $$('#draft-list form').forEach(rememberForm);
  $('#audit-list').innerHTML=data.audit.map(a=>`<div class="audit-row">${esc(date(a.created_at))} · ${esc(roles[a.actor]||a.actor)} · ${esc(actionNames[a.action]||a.action)}<br>${esc(a.detail)}</div>`).join('')||'<p class="muted">尚無操作紀錄。</p>';
}
function loadProgressValues() {
  const data=appState.detail;const note=data?.workflow?.note;
  $('#progress-summary').value=note?.summary||'';$('#progress-next').value=note?.next_action||'';$('#progress-waiting').value=note?.waiting_for||'';
  appState.noteRevision=note?.revision||0;appState.progressDirty=false;appState.progressCase=data?.case?.id||null;
  rememberForm($('#progress-form'));
}
function renderWorkflow(data,owns) {
  const w=data.workflow;const context=w?.context;const h=w?.handoff;
  $('#case-context').innerHTML=context?`<div class="context-panel"><h3>為什麼需要人員處理</h3><p>${esc(context.reason)}</p>${context.evidence?`<details><summary>查看相關訊息分級紀錄</summary><p>訊息：${esc(context.evidence.text)}</p><p>紀錄說明：${esc(context.evidence.rationale)}</p><p class="small muted">顯示最近一筆符合案件風險層級的紀錄，未替代住民照護評估。</p></details>`:''}<h4>近期使用者訊息</h4>${context.recent_inputs.map(m=>`<p class="context-message"><small>${esc(date(m.created_at))}</small><br>${esc(m.text)}</p>`).join('')}${context.last_service_reply?`<details><summary>系統先前提供的服務資料回覆</summary><p class="preserve-lines">${esc(context.last_service_reply.text)}</p></details>`:''}</div>`:'';
  const saved=h||(!owns?w?.note:null);
  $('#saved-progress').innerHTML=saved?`<div class="context-panel"><h3>${h?'本次交班內容':'已保存處理進度'}</h3><p class="preserve-lines"><strong>已處理內容</strong><br>${esc(saved.summary)}</p><p class="preserve-lines"><strong>下一步</strong><br>${esc(saved.next_action)}</p><p class="preserve-lines"><strong>待確認事項</strong><br>${esc(saved.waiting_for||'未填寫')}</p><p class="small muted">${h?`提出者：${esc(h.from_name)} · ${esc(date(h.created_at))}`:`填寫者：${esc(w.note.updated_name)} · ${esc(date(w.note.updated_at))}`} · 人員填寫紀錄</p></div>`:'';
  $('#handoff-status').innerHTML=h?`<div class="handoff-notice"><strong>交班待確認：${esc(h.from_name)} → ${esc(h.to_name)}</strong><p>確認接收前，仍由 ${esc(h.from_name)} 負責。</p>${h.stale?'<p class="error">交班提出後有新訊息或回覆；原接手者需更新內容並重新提出交班。</p>':''}${h.to_user===appState.user.id?`<button class="primary" id="accept-handoff" data-request="${h.id}" ${h.stale?'disabled':''}>確認接收交班</button>`:''}${owns?'<button class="secondary" id="cancel-handoff">取消交班</button>':''}</div>`:'';
  $('#progress-form').hidden=!owns;
  if(appState.progressCase!==data.case?.id || !appState.progressDirty)loadProgressValues();
  $('#progress-saved').textContent=w?.note?`已保存：${w.note.updated_name} · ${date(w.note.updated_at)}${appState.progressDirty?' · 本頁尚有未保存內容':''}`:'尚未保存處理進度。';
  const selected=$('#handoff-target').value;
  $('#handoff-target').innerHTML=(w?.peers||[]).map(u=>`<option value="${esc(u.id)}">${esc(u.display_name)}</option>`).join('');
  if((w?.peers||[]).some(u=>u.id===selected))$('#handoff-target').value=selected;
  $('#case-history').innerHTML=(w?.history||[]).map(item=>`<div class="history-item"><strong>案件 #${item.id} · ${esc(date(item.closed_at))}</strong><p>處理者：${esc(item.operator||'未記錄')}</p>${item.summary?`<p>已處理：${esc(item.summary)}</p>`:''}<p>結案紀錄：${esc(item.close_note||'未記錄')}</p></div>`).join('')||'<p class="muted small">尚無已結案紀錄。</p>';
}
function progressPayload() {return {summary:$('#progress-summary').value,next_action:$('#progress-next').value,waiting_for:$('#progress-waiting').value,revision:appState.noteRevision};}
function casePayload(payload={}) {return {...payload,conversation_id:appState.cid,case_id:appState.detail?.case?.id};}
async function caseAction(action,payload={}) {
  await api(`/api/residents/${appState.rid}/case/${action}`,casePayload(payload));await loadResident();await refreshBoard();
}
$('#login-form').addEventListener('submit',event=>{event.preventDefault();perform(async()=>{
  $('#login-error').textContent='';
  appState.epoch++;
  try {const result=await api('/api/login',{username:$('#username').value,password:$('#password').value});appState.csrf=result.csrf;$('#password').value='';await sessionView();}
  catch(error){$('#login-error').textContent=error.message;}
},$('button[type="submit"]',event.currentTarget));});
$('#logout').addEventListener('click',async()=>{if(await allowResidentExit())perform(async()=>{appState.epoch++;await api('/api/logout',{});await sessionView();},$('#logout'));});
$$('[data-page]').forEach(el=>el.addEventListener('click',()=>perform(()=>showPage(el.dataset.page),el)));
$('#refresh').addEventListener('click',()=>perform(async()=>{await showPage(appState.page);if($('#resident-dialog').open)await loadResident();},$('#refresh')));
$('#board-filter').addEventListener('change',renderBoard);
$('#queue-filter').addEventListener('change',renderQueue);
$('#work-queue').addEventListener('click',event=>{const el=event.target.closest('[data-work-resident]');if(el)perform(()=>openResident(el.dataset.workResident,assessor()?'handling':'messages',el.dataset.workConversation),el);});
$('#care-followups').addEventListener('click',event=>{const el=event.target.closest('[data-followup-resident]');if(el)perform(()=>openResident(el.dataset.followupResident,'records'),el);});
$('#resident-cards').addEventListener('click',event=>{const el=event.target.closest('[data-resident]');if(el)perform(()=>openResident(el.dataset.resident),el);});
$('#close-dialog').addEventListener('click',closeResident);
$('#refresh-detail').addEventListener('click',async()=>{
  if($$('#draft-list form').some(formChanged)&&!await confirmDiscard('更新紀錄會重新載入待審草稿；未保存的草稿修改將被取代。'))return;
  perform(async()=>{await loadResident();await refreshBoard();},$('#refresh-detail'));
});
$('#resident-dialog').addEventListener('cancel',event=>{event.preventDefault();closeResident();});
$('#resident-dialog').addEventListener('close',()=>{appState.rid=null;appState.cid=null;});
$('#conversation-select').addEventListener('change',async()=>{
  const next=$('#conversation-select').value;$('#conversation-select').value=appState.cid;
  if(appState.busy)return;
  const forms=['#message-form','#human-reply-form','#resolve-form','#progress-form'].map(id=>$(id));
  if((forms.some(formChanged)||$$('#draft-list form').some(formChanged)) &&
     !await confirmDiscard('切換對話會清除尚未保存的訊息、人工回覆與處理進度；照護回報表單保留。'))return;
  perform(()=>loadResident(next,true),$('#conversation-select'));
});
window.addEventListener('beforeunload',event=>{if(unsavedResidentForms()||appState.busy){event.preventDefault();event.returnValue='';}});
$$('[data-tab]').forEach(el=>el.addEventListener('click',()=>selectTab(el.dataset.tab)));
$('#observation-form').addEventListener('submit',event=>{event.preventDefault();perform(async()=>{
  const payload=Object.fromEntries(new FormData(event.currentTarget));payload.observed_at=new Date($('#observed-time').value).toISOString();payload.care_status=$('#care-status').value;
  await api(`/api/residents/${appState.rid}/observation`,payload);event.target.reset();$('#observed-time').value=new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16);rememberForm($('#observation-form'));await loadResident();await refreshBoard();toast('照護回報已保存。');
},$('button[type="submit"]',event.currentTarget));});
$('#message-form').addEventListener('submit',event=>{event.preventDefault();perform(async()=>{
  await api(`/api/residents/${appState.rid}/message`,{text:$('#message-text').value,channel:$('#message-channel').value,line_actor:$('#line-actor').value,conversation_id:appState.cid});$('#message-text').value='';await loadResident();rememberForm($('#message-form'));await refreshBoard();toast('測試訊息已寫入本機紀錄，未送往 LINE。');
},$('button[type="submit"]',event.currentTarget));});
$('#message-channel').addEventListener('change',messageSourceView);
$('#case-summary').addEventListener('click',event=>{if(event.target.closest('#claim-case'))perform(()=>caseAction('claim'),event.target);});
$('#progress-form').addEventListener('input',event=>{if(event.target.id!=='handoff-target'){appState.progressDirty=true;$('#progress-saved').textContent='本頁內容尚未保存。';}});
$('#progress-form').addEventListener('submit',event=>{event.preventDefault();perform(async()=>{await api(`/api/residents/${appState.rid}/case/progress`,casePayload(progressPayload()));appState.progressDirty=false;await loadResident();await refreshBoard();toast('處理進度已保存。');},$('button[type="submit"]',event.currentTarget));});
$('#reload-progress').addEventListener('click',async()=>{
  if(formChanged($('#progress-form'))&&!await confirmDiscard('重新載入將取代本頁尚未保存的進度，並顯示資料庫中已保存的內容。'))return;
  perform(async()=>{await loadResident();loadProgressValues();renderHandling(appState.detail);toast('已載入保存的進度。');},$('#reload-progress'));
});
$('#propose-handoff').addEventListener('click',()=>perform(async()=>{if(!$('#progress-form').reportValidity())return;await api(`/api/residents/${appState.rid}/case/handoff`,casePayload({...progressPayload(),to_user:$('#handoff-target').value}));appState.progressDirty=false;await loadResident();await refreshBoard();toast('交班已提出；對方確認前仍由你負責。');},$('#propose-handoff')));
$('#handoff-status').addEventListener('click',event=>{const accept=event.target.closest('#accept-handoff'),cancel=event.target.closest('#cancel-handoff');if(accept)perform(async()=>{await caseAction('accept_handoff',{request_id:Number(accept.dataset.request)});toast('已接收交班，案件持續人工處理。');},accept);if(cancel)perform(async()=>{await caseAction('cancel_handoff');toast('交班已取消。');},cancel);});
$('#human-reply-form').addEventListener('submit',event=>{event.preventDefault();perform(async()=>{await caseAction('reply',{text:$('#human-reply').value});$('#human-reply').value='';rememberForm($('#human-reply-form'));toast('人工回覆已記錄；案件尚未結案。');},$('button',event.currentTarget));});
$('#resolve-form').addEventListener('submit',event=>{event.preventDefault();perform(async()=>{
  const payload=casePayload({note:$('#resolve-note').value});
  await api(`/api/residents/${appState.rid}/case/resolve`,payload);
  $('#resolve-note').value='';rememberForm($('#resolve-form'));
  appState.progressDirty=false;rememberForm($('#progress-form'));
  await loadResident(appState.cid,true);await refreshBoard();toast('案件已結案。');
},$('button',event.currentTarget));});
$('#draft-list').addEventListener('submit',event=>{event.preventDefault();const form=event.target.closest('[data-draft]');if(form)perform(()=>caseAction('approve',{job_id:Number(form.dataset.draft),...Object.fromEntries(new FormData(form))}),$('button[type="submit"]',form));});
$('#draft-list').addEventListener('click',event=>{const el=event.target.closest('[data-reject]');if(el){const form=el.closest('form');perform(()=>caseAction('reject',{job_id:Number(el.dataset.reject),note:$('input[name="note"]',form).value}),el);}});
$('#move-submit').addEventListener('click',()=>perform(async()=>{await api(`/api/residents/${appState.rid}/move`,{bed_id:$('#move-bed').value});await loadResident();await refreshBoard();toast('床位已更新，住民紀錄仍保留。');},$('#move-submit')));
$('#csv-file').addEventListener('change',()=>perform(async()=>{const file=$('#csv-file').files[0];if(file){if(file.size>1000000)throw new Error('檔案須小於 1 MB。');$('#csv-text').value=await file.text();}}));
$('#import-submit').addEventListener('click',()=>perform(async()=>{
  $('#import-result').textContent='';const result=await api('/api/import',{csv:$('#csv-text').value,synthetic_confirmed:$('#synthetic-confirmed').checked});$('#import-result').textContent=`完成：新增 ${result.inserted} 筆、略過相同紀錄 ${result.skipped} 筆。`;await refreshBoard();toast('院內測試資料已匯入。');
},$('#import-submit')));
function changeAccess(event) {const el=event.target.closest('[data-access-user]');const contact=event.currentTarget.id==='line-contact-list';if(el)perform(async()=>{try{await api('/api/bindings',{user_id:el.dataset.accessUser,resident_id:el.dataset.accessResident,allowed:el.checked});toast(contact?'LINE 聯絡人配對已更新。':'人員工作範圍已更新。');}finally{await loadAccounts();}},el);}
$('#account-list').addEventListener('change',changeAccess);
$('#line-contact-list').addEventListener('change',changeAccess);
$('#monitor-filters').addEventListener('submit',event=>{event.preventDefault();perform(async()=>{
  const values=Object.fromEntries(new FormData(event.currentTarget));
  for(const key of ['from','to'])if(values[key])values[key]=new Date(values[key]+'+08:00').toISOString();
  monitorState.filters=values;monitorState.cursor=null;await refreshMonitor(null);
},$('button[type="submit"]',event.currentTarget));});
$('#monitor-reset').addEventListener('click',()=>perform(async()=>{clearMonitor();await refreshMonitor(null);},$('#monitor-reset')));
$('#monitor-first').addEventListener('click',()=>perform(()=>refreshMonitor(null),$('#monitor-first')));
$('#monitor-next').addEventListener('click',()=>perform(()=>refreshMonitor(monitorState.next),$('#monitor-next')));
$('#monitor-rows').addEventListener('click',event=>{const el=event.target.closest('[data-monitor-case]');if(el)perform(()=>openMonitorCase(Number(el.dataset.monitorCase)),el);});
$('#monitor-close').addEventListener('click',()=>$('#monitor-dialog').close());
$('#monitor-dialog').addEventListener('close',()=>{monitorState.sequence++;monitorState.current=null;monitorState.historyNext=null;$('#monitor-title').textContent='';$('#monitor-case').replaceChildren();$('#monitor-events').replaceChildren();});
$('#monitor-older').addEventListener('click',()=>perform(()=>openMonitorCase(monitorState.current,true),$('#monitor-older')));
setInterval(()=>{if(appState.user&&!document.hidden&&!appState.busy){if(supervisor()&&appState.page==='monitor'&&!$('#monitor-filters').contains(document.activeElement))refreshMonitor().catch(()=>{});else if(staff()&&appState.page==='board')refreshBoard().catch(()=>{});}},15000);
sessionView().catch(error=>{$('#login-error').textContent=error.message;});
