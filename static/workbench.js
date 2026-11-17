/* v0.3 extension: retain research, source drawer, versions and judgment storage. */
if(new URLSearchParams(location.search).has('embedded'))document.body.classList.add('embedded');
let lensControlsResearch=null;
let lens=null,selectedEvent=null,lensChart=null,candle=null,markerPlugin=null,compareChart=null,lensKey='',requestSerial=0;
let activeResearchFocus=null,focusRevision=0;
// In embedded mode, the native Harness session's server-bound topic is the
// source of truth; no ticker or prior research can become a fallback.
function clearOldFocus(label){
 ++requestSerial;
 lens=null;selectedEvent=null;lensKey='';
 $('#chartTitle').textContent=label||'当前研究';
 $('#stockName').textContent='当前研究对象';
 $('#marketValue').textContent='—';
 $('#windowReturn').textContent='';
 $('#chartEmpty').hidden=false;
 $('#chartEmpty').textContent='当前对象尚未取得已验证的对应行情，绝不以其他股票替代。';
 $('#eventTrack').innerHTML='<p class="empty">正在同步「'+esc(label||'新研究')+'」的证据时间线…</p>';
 $('#nodeTitle').textContent='「'+(label||'新研究')+'」的事件证据';
 $('#nodeSummary').innerHTML='<p class="node-empty">仅展示当前研究对象的已校验事件；旧话题新闻不再沿用。</p>';
}

$('#nodeChat').append($('#conversation'));
$('#personalNote').append($('.judgment'));
const previousRender=render;
render=function(r){previousRender(r);document.body.classList.add('has-result');$('#taskTitle').textContent=['queued','running'].includes(r.status)?'正在研究 · '+(r.steps.at(-1)?.name||'准备资料'):(r.claims.length?`研究已更新 · ${r.claims.length} 条引文`:'尚无当前主体的可验证证据');$('#taskTitle').title=r.question;$('#crumb').textContent=topicLabel(r.question);$('#aiStatus').textContent=['queued','running'].includes(r.status)?'工具执行进度可展开查看':`${r.sources.length} 份材料 · ${r.versions.length} 个版本`; localStorage.setItem('eventlens.lastResearch',r.id);location.hash=r.id;if(lensControlsResearch!==r.id){lensControlsResearch=r.id;activeResearchFocus=null;++focusRevision;lens=null;selectedEvent=null;lensKey='';$('#eventTrack').innerHTML='<p class="empty">正在生成本次研究的事件时间线…</p>';$('#nodeTitle').textContent='正在整理新研究';$('#nodeSummary').innerHTML='<p class="node-empty">等待本研究的真实证据。</p>';$('#chartTitle').textContent='等待当前标的行情';$('#marketValue').textContent='—';$('#windowReturn').textContent='';if(document.activeElement!==$('#question'))$('#question').value=r.question;defaultMarketWindow(r);try{const saved=JSON.parse(localStorage.getItem('eventlens.window.'+r.id));if(saved&&[...$('#lensSymbol').options].some(o=>o.value===saved.symbol)&&('NONE'===inferMarketSymbol(r.question)||inferMarketSymbol(r.question)===saved.symbol)){$('#lensSymbol').value=saved.symbol;$('#lensProvider').value=saved.provider;$('#lensStart').value=saved.start;$('#lensEnd').value=saved.end}}catch{}}loadLens(r);if(lens?.research_id===r.id)renderScopedMessages()};

