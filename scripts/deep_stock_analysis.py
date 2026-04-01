#!/usr/bin/env python3
"""自选股深度分析报告生成器"""
import urllib.request, json, time, math, sqlite3

API = "http://localhost:8000"
DB  = "/Users/dc/clawd/stock-analysis-system/stock_data.db"

def fetch(url):
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read())

def ksym(s):
    if s.startswith('hk'): return s
    return s if len(s)==6 and s.isdigit() else f"hk{s}"

NAMES = {
    '600519':'贵州茅台','000034':'神州数码','00700':'腾讯控股',
    '09988':'阿里巴巴','000063':'中兴通讯','002050':'三花智控',
    '01810':'小米集团','515980':'AIETF','513010':'恒生科技ETF','02590':'信达生物',
}

wl = fetch(f"{API}/api/watchlist")
symbols = [s['symbol'] for s in (wl.get('data') or [])]

# ── 拉数据 ──
data = {}
for sym in symbols:
    rt = {}
    try: rt = fetch(f"{API}/api/stocks/{sym}").get('data') or {}
    except: pass
    ks = ksym(sym)
    klines = []
    for limit in [120, 60, 30]:
        d = fetch(f"{API}/api/kline/{ks}?limit={limit}")
        if d.get('data'):
            klines = d['data']; break
        time.sleep(0.3)
    data[sym] = {'rt': rt, 'klines': klines}
    time.sleep(0.3)

# ── 工具函数 ──
def ma(closes, n):
    return sum(closes[-n:])/n if len(closes)>=n else None

def ema(closes, n):
    if len(closes) < n: return None
    k = 2/(n+1)
    e = sum(closes[:n])/n
    for c in closes[n:]: e = c*k + e*(1-k)
    return e

def macd(closes):
    if len(closes) < 35: return None, None, None
    def e(n): return ema(closes, n)
    dif = e(12) - e(26)
    # signal line EMA of DIF (9 period)
    dif_series = []
    for i in range(26, len(closes)):
        dif_series.append(ema(closes[:i+1], 12) - ema(closes[:i+1], 26))
    if len(dif_series) < 9: return dif, None, None
    sig_k = 2/(9+1)
    sig = sum(dif_series[:9])/9
    for v in dif_series[9:]: sig = v*sig_k + sig*(1-sig_k)
    bar = dif_series[-1] - sig
    return dif, sig, bar

def rsi(closes, n=14):
    if len(closes) < n+1: return None
    gains, losses = 0, 0
    for i in range(-n, 0):
        d = closes[i] - closes[i-1]
        gains += d if d>0 else 0
        losses += -d if d<0 else 0
    ag = gains/n; al = losses/n
    if al == 0: return 100
    return 100 - 100/(1 + ag/al)

def boll(closes, n=20, k=2):
    if len(closes) < n: return None, None, None
    m = sum(closes[-n:])/n
    std = math.sqrt(sum((c-m)**2 for c in closes[-n:])/n)
    return m+k*std, m, m-k*std

def vol_analysis(vols, closes):
    if len(vols) < 6: return None, None, "正常"
    avg5 = sum(vols[-5:])/5
    avg20 = sum(vols[-20:])/20 if len(vols)>=20 else None
    vr = vols[-1]/avg5 if avg5 else None
    pct_chg = (closes[-1]-closes[-5])/closes[-5]*100 if len(closes)>=5 else 0
    vol_tr = (vols[-1]-avg5)/avg5*100
    if pct_chg>3 and vol_tr<-30: vp = "价涨量缩⚠️"
    elif pct_chg<-3 and vol_tr>50: vp = "恐慌放量📉"
    elif vol_tr>80: vp = "明显放量📊"
    elif vol_tr<-40: vp = "明显缩量📉"
    else: vp = "正常"
    return vr, avg20, vp

def f2(v, d=2):
    if v is None: return "--"
    return f"{v:.{d}f}"

def f0(v):
    if v is None: return "--"
    return f"{v:.0f}"

def fpct(v):
    if v is None: return "--"
    return f"{v:+.1f}%"

# ── 报告生成 ──
conn = sqlite3.connect(DB)
cursor = conn.cursor()

