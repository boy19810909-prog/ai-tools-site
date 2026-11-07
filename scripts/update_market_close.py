#!/usr/bin/env python3
"""Fetch TWSE's latest dated end-of-day index record. Never label it intraday."""
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parents[1] / 'data' / 'market.json'
SOURCE = 'https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK'
TZ_TW = dt.timezone(dt.timedelta(hours=8))


def parse_date(raw):
    raw = str(raw).strip()
    if len(raw) != 7 or not raw.isdigit():
        raise ValueError('invalid ROC date')
    return dt.date(int(raw[:3]) + 1911, int(raw[3:5]), int(raw[5:7]))


def nfloat(x):
    return float(str(x).replace(',', '').replace('+', '').strip())


def fetch(now):
    req = Request(SOURCE, headers={'User-Agent': 'FamilyFinanceEducation/1.0', 'Accept': 'application/json'})
    with urlopen(req, timeout=18) as resp:
        url = urlparse(resp.geturl())
        if url.scheme != 'https' or url.hostname != 'openapi.twse.com.tw':
            raise ValueError('unexpected data origin')
        content = resp.read(1_000_001)
    if len(content) > 1_000_000:
        raise ValueError('oversize response')
    data = json.loads(content)
    if not isinstance(data, list):
        raise ValueError('unexpected JSON root')
    rows = []
    today = now.astimezone(TZ_TW).date()
    for row in data:
        try:
            date = parse_date(row['Date'])
            value = nfloat(row['TAIEX'])
            delta = nfloat(row['Change'])
            trade_value = int(nfloat(row['TradeValue']))
            if not 0 <= (today - date).days <= 14:
                continue
            if not (1000 < value < 100000 and abs(delta) < value * .2 and trade_value > 0):
                continue
            rows.append({'date': date.isoformat(), 'taiex': round(value,2), 'change': round(delta,2), 'trade_value': trade_value})
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    if not rows:
        raise ValueError('no recent valid trade date')
    return max(rows,key=lambda x:x['date'])


def main():
    now = dt.datetime.now(dt.timezone.utc)
    try:
        old = json.loads(OUT.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        old = {}
    state = {'attempted_at': now.isoformat(timespec='seconds'), 'source': SOURCE}
    try:
        record = fetch(now)
        state.update(record)
        state['updated_at'] = now.isoformat(timespec='seconds')
        state['error'] = None
        print('TWSE trading date:',record['date'],'index:',record['taiex'])
    except Exception as err:
        state.update({k:old.get(k) for k in ('date','taiex','change','trade_value','updated_at')})
        state['error'] = str(err)[:140]
        print('TWSE refresh failed:',state['error'])
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')

if __name__=='__main__':main()