// Only an explicitly named, supported security may focus the K-line.
// For generic or multi-company questions the neutral "NONE" view is safe.
function inferMarketSymbol(question){
 const q=String(question||'');
 const matches=[];
 if(/(?:\bNVDA\b|\bNVIDIA\b|英伟达|黄仁勋)/i.test(q))matches.push('NVDA');
 if(/(?:\bAAPL\b|\bApple\b|苹果(?!汁|派|醋|树))/i.test(q))matches.push('AAPL');
 if(/(?:300033(?:\.SZ)?|同花顺)/i.test(q))matches.push('300033.SZ');
 if(/(?:300750(?:\.SZ)?|宁德时代|\bCATL\b)/i.test(q))matches.push('300750.SZ');
 if(/(?:\bTSM\b|台积电)/i.test(q))matches.push('TSM');
 if(/\bQQQ\b/i.test(q))matches.push('QQQ');
 if(/\bSMH\b/i.test(q))matches.push('SMH');
 return matches.length===1?matches[0]:'NONE';
}
function eventMatchesSymbol(event,symbol){
 if(symbol==='NONE')return false;
 const subject=String(event.subject||'').toUpperCase();
 if(subject===symbol)return true;
 if(symbol==='AAPL'&&/^(APPLE|苹果)/i.test(subject))return true;
 if(symbol==='TSM'&&/^(TSM|台积电|TAIWAN SEMICONDUCTOR)/i.test(subject))return true;
 if(symbol==='300750.SZ'&&/(?:宁德时代|CATL|300750)/i.test(subject))return true;
 return false;
}
function defaultMarketWindow(r){
 const supported=[...$('#lensSymbol').options].map(o=>o.value);
 const planned=(r.plan?.symbols||[]).find(s=>supported.includes(s))||'NONE';
 const explicit=inferMarketSymbol(r.question);
 const symbol=explicit!=='NONE'?explicit:planned;
 $('#lensSymbol').value=supported.includes(symbol)?symbol:'NONE';
 $('#lensProvider').value=symbol.includes('.')?'fuyao':'ifind';
 if(r.plan?.start)$('#lensStart').value=r.plan.start;
 if(r.plan?.end)$('#lensEnd').value=r.plan.end;
}

