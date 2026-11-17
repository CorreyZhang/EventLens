/* Browser chat adapter. Uses the existing validated FastAPI research and
   evidence APIs. It deliberately does not impersonate native DSH or enable
   any Harness filesystem/terminal tools on this anonymous public service. */
(() => {
  const thread = document.querySelector('#thread');
  const form = document.querySelector('#composer');
  const input = document.querySelector('#prompt');
  const submit = document.querySelector('#submit');
  const status = document.querySelector('#status');
  const refs = document.querySelector('#references');
  const newStudy = document.querySelector('#newStudy');
  let current = null, busy = false, pendingRefs = [], history = [], polling = 0;
  const escapeText = x => String(x ?? '').replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeLink = x => /^https:\/\/[^\s]+$/i.test(String(x||'')) ? x : '';
  async function api(path, body) {
    const response = await fetch('/api/' + path,
      body === undefined ? {} :
      {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    let result;
    try { result = await response.json(); }
    catch {throw Error('服务器返回的内容无法读取（HTTP ' + response.status + '）');}
    if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : 'HTTP ' + response.status);
    return result;
  }
  function emit() {
    if (!current) return;
    window.parent.postMessage({type:'eventlens:cloud-study',research_id:current.id,
      question:current.question},location.origin);
  }
  function setStatus(s, isError=false) {
    status.textContent=s;
    status.classList.toggle('error', isError);
  }
  function render() {
    if (!history.length) {
      thread.innerHTML='<div class="hello"><h2>问一问，追到来源。</h2><p>输入公司、政策或投资事件。研究完成后<br>左侧自动显示时间线与证据。</p><div class="hints"><button type="button" data-example="同花顺最新季度报告有哪些事实？请查找原始公告">核对同花顺最新季报</button><button type="button" data-example="宁德时代近期有哪些重要公告？区分事实与观点">整理宁德时代近期事件</button></div></div>';
      return;
    }
    thread.innerHTML=history.map(m => m.role === 'user'
      ? '<div class="bubble user">'+escapeText(m.text)+'</div>'
      : '<section class="bubble ai"><span class="mark">EVENTLENS · 证据整理</span>'
      + (m.html || '<p>'+escapeText(m.text)+'</p>') + '</section>').join('');
    thread.scrollTop=thread.scrollHeight;
  }
  function add(role, text, html) {
    history.push({role,text,html});render();
  }
  function reportHtml(r) {
    const events=(r.events||[]).slice(0,4);
    const sources=r.sources||[];
    const sourceById=new Map(sources.map(s=>[s.id,s]));
    const intro='<p>研究完成：找到 <strong>'+r.claims.length+
      '</strong> 条通过原文定位的候选陈述、<strong>'+r.events.length+
      '</strong> 个事件。左侧可按时间查看与切换证据。</p>';
    const lines=events.map((e,i)=>{
      const source=sourceById.get((e.source_ids||[])[0]);
      const link=source&&safeLink(source.url)
        ? ' <a target="_blank" rel="noopener noreferrer" href="'+escapeText(source.url)+'">原始来源 ↗</a>'
        : '';
      return '<div class="line"><span class="num">'+(i+1)+'.</span><div><b>'+
        escapeText(e.subject || '研究对象')+' · '+escapeText(e.action || '待归并事件')+
        '</b><p>'+escapeText(e.state||'目前仍需复核')+'</p>'+
        (source?'<div class="proof">'+escapeText(source.title||'来源')+link+'</div>':'')+
        '</div></div>';
    }).join('');
    return intro+lines+'<p class="meta">引文定位 ≠ 原站独立核实；同期价格变化不代表事件因果。可继续追问。</p>';
  }
  function answerHtml(m) {
    if (!m) return '<p>暂未得到有效的追问结果。</p>';
    const answers=(m.answers||[]).map(a=>{
      const citations=(a.refs||[]).map(ref=>{
        const source=(current?.data?.sources||[]).find(s=>s.id===ref.source_id);
        const href=source&&safeLink(source.url)
          ? '<a href="'+escapeText(source.url)+'" target="_blank" rel="noopener noreferrer">查看原始来源 ↗</a>'
          : '';
        return '<div class="proof">'+escapeText(ref.quote||'原文引用')+'<br>'+href+'</div>';
      }).join('');
      return '<p>'+escapeText(a.text||'')+'</p>'+citations;
    }).join('');
    return (answers||'<p>没有生成可核实回答。</p>')+
      (m.unknowns||[]).map(v=>'<div class="proof">尚无法证实：'+escapeText(v)+'</div>').join('');
  }
  function setBusy(v) {busy=v; submit.disabled=v; newStudy.disabled=v; input.disabled=v;}
  async function poll(id) {
    const snapshot=await api('research/'+id);
    if (!current || current.id!==id) return;
    current.data=snapshot;
    const phase=snapshot.status;
    if (phase==='queued' || phase==='running') {
      const last=(snapshot.steps||[]).at(-1);
      setStatus('正在研究 · '+(last?.name||'准备检索')+'；真实来源未取得前不会生成事件。');
      clearTimeout(polling);
      polling=setTimeout(()=>poll(id).catch(e=>{setStatus(e.message,true);setBusy(false)}),1600);
      return;
    }
    clearTimeout(polling);
    if (phase==='failed') {
      const last=(snapshot.steps||[]).at(-1);
      add('ai','研究失败：'+(last?.detail||'未获取通过验证的证据'));
      setStatus('研究未通过证据校验，请检查 DeepSeek 权限/余额/检索结果。',true);
    } else {
      add('ai','',reportHtml(snapshot));
      setStatus('研究已保存；事件、引用和历史版本在左侧。');
    }
    setBusy(false);
  }
  async function start(question) {
    setBusy(true);add('user',question);setStatus('正在创建研究任务…');
    try {
      const result=await api('research',{question,mode:'live'});
      current={id:result.id,question,data:null};
      emit();
      await poll(result.id);
    } catch(e) {
      add('ai','无法创建研究：'+e.message);
      setStatus(e.message,true);setBusy(false);
    }
  }
  async function ask(question) {
    setBusy(true);add('user',question);
    setStatus('正在依据已保存的真实来源追问…');
    try {
      const response=await api('research/'+current.id+'/ask',
        {question,refresh:false,source_ids:[...new Set(pendingRefs.map(r=>r.source_id))]});
      pendingRefs=[];displayRefs();
      const refreshed=await api('research/'+current.id);
      current.data=refreshed;
      add('ai','',answerHtml(response));
      setStatus('追问已完成；回答只引用当前研究中已校验的来源。');
    } catch(e) {
      add('ai','追问失败：'+e.message);
      setStatus(e.message,true);
    } finally {setBusy(false);}
  }
  function displayRefs() {
    refs.classList.toggle('visible',pendingRefs.length>0);
    refs.textContent=pendingRefs.length
      ? '下一次提问附带 '+pendingRefs.length+' 份左侧选中的原文证据'
      : '';
  }
  form.addEventListener('submit',async e=>{
    e.preventDefault();
    const question=input.value.trim();
    if (busy || question.length<3) {setStatus('请提出具体公司、行业或投资事件问题。',true);return;}
    input.value='';
    if (!current) await start(question);
    else if (!current.data || ['failed','queued','running'].includes(current.data.status)) {
      setStatus('本研究尚未形成可追问的证据；请点“新对话”后改问具体事件。',true);
      input.value=question;
    } else await ask(question);
  });
  input.addEventListener('keydown',e=>{
    if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing) {e.preventDefault();form.requestSubmit();}
  });
  newStudy.addEventListener('click',()=>{
    if(busy)return;
    clearTimeout(polling);current=null;pendingRefs=[];displayRefs();history=[];
    render();setStatus('新对话已开始；公开体验最多两项研究、三次追问。');input.focus();
  });
  thread.addEventListener('click',e=>{
    const button=e.target.closest('[data-example]');
    if(button){input.value=button.dataset.example||'';input.focus();}
  });
  window.addEventListener('message',e=>{
    if(e.origin!==location.origin||e.source!==window.parent)return;
    const m=e.data;
    if(m?.type!=='eventlens:cloud-quote'||!current||
        m.reference?.research_id!==current.id)return;
    const r=m.reference;
    if(typeof r.source_id!=='string'||typeof r.quote!=='string')return;
    if(!pendingRefs.some(v=>v.source_id===r.source_id))pendingRefs.push(r);
    displayRefs();
  });
  api('research').then(rows=>{
    const row=rows.find(r=>['complete','partial','queued','running'].includes(r.status));
    if(!row)return;
    current={id:row.id,question:row.question,data:null};emit();setBusy(true);
    poll(row.id).catch(e=>{setStatus(e.message,true);setBusy(false)});
  }).catch(()=>{});
})();
