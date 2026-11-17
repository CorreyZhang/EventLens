import providers

def test_market_common_window_and_provenance(monkeypatch):
    monkeypatch.setenv('ALPHAVANTAGE_API_KEY','TEST_ONLY')
    class Response:
        status_code=200
        def __init__(self,symbol):self.symbol=symbol
        def json(self):return {'Meta Data':{'5. Time Zone':'US/Eastern'},'Time Series (Daily)':{d:{'4. close':p} for d,p in ([('2026-11-10','100'),('2026-11-11','110'),('2026-11-12','120')] if self.symbol=='NVDA' else [('2026-11-11','200'),('2026-11-12','210')])}}
    monkeypatch.setattr(providers.httpx,'get',lambda url,params,timeout:Response(params['symbol']))
    a,b=providers.market(['NVDA','SOXX'],'2026-11-10','2026-11-12')
    assert [p['date'] for p in a['points']]==[p['date'] for p in b['points']]
    assert a['points'][0]['change_pct']==0 and b['points'][-1]['change_pct']==5
    assert a['timezone']=='US/Eastern' and a['basis']=='未复权日收盘价'

def test_market_invalid_prices_rejected(monkeypatch):
    monkeypatch.setenv('ALPHAVANTAGE_API_KEY','TEST_ONLY')
    class R:
        status_code=200
        def json(self):return {'Time Series (Daily)':{'2026-11-10':{'4. close':'NaN'}}}
    monkeypatch.setattr(providers.httpx,'get',lambda *a,**k:R())
    row=providers.market(['NVDA'],'2026-11-10','2026-11-12')[0]
    assert row['status']=='unavailable' and not row['points']