lines = []
lines.append(f"# 📊 自选股深度分析报告")
lines.append(f"**{time.strftime('%Y-%m-%d %H:%M')}**  |  数据：本地DB + 腾讯财经")
lines.append("")
lines.append("---")
lines.append("")

# ── Section 1: 数据总览 ──
lines.append("## 一、数据总览")
lines.append("")
lines.append("| 代码 | 名称 | 现价 | 昨收 | 日涨跌 | 5日涨跌 | 20日涨跌 | 量比 |")
lines.append("| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |")

for sym in symbols:
    rt = data[sym]['rt']
    klines = data[sym]['klines']
    closes = [k['close'] for k in klines]
    vols = [k['volume'] for k in klines]
    price = rt.get('price') or rt.get('last_close') or (closes[-1] if closes else 0)
    prev = rt.get('prev_close') or (closes[-2] if len(closes)>=2 else price)
    d_chg = (price-prev)/prev*100 if prev else 0
    d5    = (price-closes[-6])/closes[-6]*100 if len(closes)>=6 else 0
    d20   = (price-closes[-21])/closes[-21]*100 if len(closes)>=21 else 0
    vr,_,_ = vol_analysis(vols, closes)
    name = NAMES.get(sym, rt.get('name', sym))
    em = "🔴" if d_chg>0 else "🟢"
    lines.append(f"| {sym} | {name} | {f2(price)} | {f2(prev)} | {em}{d_chg:+.2f}% | {fpct(d5)} | {fpct(d20)} | {f2(vr)} |")

lines.append("")

# ── Section 2: 技术分析 ──
lines.append("## 二、技术分析")
lines.append("")
lines.append("### 2.1 均线与趋势")
lines.append("")
lines.append("| 代码 | MA5 | MA10 | MA20 | MA60 | 趋势判断 |")
lines.append("| ---: | ---: | ---: | ---: | ---: | --- |")

for sym in symbols:
    closes = [k['close'] for k in data[sym]['klines']]
    price = closes[-1] if closes else 0
    m5  = ma(closes, 5);   m10 = ma(closes, 10)
    m20 = ma(closes, 20); m60 = ma(closes, 60)
    if price and m20 and m5 and m10 and price>m20 and m5>m10 and m10>m20: trend = "🔴 上升趋势"
    elif price and m20 and m5 and m10 and price<m20 and m5<m10 and m10<m20: trend = "🟢 下降趋势"
    elif price and m20 and price>m20: trend = "➡️ 反弹"
    else: trend = "⚠️ 调整"
    lines.append(f"| {sym} | {f2(m5)} | {f2(m10)} | {f2(m20)} | {f2(m60)} | {trend} |")

lines.append("")
lines.append("### 2.2 MACD / RSI / 布林带")
lines.append("")
lines.append("| 代码 | DIF | DEA | MACD柱 | RSI | BOLL上 | BOLL中 | BOLL下 | 位置 |")
lines.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")

for sym in symbols:
    closes = [k['close'] for k in data[sym]['klines']]
    price = closes[-1] if closes else 0
    if len(closes) >= 35:
        dif, dea, bar = macd(closes)
        ri = rsi(closes)
        upper, mid, lower = boll(closes)
    else:
        dif=dea=bar=ri=upper=mid=lower=None
    if upper and mid and lower:
        if price > upper: pos = "突破上轨⚠️"
        elif price < lower: pos = "跌破下轨📉"
        elif price > mid: pos = "中上↗"
        else: pos = "中下↘"
    else: pos = "--"
    lines.append(f"| {sym} | {f2(dif)} | {f2(dea)} | {f2(bar)} | {f0(ri)} | {f2(upper)} | {f2(mid)} | {f2(lower)} | {pos} |")

lines.append("")
lines.append("### 2.3 量价分析")
lines.append("")
lines.append("| 代码 | 今日成交量 | 5日均量 | 20日均量 | 量比 | 量价关系 |")
lines.append("| ---: | ---: | ---: | ---: | ---: | --- |")

for sym in symbols:
    klines = data[sym]['klines']
    vols = [k['volume'] for k in klines]
    closes = [k['close'] for k in klines]
    vr, avg20, vp = vol_analysis(vols, closes)
    lines.append(f"| {sym} | {f0(vols[-1])} | {f0(sum(vols[-5:])/5 if len(vols)>=5 else sum(vols)/len(vols))} | {f0(avg20)} | {f2(vr)} | {vp} |")

