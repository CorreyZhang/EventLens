"""v0.3 event identities, claim-level provenance, chronological node groups."""
import hashlib
import re
from datetime import date
from disclosure import normalized_source,timeline_sort,session_mapping
from event_assessment import assess, partition_sources

ACTION_RULES=[
 ('ceo_departure','CEO离任',r'管理层变动|接受辞任|辞任|辞职|离任|resign|stepped down'),
 ('interim_ceo','临时CEO任命',r'临时.*任命|任命临时|interim'),
 ('board_chair','董事会主席任命',r'董事会主席|chair'),
 ('ceo_search','CEO遴选',r'遴选|继任人选|候选人|ceo search'),
 ('return_discussion','回归讨论',r'回归|复任|复职|游说|return'),
 ('investigation_update','调查进展',r'外部律师|律所|聘请|retai[nr]'),
 ('investigation','董事会调查',r'调查|配合调查|investigat'),
 ('statement','公开声明',r'致歉|道歉|公开声明')]

def entity(subject):
    if re.search(r'nvidia|nvda|英伟达|黄仁勋|jensen|jen-hsun|克雷斯|colette|kress',subject,re.I):return 'NVDA'
    if re.search(r'\bAAPL\b|\bApple(?: Inc\.?| Corporation)?\b|苹果(?:公司|集团|股份)?',subject,re.I):return 'AAPL'
    if re.search(r'同花顺|300033',subject,re.I):return '300033.SZ'
    if re.search(r'宁德时代|300750(?:\.SZ)?|\bCATL\b',subject,re.I):return '300750.SZ'
    return re.sub(r'\s+','',subject).lower()

def action_kind(action):
    for key,label,pattern in ACTION_RULES:
        if re.search(pattern,action,re.I):return key,label
    return re.sub(r'\s+','',action).lower(),action

