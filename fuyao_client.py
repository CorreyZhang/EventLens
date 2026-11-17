"""Optional, server-side Fuyao connector. Keys are read from environment only.

A-share example ONLY: do not use a domestic stock feed as an NVDA news source.
Never log keys, request headers, or full licensed upstream data.
"""
from __future__ import annotations
import argparse
import json
import os
import re
from urllib import error, parse, request

BASE_URL = "https://fuyao.aicubes.cn"
ASTOCK_RE = re.compile(r"^[0-9]{6}\.(?:SH|SZ|BJ)$")


class FuyaoError(RuntimeError):
    """User-facing sanitized integration error."""


def stock_timeline(thscode: str = "300033.SZ", *, timeout: float = 8.0) -> dict:
    """Read a page of A-share time-line news through the documented REST endpoint.

    Returns a small subset of metadata; the API's `jump_url` is only a source
    pointer, not proof that source content has been independently verified.
    """
    if not ASTOCK_RE.fullmatch(thscode):
        raise FuyaoError("该接口仅支持 6 位 A 股代码及 .SH/.SZ/.BJ 后缀；不能用 NVDA 查询")
    api_key = os.environ.get("FUYAO_API_KEY", "").strip()
    if not api_key:
        raise FuyaoError("FUYAO_API_KEY 未配置；请使用轮换后的密钥，且勿发送到聊天或提交到 Git")

    url = BASE_URL + "/api/news/stock/timeline-list?" + parse.urlencode({
        "thscode": thscode, "offset": "first", "size": 5,
    })
    req = request.Request(url, headers={"X-api-key": api_key, "Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(200_000)
    except error.HTTPError as exc:
        raise FuyaoError(f"扶摇 HTTP {exc.code}；请检查权限或限流") from None
    except (error.URLError, TimeoutError, OSError):
        raise FuyaoError("扶摇网络连接失败或请求超时") from None

    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise FuyaoError("扶摇响应不是合法 JSON") from None
    if not isinstance(payload, dict):
        raise FuyaoError("扶摇响应格式不符合官方信封")
    code = payload.get("code")
    if code != 0:
        if code == 2001:
            msg = "API Key 无效或已被撤销"
        elif code == 2003:
            msg = "当前账号无权访问个股新闻接口"
        elif code == 4001:
            msg = "访问频率超过限制"
        else:
            msg = "业务请求未成功（请核对授权和接口状态）"
        raise FuyaoError(f"扶摇接口返回业务错误 {code}：{msg}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise FuyaoError("扶摇响应缺少 data 对象")
    items = data.get("items", [])
    if not isinstance(items, list):
        raise FuyaoError("扶摇响应 items 格式错误")
    preview = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        preview.append({
            "id": str(item.get("id", "")),
            "title": str(item.get("title", ""))[:200],
            "source": str(item.get("source", ""))[:100],
            "publish_time_ms": item.get("publish_time_ms"),
            "has_source_link": bool(item.get("jump_url")),
        })
    return {
        "ok": True,
        "provider": "Fuyao",
        "capability": "stock_timeline_list",
        "thscode": thscode,
        "item_count": len(items),
        "preview": preview,
        "note": "仅证明该 A 股资讯接口可查询，不等于美股 NVDA 数据已授权或事件原文已核实",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify Fuyao A-share news capability with a rotated runtime key")
    parser.add_argument("--thscode", default="300033.SZ")
    args = parser.parse_args()
    try:
        print(json.dumps(stock_timeline(args.thscode), ensure_ascii=False))
    except FuyaoError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)


def historical(thscode, start, end, index=False, timeout=12):
    """Official A-share daily OHLC; never accepts overseas ticker aliases."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    if not ASTOCK_RE.fullmatch(thscode):
        raise FuyaoError('扶摇公开A股历史行情不支持NVDA等美股代码')
    api_key=os.getenv('FUYAO_API_KEY','').strip()
    if not api_key:
        import finance_runtime
        if not finance_runtime.available():raise FuyaoError('FUYAO_API_KEY 未配置，且本地进程内凭据服务不可用')
    begin=datetime.fromisoformat(start).replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    finish=datetime.fromisoformat(end).replace(tzinfo=ZoneInfo('Asia/Shanghai'))+timedelta(days=1)-timedelta(milliseconds=1)
    params={'thscode':thscode,'interval':'1d','start':int(begin.timestamp()*1000),'end':int(finish.timestamp()*1000)}
    if not index:params['adjust']='none'
    path='/api/a-share-index/prices/historical' if index else '/api/a-share/prices/historical'
    req=request.Request(BASE_URL+path+'?'+parse.urlencode(params),headers={'X-api-key':api_key,'Accept':'application/json'})
    try:
        if api_key:
            with request.urlopen(req,timeout=timeout) as resp:payload=json.loads(resp.read(2000000))
        else:
            import finance_runtime
            payload=finance_runtime.call({'op':'fuyao','path':path,'params':params})
    except error.HTTPError as exc:raise FuyaoError('扶摇 HTTP '+str(exc.code)) from None
    except (error.URLError,ValueError,OSError):raise FuyaoError('扶摇网络或JSON失败') from None
    if not isinstance(payload,dict) or payload.get('code')!=0:
        raise FuyaoError('扶摇业务失败 code='+str(payload.get('code') if isinstance(payload,dict) else 'invalid'))
    data=payload.get('data')
    if not isinstance(data,dict) or not isinstance(data.get('item'),list):raise FuyaoError('扶摇响应缺少data.item')
    return {'request_id':payload.get('request_id'),'path':path,'upstream_timestamp':data.get('timestamp'),'bars':[{'date':datetime.fromtimestamp(b['date_ms']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat(),**{k:b[k+'_price'] for k in ('open','high','low','close')},'volume':b.get('volume'),'turnover':b.get('turnover')} for b in data['item']]}