lines.append("")

# ── Section 3: 基本面 ──
lines.append("## 三、基本面")
lines.append("")
lines.append("| 代码 | PE | PB | ROE% | 股息率% | 毛利率% | 净利增长% | 营收增长% | 估值 |")
lines.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")

for sym in symbols:
    rt = data[sym]['rt']
    name = NAMES.get(sym, rt.get('name', sym))
    pe = rt.get('pe') or 0; pb = rt.get('pb') or 0; roe_v = rt.get('roe') or 0
    cursor.execute("SELECT pe,pb,roe,gross_margin,revenue_growth,profit_growth FROM stocks WHERE symbol=? LIMIT 1", (sym,))
    sr = cursor.fetchone()
    pe_v = sr[0] if sr else pe; pb_v = sr[1] if sr else pb
    roe_v2 = sr[2] if sr else roe_v; gm = sr[3] if sr else None
    rev_g = fpct(sr[4] if sr else None); prof_g = fpct(sr[5] if sr else None)
    if pe_v > 0:
        if pe_v < 15: val = "低估📈"
        elif pe_v > 50: val = "极高估⚠️"
        else: val = "合理"
    else: val = "亏损/负"
    lines.append(f"| {sym} | {f2(pe_v)} | {f2(pb_v)} | {f2(roe_v2)} | -- | {f2(gm)} | {prof_g} | {rev_g} | {val} |")

conn.close()
lines.append("")

# ── Section 4: 因子暴露 ──
lines.append("## 四、因子暴露与综合信号")
lines.append("")
lines.append("| 代码 | 20d动量 | 价值 | 质量 | 波动性 | 相对MA20 | 综合信号 |")
lines.append("| ---: | ---: | ---: | ---: | ---: | ---: | --- |")

for sym in symbols:
    rt = data[sym]['rt']
    closes = [k['close'] for k in data[sym]['klines']]
    price = closes[-1] if closes else 0
    m20 = ma(closes, 20)
    mom20 = (price-closes[-21])/closes[-21]*100 if len(closes)>=21 else 0 if closes else 0
    pe = rt.get('pe') or 0; pb = rt.get('pb') or 0; roe_v = rt.get('roe') or 0
    val = "✅低估" if 0<pe<20 or 0<pb<3 else "⚠️高估" if pe>50 or pb>10 else "➡️合理"
    qual = "✅优质" if roe_v>15 else "➡️一般" if roe_v>5 else "❌低质"
    if len(closes)>=20:
        rets=[(closes[i]-closes[i-1])/closes[i-1] for i in range(1,min(20,len(closes)))]
        std=math.sqrt(sum(r**2 for r in rets)/len(rets)) if rets else 0
        avg_r=sum(rets)/len(rets) if rets else 0.001
        cv=std/abs(avg_r)
        vol_s="低波动✅" if cv<1.5 else "高波动⚠️"
    else: vol_s="--"
    rs = (price/m20-1)*100 if m20 else 0
    rs_s="强✅" if rs>5 else "弱⚠️" if rs<-5 else "中性"
    n_pos=sum([1 if mom20>0 else 0, 1 if 0<pe<40 else 0, 1 if roe_v>10 else 0, 1 if rs>0 else 0])
    final="🟢偏多" if n_pos>=3 else "🔴偏空" if n_pos<=1 else "⚪中性"
    lines.append(f"| {sym} | {fpct(mom20)} | {val} | {qual} | {vol_s} | {fpct(rs)} | {final} |")

lines.append("")
lines.append("---")
lines.append("**因子说明**：")
lines.append("- 动量：近20日价格变化，正向=上涨趋势")
lines.append("- 价值：PE&lt;20或PB&lt;3为低估，PE&gt;50为极高估")
lines.append("- 质量：ROE&gt;15%为优质，&lt;5%为低质")
lines.append("- 波动性：标准差/均值，比值低=稳健")
lines.append("- 相对MA20：&gt;5%=强于均线，&lt;-5%=弱于均线")
lines.append(f"\n*生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}*")

report = '\n'.join(lines)
print(report)
with open('/tmp/deep_analysis_report.md', 'w') as f:
    f.write(report)