function mobileView(view){document.body.dataset.mobileView=view;document.querySelectorAll('[data-mobile]').forEach(b=>b.classList.toggle('active',b.dataset.mobile===view))}
function windowParams(){return {symbol:$('#lensSymbol').value,provider:$('#lensProvider').value,start:$('#lensStart').value,end:$('#lensEnd').value}}
async function loadLens(r,force=false){
 const focusSnapshot=focusRevision;
 const params=windowParams();localStorage.setItem('eventlens.window.'+r.id,JSON.stringify(params));const key=JSON.stringify([r.id,r.versions.length,r.status,params]);
 if(!force&&key===lensKey)return;lensKey=key;
 const serial=++requestSerial;$('#marketQuality').textContent='正在读取实际行情与事件披露时间…';
 try{
  const path=document.body.classList.contains('embedded')?`workspace/research/${r.id}/view?${new URLSearchParams({start:params.start,end:params.end})}`:`research/${r.id}/workbench?${new URLSearchParams(params)}`;
  const result=await api(path);
  if(serial!==requestSerial||r.id!==current||focusSnapshot!==focusRevision)return;
  // A market ticker is not a research subject. The native chat session owns
  // the focus; unsupported tickers MUST NOT mean "show all events".
  const focus=document.body.classList.contains('embedded')?(result.focus||null):activeResearchFocus;
  if(document.body.classList.contains('embedded')){
    activeResearchFocus=focus;
    const verifiedMarket=focus?.market_symbol||'NONE';
    $('#lensSymbol').value=[...$('#lensSymbol').options].some(o=>o.value===verifiedMarket)?verifiedMarket:'NONE';
    $('#lensProvider').value=verifiedMarket.includes('.')?'fuyao':'ifind';
  }
  result.events=document.body.classList.contains('embedded')
    ? result.events
    : params.symbol==='NONE'?result.events:
      result.events.filter(e=>eventMatchesSymbol(e,params.symbol));
  const visibleIds=new Set(result.events.map(e=>e.id));
  result.markers=result.markers.map(m=>({...m,event_ids:m.event_ids.filter(id=>visibleIds.has(id))})).filter(m=>m.event_ids.length).map(m=>({...m,count:m.event_ids.length}));
  lens=result;
  const remembered=localStorage.getItem('eventlens.event.'+r.id);
  if(result.related_business.some(e=>/台积电|TSMC|Taiwan Semiconductor/i.test(e.target))&&!$('#lensSymbol option[value="TSM"]')){const option=document.createElement('option');option.value='TSM';option.textContent='TSM · 台积电ADR（业务关系候选）';$('#lensSymbol').append(option)}
  selectedEvent=result.events.find(e=>e.id===(selectedEvent?.id||remembered))||result.events[0]||null;
  drawChart();renderTrack();renderNode();
 }catch(error){$('#marketQuality').textContent=error.message;$('#chartEmpty').hidden=false;$('#chartEmpty').textContent='读取失败：'+error.message}
}
function barTime(time){if(typeof time==='string')return time;if(time?.year)return `${time.year}-${String(time.month).padStart(2,'0')}-${String(time.day).padStart(2,'0')}`;return ''}
function drawChart(){
 if(lensChart)lensChart.remove();if(compareChart)compareChart.remove();lensChart=null;compareChart=null;
 const m=lens.market;$('#chartTitle').textContent=m.symbol||'未选定行情';$('#stockName').textContent=m.label||'行情核对';const last=m.bars.at(-1),first=m.bars[0];$('#marketValue').textContent=last?last.close.toFixed(2):'—';$('#windowReturn').textContent=last&&first?`${((last.close/first.close-1)*100).toFixed(2)}% · 区间变化`:'';$('#chartProvider').textContent=m.provider;
 $('#marketQuality').textContent=m.status==='available'?`${m.provider} · ${m.currency} · ${m.bars.length} 个交易日`:`行情不可用：${m.reason}`;
 $('#chartEmpty').hidden=m.status==='available';$('#chartEmpty').textContent='行情数据不可用\n'+m.reason+'。新闻证据仍可查看。';
 $('#marketMeta').innerHTML=`<dl>${Object.entries({'提供方':m.provider,'证券代码':m.provider_code||m.symbol,'时区':m.timezone,'货币':m.currency,'价格口径':m.basis,'交易会话':m.session_basis,'采集时刻':m.fetched_at,'成交量精度':m.volume_precision||'按接口原字段','缺失日期':m.missing_dates?.join('、')||'见实际覆盖区间；不回填'}).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl><a href="${esc(m.source_url)}" target="_blank" rel="noopener">查看数据服务说明 ↗</a>`;
 $('#chartPins').innerHTML='';
 if(m.status==='available'&&window.LightweightCharts){
  const LC=window.LightweightCharts;const palette=getComputedStyle(document.documentElement);const chartBG=palette.getPropertyValue('--chart-bg').trim()||'#fff';const gridColor=palette.getPropertyValue('--chart-grid').trim()||'#f1f1f3';
  lensChart=LC.createChart($('#kline'),{autoSize:true,layout:{background:{color:chartBG},textColor:'#768579',attributionLogo:true},grid:{vertLines:{color:gridColor},horzLines:{color:gridColor}},rightPriceScale:{borderVisible:false,scaleMargins:{top:.18,bottom:.18}},timeScale:{borderVisible:false,timeVisible:false,rightOffset:2},handleScroll:{horzTouchDrag:true,vertTouchDrag:false}});
  candle=lensChart.addSeries(LC.CandlestickSeries,{upColor:'#26958c',downColor:'#c76b6b',borderVisible:false,wickUpColor:'#26958c',wickDownColor:'#c76b6b'});
  candle.setData(m.bars.map(b=>({time:b.date,open:b.open,high:b.high,low:b.low,close:b.close})));
  markerPlugin=LC.createSeriesMarkers(candle,lens.markers.map(m=>({id:m.id,time:m.time,position:'aboveBar',shape:'circle',color:'#6e829e',text:m.count>1?`${m.count}项`:'披露'})));
  lensChart.subscribeClick(p=>{const id=String(p.hoveredObjectId||'');const cluster=lens.markers.find(m=>m.id===id)||lens.markers.find(m=>m.time===barTime(p.time));if(cluster)selectCluster(cluster)});
  lensChart.subscribeCrosshairMove(p=>{const b=p.seriesData.get(candle);if(b)$('#ohlcReadout').textContent=`${barTime(p.time)}  O ${b.open}  H ${b.high}  L ${b.low}  C ${b.close} · ${m.currency}`});
  lensChart.timeScale().subscribeVisibleLogicalRangeChange(updatePins);lensChart.timeScale().fitContent();
  new ResizeObserver(updatePins).observe($('#kline'));requestAnimationFrame(updatePins);
 }
 const colors=['#0071e3','#8e7cc3','#a07845'];const chartBG=getComputedStyle(document.documentElement).getPropertyValue('--chart-bg').trim()||'#fff';const gridColor=getComputedStyle(document.documentElement).getPropertyValue('--chart-grid').trim()||'#f1f1f3';
 if(lens.comparison.status==='available'){
  compareChart=LightweightCharts.createChart($('#compareChart'),{autoSize:true,layout:{background:{color:chartBG},textColor:'#78847a'},grid:{vertLines:{visible:false},horzLines:{color:gridColor}},rightPriceScale:{borderVisible:false},timeScale:{borderVisible:false},handleScroll:{horzTouchDrag:true,vertTouchDrag:false}});
  lens.comparison.series.forEach((s,i)=>compareChart.addSeries(LightweightCharts.LineSeries,{color:colors[i%3],lineWidth:2,priceFormat:{type:'percent'}}).setData(s.points));compareChart.timeScale().fitContent();
 }
 $('#compareStatus').innerHTML=lens.comparison.status==='available'?lens.comparison.series.map((s,i)=>`<span style="color:${colors[i%3]}">${esc(s.symbol)} ${esc(s.label)} · ${esc(s.points.at(-1)?.value)}%</span>`).join(''):`<p>${esc(lens.comparison.reason)}</p>`;
 $('#compareStatus').innerHTML+=lens.markets.filter(m=>m.status!=='available').map(m=>`<p>${esc(m.symbol)}：${esc(m.reason)}</p>`).join('')+'<p>同期表现是观察事实，不代表新闻造成价格变化。</p>'+`<details><summary>有业务依据的关联范围（${lens.related_business.length}条候选）</summary>${lens.related_business.length?lens.related_business.map(e=>`<p>${esc(e.subject)} → ${esc(e.relation)} → ${esc(e.target)} ${sourceButtons(e)}<span class="meta">${esc(e.temporal_status)}</span></p>`).join(''):'<p>当前没有通过原文定位的业务关系候选；不把外部律所作为产业链标的。</p>'}</details>`;
 window.eventLensChart={chart:lensChart,series:candle,get state(){return {researchId:lens.research_id,eventId:selectedEvent?.id,markers:lens.markers,barCount:lens.market.bars.length,provider:lens.market.provider}}};
}
function updatePins(){
 if(!lensChart||!lens)return;
 $('#chartPins').innerHTML=lens.markers.map(m=>{const x=lensChart.timeScale().timeToCoordinate(m.time);if(x===null)return '';return `<button class="chart-pin ${m.event_ids.includes(selectedEvent?.id)?'active':''}" style="left:${x}px" data-cluster="${esc(m.id)}" aria-label="${m.time} 新闻事件 ${m.count}项" title="${m.time} · ${m.count}个事件">${m.count}</button>`}).join('');
}
function selectCluster(cluster){const e=lens.events.find(e=>e.id===cluster.event_ids[0]);if(e)selectEvent(e.id);$('#nodeGroup').innerHTML=cluster.event_ids.map(id=>{const e=lens.events.find(e=>e.id===id);return `<button class="quiet" data-event="${id}">${esc(e.action)}</button>`}).join('')}
function selectEvent(id){selectedEvent=lens.events.find(e=>e.id===id);if(!selectedEvent)return;localStorage.setItem('eventlens.event.'+lens.research_id,id);renderTrack();renderNode();updatePins();if(innerWidth<=850)mobileView('events')}
function renderTrack(){
 const filter=$('#lensFilter').value;
 const events=lens.events.filter(e=>filter==='all'||filter==='conflict'&&e.has_conflict||filter===e.source_type)
   .slice().sort((a,b)=>{
     const ad=a.timeline_date||a.disclosed_at?.slice(0,10)||'';
     const bd=b.timeline_date||b.disclosed_at?.slice(0,10)||'';
     return Number(!ad)-Number(!bd)||ad.localeCompare(bd)
       ||(a.disclosed_at||'').localeCompare(b.disclosed_at||'')
       ||a.id.localeCompare(b.id);
   });
 const groups=[];
 for(const event of events){
   const day=event.timeline_date||event.disclosed_at?.slice(0,10)||'';
   if(groups.at(-1)?.day!==day)groups.push({day,events:[]});
   groups.at(-1).events.push(event);
 }
 $('#eventTrack').innerHTML=groups.length?groups.map(group=>
   '<section class="timeline-group"><div class="timeline-date">'+
   esc(group.day?group.day.replaceAll('-',' / '):'日期待核')+
   '<span>'+group.events.length+' 个事件</span></div><div class="timeline-stack">'+
   group.events.map(e=>'<button type="button" class="event-item '+(e.id===selectedEvent?.id?'active':'')+
     '" data-event="'+esc(e.id)+'"><span class="timeline-dot" aria-hidden="true"></span>'+
     '<span class="track-body"><strong>'+esc(e.action)+'</strong>'+
     '<span class="track-caption">'+esc(e.subject)+' · '+esc(e.timeline_basis||'披露日期')+
     ' · '+e.source_count+' 份来源'+(e.has_conflict||e.timeline_conflict?' · 存在分歧':'')+
     '</span></span><span class="track-arrow" aria-hidden="true">›</span></button>'
   ).join('')+'</div></section>').join('')
   :'<p class="empty">当前主题暂无可核对的事件；请继续在右侧检索。不会展示其他标的的旧信息。</p>';
}
function renderNode(){
 const e=selectedEvent;
 if(e&&lens)fetch('/api/harness/selection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({research_id:lens.research_id,event_id:e.id,source_ids:e.source_ids,market_window:windowParams()})}).catch(()=>{});
 if(!e){$('#nodeTitle').textContent='暂无匹配的事件证据';$('#nodeGroup').replaceChildren();$('#nodeSummary').innerHTML='<p class="node-empty">当前标的尚未取得已核验的事件证据。请继续在右侧检索，不展示其他公司的旧新闻。</p>';return}
 $('#nodeTitle').textContent=e.subject+' · '+e.action;
 const sameDay=lens.events.filter(x=>x.marker_date&&x.marker_date===e.marker_date);
 $('#nodeGroup').innerHTML=sameDay.length>1?sameDay.map(x=>`<button class="quiet ${x.id===e.id?'chosen':''}" data-event="${x.id}">${esc(x.action)}</button>`).join(''):'';
 const headings={disclosed:'披露内容',reported:'媒体陈述与观点',unverified:'尚未证实',conflicts:'需要核对的分歧'};
 const sourceName=id=>{const s=lens.sources.find(s=>s.id===id);if(!s)return '查看依据';if(s.publisher?.includes('nvidia'))return 'NVIDIA 原文';if(s.publisher?.includes('sec.gov'))return 'SEC 文件';return s.publisher||'查看来源'};
 const a=e.assessment||{};
 const assessmentHTML='<section class="evidence-assessment" aria-label="当前结论与证据权重">'+
   '<div class="assessment-eyebrow">当前结论 · v'+esc(lens.versions.length)+'</div>'+
   (e.changes?.previous_state&&e.changes.previous_state!==e.state?
     '<p class="assessment-change">状态变化：'+esc(e.changes.previous_state)+' → '+esc(e.state)+'</p>':'')+
   '<h3>'+esc(a.status_label||e.state||'待核实')+'</h3>'+
   '<p>'+esc(a.reason||'当前没有足够已核验材料')+'</p>'+
   '<div class="assessment-origin">底层来源组 '+esc(a.origin_count??e.provenance_groups??'—')+
   ' · 一手来源标记 '+esc((a.source_tiers?.official||0)+(a.source_tiers?.regulatory||0))+
   ' · 二手/待核 '+esc(a.source_tiers?.secondary??0)+'</div>'+
   (e.earliest_source_id?
     '<p class="assessment-first">本研究最早可定位的披露：'+esc(e.disclosed_at)+
     ' <button class="quiet" data-source="'+esc(e.earliest_source_id)+'">查看最早来源</button></p>':
     '<p class="assessment-first">首次披露时间待核实；不将搜索收录时间当作首发。</p>')+
   '<details><summary>证据权重怎么判断</summary><p>'+esc(a.weight_rule||'不以来源数机械投票')+
   '</p><p>'+esc(a.freshness_note||'时效按来源核实')+
   '</p>'+(a.origin_groups||[]).map(g=>'<p>'+esc(g.tier_label)+' · '+esc(g.source_ids.join(' / '))+
   ' · '+esc(g.kind_labels.join('、'))+'</p>').join('')+'</details></section>';
 $('#nodeSummary').innerHTML=`<div class="node-dateline">${esc(e.timeline_date||'时间待核')}<span>·</span>${esc(e.timeline_basis||'披露日期')}</div><p class="timeline-provenance">可定位披露：${esc(e.disclosed_at||'未知')} · ${e.source_count} 份来源；行情交易日期独立标注。</p>`+assessmentHTML+(e.date_conflicts?.length?`<p class="summary-boundary">同一报告的披露日期说法不同：${e.date_conflicts.map(esc).join(' / ')}。转载日期不等于首次披露，需核对原始公告。</p>`:'')+Object.entries(headings).filter(([key])=>e.categories[key].length).map(([key,title])=>`<section class="node-section"><h3>${title}</h3>${e.categories[key].map((c,i)=>`<div class="node-claim"><span class="claim-kind">${esc({FACT:'事实陈述',OPINION:'观点',SPECULATION:'推测',RUMOR:'传闻'}[c.kind]||'类型待核')}${c.stance==='corrects'?' · 更正候选':c.stance==='disputes'?' · 否认/异议':''}</span><button type="button" class="claim-quote-text" data-quote-category="${esc(key)}" data-quote-index="${i}" title="点击将这条信息引用到右侧对话">${esc(c.statement)}</button><div class="claim-actions"><button type="button" class="cite-evidence" data-quote-category="${esc(key)}" data-quote-index="${i}">＋ 引用</button><button data-source="${esc(c.source_id)}">${esc(sourceName(c.source_id))} ↗</button><details><summary>引文</summary><div class="quote">${esc(c.quote)}</div><span class="meta">原文位置 ${esc(c.offset)}；概括语义仍需核对。</span></details></div></div>`).join('')}</section>`).join('')+`<details class="node-audit"><summary>证据与时间</summary><p class="meta">${esc(e.state)}。AI归并摘要，请结合原文核对。${e.provenance_groups} 个底层来源分组，不等于独立证实票数。</p><p class="meta">图表对齐 ${esc(e.market_session_date||'未放置')}<br>${esc(e.alignment_reason)}</p>${e.disclosures.map(d=>{const s=lens.sources.find(x=>x.id===d.source_id);return `<details><summary>${esc(s.title)}</summary><p class="meta">发生：${esc(e.claims.filter(c=>c.source_id===s.id).map(c=>c.occurred_at||'未知').join(' / '))}<br>披露：${esc(d.disclosed_at||'未知')} · ${esc(d.precision)} · 时区 ${esc(d.timezone||'未知')}<br>日期依据：${esc(d.quote||'无可定位日期')}<br>搜索索引：${esc(d.search_published_at||'未知')}（不用于节点）<br>抓取：${esc(s.fetched_at)}<br>更新：${esc(s.updated_at)}</p><a href="${esc(s.url)}" target="_blank" rel="noopener">打开原始来源 ↗</a></details>`}).join('')}</details><details class="node-audit"><summary>版本变化</summary><p class="meta">${lens.versions.length} 个研究版本。${e.changes?.new_event?'首次纳入本事件':'此前状态：'+esc(e.changes?.previous_state)}。本版新增 ${e.changes?.added_source_ids.length||0} 份来源；仅影响信息整理，不改写你的判断。</p></details><p class="summary-boundary">公开时间与图表交易日可能不同。同期涨跌不能证明因果。</p>`;
 renderScopedMessages();$('#followup').placeholder=`继续了解“${e.action}”…`;
 fitResearchPanel();
}
// The host owns validated subject focus, and passes it by same-origin
// postMessage. Changing focus immediately invalidates old rendered evidence.
window.addEventListener('message',event=>{
 if(window===window.parent||event.origin!==location.origin||event.source!==window.parent)return;
 const data=event.data;
 if(!data||data.type!=='eventlens:focus'||data.research_id!==current)return;
 const focus=data.focus||null;
 const nextSignature=JSON.stringify([data.research_id,focus]);
 const oldSignature=JSON.stringify([current,activeResearchFocus]);
 if(nextSignature===oldSignature)return;
 activeResearchFocus=focus;
 ++focusRevision;
 const marketSymbol=focus?.market_symbol||'NONE';
 const supported=[...$('#lensSymbol').options].some(o=>o.value===marketSymbol);
 $('#lensSymbol').value=supported?marketSymbol:'NONE';
 $('#lensProvider').value=marketSymbol.includes('.')?'fuyao':'ifind';
 clearOldFocus(focus?.subject||data.text||'新研究');
 if(task)loadLens(task,true);
});
const chartPanel=document.querySelector('.chart-panel');
$('#toggleChart').onclick=()=>{
 const condensed=chartPanel.classList.toggle('is-condensed');
 $('#toggleChart').textContent=condensed?'展开行情':'收起行情';
 $('#toggleChart').setAttribute('aria-expanded',String(!condensed));
 if(!condensed)requestAnimationFrame(()=>{lensChart?.timeScale().fitContent();updatePins()});
};
if(!document.body.classList.contains('embedded')){
 chartPanel.classList.remove('is-condensed');
 $('#toggleChart').textContent='收起行情';
 $('#toggleChart').setAttribute('aria-expanded','true');
}
$('#loadChart').onclick=()=>{if(task)loadLens(task,true)};$('#fitChart').onclick=()=>lensChart?.timeScale().fitContent();$('#lensFilter').onchange=renderTrack;
$('#lensSymbol').onchange=()=>{if($('#lensSymbol').value.includes('.'))$('#lensProvider').value='fuyao';else if($('#lensProvider').value==='fuyao')$('#lensProvider').value='ifind'};
$('#toggleEvidence').onclick=()=>{document.body.classList.toggle('show-legacy');$('#toggleEvidence').textContent=document.body.classList.contains('show-legacy')?'收起来源列表与历史版本':'展开来源列表与历史版本'};
document.addEventListener('click',e=>{const node=e.target.closest('[data-event],[data-cluster],[data-mobile]');if(!node||!lens)return;if(node.dataset.event)selectEvent(node.dataset.event);if(node.dataset.cluster){const cluster=lens.markers.find(m=>m.id===node.dataset.cluster);if(cluster)selectCluster(cluster)}if(node.dataset.mobile)mobileView(node.dataset.mobile)});
// Text/quote actions in the left pane create a verified reference draft.
// They never dispatch an AI request; the user still submits in Harness.
document.addEventListener('click', e => {
 const button=e.target.closest('[data-quote-category][data-quote-index]');
 if(!button||!selectedEvent||!lens)return;
 const section=selectedEvent.categories[button.dataset.quoteCategory]||[];
 const c=section[Number(button.dataset.quoteIndex)];
 if(!c||!c.source_id||!c.quote)return;
 if(window.parent===window){notice('在 EventLens 双栏工作台中可将这条内容引用到 Harness 对话。');return}
 window.parent.postMessage({type:'eventlens:quote',reference:{
   research_id:lens.research_id,event_id:selectedEvent.id,
   source_id:c.source_id,quote:c.quote
 }},location.origin);
});
$('#askForm').onsubmit=async e=>{
 e.preventDefault();if(!current||!selectedEvent){notice('请先选中一个事件节点。');return}
 $('#askButton').disabled=true;
 try{
  const payload={question:$('#followup').value,refresh:$('#askRefresh').checked,event_id:selectedEvent.id,source_ids:selectedEvent.source_ids,market_window:windowParams()};
  await api(`research/${current}/ask`,payload);$('#followup').value='';await poll();if(innerWidth<=850)mobileView('chat');
 }catch(error){notice(error.message)}finally{$('#askButton').disabled=false}
};
const rememberedResearch=location.hash.slice(1)||(!document.body.classList.contains('embedded')?localStorage.getItem('eventlens.lastResearch'):'');
if(/^[a-f0-9]{32}$/.test(rememberedResearch))openTask(rememberedResearch);
// Setting iframe.src to the same page with a different hash is a same-document
// navigation: scripts do not run again. Explicitly load/clear the bound study.
window.addEventListener('hashchange',()=>{
 const id=location.hash.slice(1);
 if(id===current)return;
 if(noteDirty&&current)localStorage.setItem('eventlens.noteDraft.'+current,$('#note').value);
 noteDirty=false;
 if(/^[a-f0-9]{32}$/.test(id)){openTask(id);return}
 if(document.body.classList.contains('embedded')){
  clearTimeout(timer);current=null;task=null;lensControlsResearch=null;
  clearOldFocus('新研究');$('#workspace').hidden=true;
 }
});
const renderWithEvidence=render;
render=function(r){
 const entering=current===r.id&&lensControlsResearch!==r.id;
 renderWithEvidence(r);
 if(entering){
  const draft=localStorage.getItem('eventlens.noteDraft.'+r.id);
  if(draft!==null){$('#note').value=draft;noteDirty=true;$('#noteState').textContent='已恢复本机未保存的判断草稿'}
 }
};
const saveJudgment=$('#saveNote').onclick;
$('#saveNote').onclick=async()=>{const id=current;await saveJudgment();if(!noteDirty&&current===id)localStorage.removeItem('eventlens.noteDraft.'+id)};

function renderScopedMessages(){
 if(!task||!selectedEvent)return;
 const messages=task.messages.filter(m=>m.context?.event_id===selectedEvent.id);
 $('#messages').innerHTML=messages.length?messages.map(m=>`<div class="message"><div class="meta">当前事件 · 版本 ${esc(m.version)} · ${esc(m.context?.market_window?.symbol||'')}</div><h3>${esc(m.question)}</h3>${m.answers.map(a=>`<p>${esc(a.text)}</p>${[...new Map(a.refs.map(ref=>[ref.source_id,ref])).values()].map(sourceButtons).join('')+(a.refs.length?`<details><summary>${a.refs.length} 处原文引文</summary>${a.refs.map(ref=>`<p class="quote">${esc(ref.quote)}<br><span class="meta">${esc(ref.source_id)} · 原文位置 ${esc(ref.offset)}</span></p>`).join('')}</details>`:'')}${(a.market_refs||[]).map(ref=>`<p class="meta">行情依据 ${esc(ref.symbol)} / ${esc(ref.date)} / ${esc(ref.field)} = ${esc(ref.value)} · ${esc(ref.provider)} · ${esc(ref.basis)}</p>`).join('')}`).join('')}${m.unknowns.map(u=>`<p class="quote">当前资料无法证实：${esc(u)}</p>`).join('')}${(m.validation_warnings||[]).map(w=>`<p class="meta">已拒绝第 ${esc(w.index)} 条回答：${esc(w.reason)}</p>`).join('')}</div>`).join(''):'<p class="meta">基于当前选中事件及行情窗口回答。引用不足时会明确说明。</p>';
 $('#messages').scrollTop=$('#messages').scrollHeight;
}
function fitResearchPanel(){
 const panel=$('.lens-right'),grid=$('.lens-grid');
 if(innerWidth>850&&grid){panel.style.height=Math.max(460,innerHeight-Math.max(12,grid.getBoundingClientRect().top)-12)+'px'}else panel.style.height='';
}
window.addEventListener('resize',()=>requestAnimationFrame(fitResearchPanel));
window.addEventListener('scroll',()=>requestAnimationFrame(fitResearchPanel),{passive:true});
new ResizeObserver(fitResearchPanel).observe($('#workspace'));

function topicLabel(question){if(/nvidia|英伟达|黄仁勋/i.test(question))return 'NVIDIA · 事件研究';return question.slice(0,30)}
recent=async function(){
 const rows=await api('research');const visible=rows.filter(r=>['complete','partial','running','queued'].includes(r.status)).slice(0,8);
 $('#recent').innerHTML=visible.map(r=>`<button class="recent ${r.id===current?'selected':''}" data-task="${r.id}"><span>${esc(topicLabel(r.question))}</span><span class="recent-state">${['running','queued'].includes(r.status)?'正在研究':'研究就绪'}</span></button>`).join('');
};
recent();
// Harness can append evidence while the original API task is already idle.
let revisionBusy=false;
setInterval(async()=>{if(!task||!current||revisionBusy||loading)return;revisionBusy=true;try{const r=await api(`research/${current}/revision`);if(r.version!==task.versions.length)await poll()}catch{}finally{revisionBusy=false}},3000);