def build_events(claims,sources,as_of,schedule=None,bar_dates=None):
    docs={s['id']:normalized_source(s) for s in sources};groups={};eligible=[]
    for original in claims:
        c=dict(original);s=docs.get(c['source_id'])
        if not s or s['is_navigation']:continue
        if s['disclosed_at'] and s['disclosed_at'][:10]>as_of:continue
        ek=c.get('research_entity_key') or entity(c['subject']);ak,label=action_kind(c['action'])
        # Metrics in one identified quarterly report are facets of that report,
        # not separate news events. Require an explicit year/quarter in text.
        period=re.search(r'(20\d{2})\s*年\s*第?\s*([一二三四1234])\s*季度报告',s.get('content','')[:1200])
        report_anchor=None
        if period and re.search(r'季报|财报|净利润|营业收入|合同负债|研发费用|销售费用|股东户数',c['action']):
            quarter='一二三四'.find(period[2])+1 if period[2] in '一二三四' else int(period[2])
            report_anchor=period[1]+'Q'+str(quarter);ak='financial_report';label=period[1]+'年第'+str(quarter)+'季度业绩披露'
        occurred=c.get('occurred_at')
        if occurred:
            try:date.fromisoformat(occurred)
            except ValueError:occurred=None
        anchor=report_anchor or occurred or (s.get('disclosed_at') or '')[:10] or 'unknown'
        c.update(entity_key=ek,event_type=ak,anchor=anchor,label=label)
        eligible.append(c)
    # Unknown occurrence may join one unambiguous nearby occurrence only. This
    # cannot merge different dates when both sources explicitly state dates.
    for c in eligible:
        s=docs[c['source_id']]
        if not c.get('occurred_at') and c['event_type']!='financial_report':
            candidates={x['anchor'] for x in eligible if x['entity_key']==c['entity_key'] and x['event_type']==c['event_type'] and x.get('occurred_at') and c['anchor']!='unknown' and abs((date.fromisoformat(x['anchor'])-date.fromisoformat(c['anchor'])).days)<=2}
            if len(candidates)==1:c['anchor']=next(iter(candidates));c['merge_basis']='同实体/动作，唯一相邻发生日；归并可复核'
        key='|'.join((c['entity_key'],c['event_type'],c['anchor']))
        if c.get('research_scope_id'):key+='|'+c['research_scope_id']
        if c['anchor']=='unknown':key+='|'+s['source_identity']
        event=groups.setdefault(key,{'id':'E'+hashlib.sha256(key.encode()).hexdigest()[:14],'key':key,'subject':c['entity_key'],'action':c['label'],'event_type':c['event_type'],'claims':[],'source_ids':[],'disclosures':[]})
        # Avoid multiple equivalent extractions from the same version.
        if not any(x['id']==c['id'] for x in event['claims']):event['claims'].append(c)
        if s['id'] not in event['source_ids']:
            event['source_ids'].append(s['id']);event['disclosures'].append({'source_id':s['id'],'disclosed_at':s['disclosed_at'],'precision':s['disclosure_precision'],'timezone':s['disclosure_timezone'],'basis':s['disclosure_basis'],'quote':s['disclosure_quote'],'search_published_at':s['search_published_at']})
    result=[]
    for e in groups.values():
        e['claims'].sort(key=lambda c:(docs[c['source_id']].get('disclosed_at') is None,docs[c['source_id']].get('disclosed_at') or '',c['id']))
        dated=[d for d in e['disclosures'] if d['disclosed_at']]
        d=min(dated,key=lambda d:d['disclosed_at']) if dated else None
        e['disclosed_at']=d['disclosed_at'] if d else None;e['disclosure_precision']=d['precision'] if d else 'unknown'
        e['earliest_source_id']=d['source_id'] if d else None
        e['earliest_source_note']='本研究材料中最早可核对的披露，非全网首发证明' if d else '缺少可确定的首发披露日期'
        e['source_count']=len(e['source_ids']);e['provenance_groups']=provenance_count([docs[x] for x in e['source_ids']])
        e['categories']={'disclosed':[],'reported':[],'unverified':[],'conflicts':[]}
        for c in e['claims']:
            s=docs[c['source_id']]
            primary=s['kind'] in ('official','regulatory') and not s['is_navigation']
            c['evidence_status']='官源引文已定位；概括语义待审' if primary else '来源引文已定位；未独立证实'
            c['source_identity']=s['source_identity'];c['semantic_status']='not_verified'
            bucket='conflicts' if c['stance'] in ('corrects','disputes') else 'unverified' if c['kind'] in ('RUMOR','SPECULATION') else 'disclosed' if primary and c['kind']=='FACT' else 'reported'
            e['categories'][bucket].append(c)
        e['date_conflicts']=sorted({c['occurred_at'] for c in e['claims'] if c.get('occurred_at')}) if e['event_type']=='financial_report' else []
        if len(e['date_conflicts'])<2:e['date_conflicts']=[]
        conflict=bool(e['categories']['conflicts'] or e['date_conflicts'])
        e['state']='存在否认/更正候选；对象与语义待复核' if conflict else '存在官源引文；概括语义待审' if e['categories']['disclosed'] else '来源说法；待独立核实'
        if e['date_conflicts']:e['state']='同一报告的披露发生日期说法不一；需核对原始公告，转载日期不等于首次披露'
        e['has_conflict']=conflict;e['earliest_source_note']='目前集合中最早的可定位披露日期；不证明全网首发'
        mapped=session_mapping(e['disclosed_at'],e['disclosure_precision'],schedule or [])
        e['market_session_date']=mapped['date'];e['alignment_reason']=mapped['reason']
        e['marker_date']=mapped['date'] if mapped['date'] in (bar_dates or set()) else None
        if mapped['date'] and not e['marker_date']:e['alignment_reason']+='；目标交易日没有已取得K线，不跨缺失日回填'
        e['source_type']='official' if e['categories']['disclosed'] else 'media'
        e['updated_at']=max((docs[x].get('updated_at') or '' for x in e['source_ids']),default=None)
        # The timeline follows the actual occurrence day when it is
        # uniquely supported. Otherwise use the disclosure date explicitly
        # LABELLED as disclosure, never as a fabricated occurrence.
        occurred_days=sorted({c.get('occurred_at') for c in e['claims']
                              if c.get('occurred_at')})
        if len(occurred_days)==1:
            e['timeline_date']=occurred_days[0]
            e['timeline_basis']='发生时间'
            e['timeline_conflict']=False
        else:
            e['timeline_date']=e['disclosed_at'][:10] if e['disclosed_at'] else None
            e['timeline_basis']='披露时间（发生日存在分歧）' if len(occurred_days)>1 else (
                '披露时间（发生日待核）' if e['timeline_date'] else '时间待核')
            e['timeline_conflict']=len(occurred_days)>1
        e['timeline_occurred_dates']=occurred_days
        # Preserve the actual source timestamp independently of the timeline
        # day and independently of the market-session marker.
        e['timeline_disclosed_at']=e['disclosed_at']
        e['assessment']=assess(e,docs.values(),as_of)
        e['state']=e['assessment']['status_label']
        e['status_code']=e['assessment']['status_code']
        result.append(e)
    return sorted(result,key=lambda e:(e['timeline_date'] is None,
                                       e['timeline_date'] or '',
                                       e['timeline_disclosed_at'] or '',e['id']))

def safe_source(s):
    s=normalized_source(s);return {k:v for k,v in s.items() if k!='content'}


def provenance_count(sources):
    # Use the same connected-origin rule as the evidence assessment.
    # Two missing underlying_source values must NOT count as a match.
    return len(partition_sources(sources))
