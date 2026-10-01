"""Build dashboard.html: one self-contained page (no internet, no hosting).

Usage (from the code/ folder):  python -m polysweeper.dashboard
Options: --shadow-dir data/shadow  --summary data/backtest_summary.json
         --config config.json  --out dashboard.html
Shows: live shadow-mode results (real prices, pretend orders) and the
historical backtest summary, plus the risk rules and honest caveats.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def read_jsonl(path: Path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def build_shadow(shadow_dir: Path):
    trades = read_jsonl(shadow_dir / "trades.jsonl")
    events = read_jsonl(shadow_dir / "events.jsonl")
    entries, settled, thin = {}, {}, 0
    for r in trades:
        t = r.get("type")
        if t == "entry":
            entries[r["key"]] = r
        elif t == "settled":
            settled[r["key"]] = r
        elif t == "skip_thin":
            thin += 1
    rows = []
    for key, e in entries.items():
        s = settled.get(key)
        rows.append({
            "ts": e["ts"], "league": e.get("league"), "question": e.get("question"), "outcome": e.get("outcome"),
            "vwap": e.get("vwap"), "best_ask": e.get("best_ask"), "available": e.get("available_shares"),
            "ended_flag": e.get("event_ended_flag") is True,
            "result": s["result"] if s else "pending", "pnl": s["pnl"] if s else None,
            "settled_ts": s["ts"] if s else None,
        })
    rows.sort(key=lambda r: r["ts"])
    done = [r for r in rows if r["result"] != "pending"]
    kpi = {
        "entries": len(rows), "settled": len(done), "pending": len(rows) - len(done),
        "wins": sum(r["result"] == "win" for r in done), "losses": sum(r["result"] == "loss" for r in done),
        "splits": sum(r["result"] == "split" for r in done),
        "pnl": round(sum(r["pnl"] for r in done), 2), "thin": thin,
        "avg_fill": round(statistics.mean(r["vwap"] for r in rows), 4) if rows else None,
    }
    timing = {}
    for label, flag in (("ended", True), ("in_play", False)):
        sub = [r for r in rows if r["ended_flag"] is flag]
        d = [r for r in sub if r["result"] != "pending"]
        timing[label] = {"entries": len(sub), "settled": len(d),
                         "wins": sum(r["result"] == "win" for r in d),
                         "losses": sum(r["result"] == "loss" for r in d),
                         "splits": sum(r["result"] == "split" for r in d),
                         "pnl": round(sum(r["pnl"] for r in d), 2)}
    ev = {}
    for r in events:
        e = ev.setdefault(r["event_id"], {"first": r["ts"], "live": None, "ended": None})
        st = r.get("state", {})
        if st.get("live") and not e["live"]:
            e["live"] = r["ts"]
        if st.get("ended") is True and not e["ended"]:
            e["ended"] = r["ts"]
    durs = []
    for e in ev.values():
        if e["live"] and e["ended"]:
            a = datetime.fromisoformat(e["live"])
            b = datetime.fromisoformat(e["ended"])
            durs.append((b - a).total_seconds() / 60)
    last = max([r["ts"] for r in trades] + [r["ts"] for r in events], default=None)
    return {"rows": rows[-500:], "kpi": kpi, "timing": timing, "last_activity": last,
            "events": {"seen": len(ev), "ended": sum(1 for e in ev.values() if e["ended"]),
                       "median_minutes": round(statistics.median(durs), 1) if durs else None}}


def build(shadow_dir, summary_path, config_path):
    summary = json.loads(Path(summary_path).read_text()) if Path(summary_path).exists() else None
    config = json.loads(Path(config_path).read_text()) if Path(config_path).exists() else {}
    return {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "shadow": build_shadow(Path(shadow_dir)), "backtest": summary, "config": config}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--shadow-dir", default="data/shadow")
    ap.add_argument("--summary", default="data/backtest_summary.json")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--out", default="dashboard.html")
    ap.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                    help="keep rebuilding every N seconds (min 5); the page reloads itself")
    a = ap.parse_args(argv)
    refresh = max(5, a.watch) if a.watch else 0
    try:
        while True:
            write_once(a, refresh)
            if not refresh:
                return 0
            time.sleep(refresh)
    except KeyboardInterrupt:
        print("stopped")
        return 0


def write_once(a, refresh):
    data = build(a.shadow_dir, a.summary, a.config)
    payload = json.dumps(data).replace("</", "<\\/")
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    html = TEMPLATE.replace("__DATA__", payload).replace("__REFRESH__", meta)
    tmp = Path(a.out + ".tmp")
    tmp.write_text(html, encoding="utf-8")
    os.replace(tmp, a.out)                  # swap in one step so the browser never reads half a file
    k = data["shadow"]["kpi"]
    print(f"{datetime.now().strftime('%H:%M:%S')} wrote {a.out} | shadow: {k['entries']} pretend buys, {k['settled']} settled, P&L {k['pnl']:+.2f}")


TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
__REFRESH__
<title>PolySweeper Dashboard</title>
<style>
:root {
  color-scheme: light;
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
  --s1:#2a78d6; --s2:#eb6834;
  --good:#0ca30c; --goodtext:#006300; --crit:#d03b3b; --warn:#fab219; --warntext:#8a5a00;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
    --s1:#3987e5; --s2:#d95926; --goodtext:#0ca30c; --warntext:#fab219;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
  --s1:#3987e5; --s2:#d95926; --goodtext:#0ca30c; --warntext:#fab219;
}
* { box-sizing: border-box; }
body { margin:0; background:var(--page); color:var(--ink); font-family: system-ui,-apple-system,"Segoe UI",sans-serif; line-height:1.45; }
.wrap { max-width:1120px; margin:0 auto; padding:20px 16px 56px; }
header { display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; margin-bottom:8px; }
h1 { font-size:22px; margin:0; font-weight:650; }
h2 { font-size:17px; margin:34px 0 4px; font-weight:650; }
.sub { color:var(--ink2); font-size:14px; margin:0 0 14px; }
.meta { color:var(--muted); font-size:13px; }
button.toggle { background:var(--surface); color:var(--ink); border:1px solid var(--border); border-radius:8px; padding:6px 12px; font:inherit; font-size:13px; cursor:pointer; }
.banner { background:var(--surface); border:1px solid var(--border); border-left:4px solid var(--warn); border-radius:10px; padding:12px 14px; font-size:14px; color:var(--ink2); margin:10px 0 6px; }
.banner b { color:var(--ink); }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(150px,100%),1fr)); gap:12px; margin:14px 0; }
.tile { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:14px 16px; }
.tile .v { font-size:30px; font-weight:650; letter-spacing:-0.01em; }
.tile .l { font-size:13px; color:var(--ink2); margin-top:2px; }
.tile .n { font-size:12px; color:var(--muted); margin-top:4px; }
.grid2 { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(340px,100%),1fr)); gap:14px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:14px 16px 12px; min-width:0; overflow-x:auto; }
.card h3 { font-size:15px; margin:0 0 2px; font-weight:600; }
.card .why { font-size:13px; color:var(--ink2); margin:0 0 8px; }
.legend { display:flex; gap:14px; font-size:13px; color:var(--ink2); margin:2px 0 6px; flex-wrap:wrap; }
.legend i { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px; vertical-align:-1px; }
svg { width:100%; height:auto; display:block; overflow:visible; }
svg text { fill:var(--muted); font-size:11px; font-family:inherit; }
.empty { color:var(--muted); font-size:14px; padding:26px 6px; text-align:center; }
details { margin-top:6px; } summary { cursor:pointer; font-size:12px; color:var(--ink2); }
table { width:100%; border-collapse:collapse; font-size:13px; margin-top:6px; min-width:460px; }
th,td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--grid); vertical-align:top; }
th { color:var(--ink2); font-weight:600; font-size:12px; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
.res { font-weight:600; white-space:nowrap; }
.res.win { color:var(--goodtext); } .res.loss { color:var(--crit); } .res.split { color:var(--warntext); } .res.pending { color:var(--ink2); font-weight:500; }
.rules { columns:2 280px; font-size:14px; color:var(--ink2); }
.rules div { break-inside:avoid; padding:3px 0; } .rules b { color:var(--ink); }
ul.caveats { color:var(--ink2); font-size:14px; padding-left:20px; margin:6px 0; } ul.caveats li { margin:4px 0; }
#tip { position:fixed; pointer-events:none; background:var(--surface); color:var(--ink); border:1px solid var(--border); border-radius:8px; padding:8px 10px; font-size:12px; box-shadow:0 4px 18px rgba(0,0,0,.18); opacity:0; transition:opacity .08s; z-index:10; max-width:260px; }
#tip .t { font-weight:600; margin-bottom:3px; } #tip .r { display:flex; gap:6px; align-items:center; color:var(--ink2); }
#tip i { width:9px; height:9px; border-radius:3px; display:inline-block; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>PolySweeper dashboard</h1>
      <div class="meta" id="meta"></div>
    </div>
    <button class="toggle" id="themeBtn" type="button">Light / dark</button>
  </header>
  <div class="banner" id="banner"></div>

  <h2>Shadow mode: real prices, pretend orders</h2>
  <p class="sub">The tool watches live matches, reads the real order book and pretends to buy 5 shares. No money is involved.</p>
  <div class="tiles" id="tiles"></div>
  <div class="grid2">
    <div class="card"><h3>Fake profit over time</h3><p class="why">Running total of pretend profit, each point is one settled pretend trade.</p><div id="pnl"></div></div>
    <div class="card"><h3>Prices we would really have paid</h3><p class="why">Average fill price of each pretend buy. Higher price means a smaller profit and a bigger loss when wrong.</p><div id="hist"></div></div>
  </div>
  <div class="card" style="margin-top:14px"><h3>Did buying after the match ended help?</h3><p class="why">Splits pretend buys by whether Polymarket had already marked the match as ended at that moment.</p><div id="timing"></div></div>
  <div class="card" style="margin-top:14px"><h3>Matches the tool has watched</h3><p class="why" id="evtext"></p></div>
  <div class="card" style="margin-top:14px"><h3>Latest pretend trades</h3><div id="trades"></div></div>

  <h2>Historical backtest</h2>
  <p class="sub">Past finished matches, buying when the price first rose into 0.96 to 0.995 and holding to payout. Uses mid prices, so it is optimistic.</p>
  <div class="tiles" id="btTiles"></div>
  <div class="grid2">
    <div class="card"><h3>Profit per share by price band</h3><p class="why">Cents per share after fees. Above zero means the band paid, below zero means it lost money.</p><div class="legend" id="lg1"></div><div id="ev"></div></div>
    <div class="card"><h3>Loss rate by when you buy</h3><p class="why">Minutes between the buy moment and the market payout. Football pays out soon after the final whistle, so this split is less reliable for football.</p><div class="legend" id="lg2"></div><div id="tm"></div></div>
  </div>

  <h2>Risk rules in force</h2>
  <p class="sub">From <code>config.json</code>. One loss costs about the amount per trade, so these limits decide how much a bad day can cost.</p>
  <div class="card"><div class="rules" id="rules"></div></div>

  <h2>Read this before trusting any number</h2>
  <div class="card"><ul class="caveats">
    <li><b>Shadow mode needs time.</b> Judge it only after 100 or more settled pretend trades, ideally a few weeks.</li>
    <li><b>The backtest uses mid prices,</b> not real asking prices, and cannot see order-book depth. Real results will be worse.</li>
    <li><b>Losses are rare but large.</b> At a price near 0.98, one loss wipes out roughly 49 wins.</li>
    <li><b>Cancelled matches, ties, forfeits and walkovers can pay 50/50,</b> which is a big loss when you bought near 1.00.</li>
    <li><b>This is not financial advice.</b> No real money should be used until shadow mode shows an edge.</li>
  </ul></div>
</div>
<div id="tip"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById('data').textContent);
  var NS = 'http://www.w3.org/2000/svg';
  var tip = document.getElementById('tip');
  function $(id) { return document.getElementById(id); }
  function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]; }); }
  function money(x) { return (x < 0 ? '-$' : '+$') + Math.abs(x).toFixed(2); }
  function el(n, a, p) { var e = document.createElementNS(NS, n); for (var k in a) e.setAttribute(k, a[k]); if (p) p.appendChild(e); return e; }
  function showTip(evt, title, rows) {
    tip.innerHTML = '<div class="t">' + esc(title) + '</div>' + rows.map(function (r) {
      return '<div class="r">' + (r.color ? '<i style="background:' + r.color + '"></i>' : '') + esc(r.text) + '</div>'; }).join('');
    tip.style.opacity = 1;
    var x = evt.clientX + 14, y = evt.clientY + 14;
    if (x + 270 > window.innerWidth) x = evt.clientX - 270;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  function hideTip() { tip.style.opacity = 0; }

  function niceTicks(lo, hi, n) {
    if (hi === lo) { hi = lo + 1; }
    var span = hi - lo, step = Math.pow(10, Math.floor(Math.log10(span / n)));
    var err = span / n / step; step *= err >= 5 ? 5 : err >= 2 ? 2 : 1;
    var a = Math.floor(lo / step) * step, b = Math.ceil(hi / step) * step, t = [];
    for (var v = a; v <= b + step / 2; v += step) t.push(+v.toFixed(6));
    return t;
  }
  function barPath(x, y0, y1, w, r) {
    var up = y1 < y0, h = Math.abs(y1 - y0); r = Math.min(r, h, w / 2);
    if (h < 0.5) return 'M' + x + ',' + y0 + 'h' + w + 'v0h-' + w + 'z';
    if (up) return 'M' + x + ',' + y0 + 'V' + (y1 + r) + 'Q' + x + ',' + y1 + ' ' + (x + r) + ',' + y1 + 'H' + (x + w - r) + 'Q' + (x + w) + ',' + y1 + ' ' + (x + w) + ',' + (y1 + r) + 'V' + y0 + 'Z';
    return 'M' + x + ',' + y0 + 'V' + (y1 - r) + 'Q' + x + ',' + y1 + ' ' + (x + r) + ',' + y1 + 'H' + (x + w - r) + 'Q' + (x + w) + ',' + y1 + ' ' + (x + w) + ',' + (y1 - r) + 'V' + y0 + 'Z';
  }
  function legend(id, items) {
    $(id).innerHTML = items.map(function (i) { return '<span><i style="background:' + i.color + '"></i>' + esc(i.name) + '</span>'; }).join('');
  }
  function tableView(host, head, rows) {
    var d = document.createElement('details');
    d.innerHTML = '<summary>Table view</summary><table><thead><tr>' + head.map(function (h, i) { return '<th class="' + (i ? 'num' : '') + '">' + esc(h) + '</th>'; }).join('') +
      '</tr></thead><tbody>' + rows.map(function (r) { return '<tr>' + r.map(function (c, i) { return '<td class="' + (i ? 'num' : '') + '">' + esc(c) + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody></table>';
    host.appendChild(d);
  }

  // grouped bars: cats = [labels]; series = [{name,color,vals[]}]; fmt(v) text; unit label
  function groupedBars(host, cats, series, o) {
    host.innerHTML = '';
    var W = 640, H = 270, L = 46, R = 10, T = 18, B = 34;
    var all = []; series.forEach(function (s) { s.vals.forEach(function (v) { if (v != null) all.push(v); }); });
    if (!all.length) { host.innerHTML = '<div class="empty">No data yet.</div>'; return; }
    var lo = Math.min(0, Math.min.apply(null, all)), hi = Math.max(0, Math.max.apply(null, all));
    if (hi === lo) hi = lo + 1;
    var ticks = niceTicks(lo, hi, 4); lo = ticks[0]; hi = ticks[ticks.length - 1];
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': o.aria });
    var y = function (v) { return T + (hi - v) / (hi - lo) * (H - T - B); };
    ticks.forEach(function (t) {
      el('line', { x1: L, x2: W - R, y1: y(t), y2: y(t), stroke: t === 0 ? css('--axis') : css('--grid'), 'stroke-width': t === 0 ? 1.5 : 1 }, svg);
      var tx = el('text', { x: L - 6, y: y(t) + 4, 'text-anchor': 'end' }, svg); tx.textContent = t;
    });
    var band = (W - L - R) / cats.length, ns = series.length, bw = Math.min(30, band * 0.72 / ns), gap = 2;
    cats.forEach(function (c, i) {
      var x0 = L + i * band + (band - (bw * ns + gap * (ns - 1))) / 2;
      series.forEach(function (s, j) {
        var v = s.vals[i]; if (v == null) return;
        var x = x0 + j * (bw + gap);
        el('path', { d: barPath(x, y(0), y(v), bw, 4), fill: s.color }, svg);
        var lab = el('text', { x: x + bw / 2, y: v >= 0 ? y(v) - 4 : y(v) + 12, 'text-anchor': 'middle' }, svg);
        lab.textContent = o.fmt(v);
      });
      var cx = el('text', { x: L + i * band + band / 2, y: H - 14, 'text-anchor': 'middle' }, svg); cx.textContent = c;
      var hit = el('rect', { x: L + i * band, y: T, width: band, height: H - T - B, fill: 'transparent' }, svg);
      hit.addEventListener('mousemove', function (e) {
        showTip(e, c + (o.catSuffix || ''), series.map(function (s) { return { color: s.color, text: s.name + ': ' + (s.vals[i] == null ? 'no data' : o.fmt(s.vals[i])) + (s.extra && s.extra[i] ? '  (' + s.extra[i] + ')' : '') }; }));
      });
      hit.addEventListener('mouseleave', hideTip);
    });
    if (o.xTitle) { var xt = el('text', { x: L + (W - L - R) / 2, y: H - 1, 'text-anchor': 'middle' }, svg); xt.textContent = o.xTitle; }
    host.appendChild(svg);
    tableView(host, [o.catName].concat(series.map(function (s) { return s.name; })), cats.map(function (c, i) { return [c].concat(series.map(function (s) { return s.vals[i] == null ? '' : o.fmt(s.vals[i]); })); }));
  }

  // ---------- header, banner ----------
  var S = D.shadow, K = S.kpi;
  $('meta').textContent = 'Generated ' + D.generated.replace('T', ' ').replace('+00:00', ' UTC') + (S.last_activity ? '  |  last shadow activity ' + S.last_activity.replace('T', ' ').replace('+00:00', ' UTC') : '  |  no shadow data yet');
  $('banner').innerHTML = K.entries === 0
    ? '<b>No shadow data yet.</b> Start <code>run_shadow.bat</code> and leave it running. Charts below will fill in as matches finish.'
    : (K.settled < 100 ? '<b>Too early to judge.</b> ' + K.settled + ' settled pretend trades so far; aim for 100 or more before drawing conclusions.'
                       : '<b>' + K.settled + ' settled pretend trades.</b> Compare the loss count with the backtest before deciding anything.');
  $('themeBtn').addEventListener('click', function () {
    var r = document.documentElement, cur = r.getAttribute('data-theme');
    var dark = cur ? cur === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    r.setAttribute('data-theme', dark ? 'light' : 'dark'); draw();
  });

  function tile(v, l, n, cls) { return '<div class="tile"><div class="v" ' + (cls ? 'style="color:' + cls + '"' : '') + '>' + v + '</div><div class="l">' + l + '</div>' + (n ? '<div class="n">' + n + '</div>' : '') + '</div>'; }

  function drawShadow() {
    var pnlColor = K.pnl < 0 ? 'var(--crit)' : K.pnl > 0 ? 'var(--goodtext)' : '';
    $('tiles').innerHTML =
      tile(K.entries, 'Pretend buys', K.pending + ' still waiting for payout') +
      tile(K.settled, 'Settled', 'paid out and scored') +
      tile(K.wins + ' / ' + K.losses, 'Wins / losses', K.splits + ' paid 50/50', K.losses > 0 ? 'var(--crit)' : '') +
      tile(K.settled ? money(K.pnl) : '$0.00', 'Fake profit', 'after fees, 5 shares per trade', pnlColor) +
      tile(K.thin, 'Skipped: book too thin', 'price was right but fewer than 5 shares for sale');

    // P&L line
    var host = $('pnl'); host.innerHTML = '';
    var pts = S.rows.filter(function (r) { return r.pnl != null; }).sort(function (a, b) { return a.settled_ts < b.settled_ts ? -1 : 1; });
    if (pts.length < 2) { host.innerHTML = '<div class="empty">Needs at least 2 settled pretend trades.</div>'; }
    else {
      var cum = 0, P = pts.map(function (r, i) { cum += r.pnl; return { i: i, t: new Date(r.settled_ts).getTime(), v: cum, r: r }; });
      var W = 640, H = 250, L = 46, R = 12, T = 14, B = 30;
      var lo = Math.min(0, Math.min.apply(null, P.map(function (p) { return p.v; }))), hi = Math.max(0, Math.max.apply(null, P.map(function (p) { return p.v; })));
      var ticks = niceTicks(lo, hi, 4); lo = ticks[0]; hi = ticks[ticks.length - 1];
      var t0 = P[0].t, t1 = P[P.length - 1].t; if (t1 === t0) t1 = t0 + 1;
      var x = function (t) { return L + (t - t0) / (t1 - t0) * (W - L - R); }, y = function (v) { return T + (hi - v) / (hi - lo) * (H - T - B); };
      var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Cumulative fake profit over time' });
      ticks.forEach(function (t) {
        el('line', { x1: L, x2: W - R, y1: y(t), y2: y(t), stroke: t === 0 ? css('--axis') : css('--grid'), 'stroke-width': t === 0 ? 1.5 : 1 }, svg);
        var tx = el('text', { x: L - 6, y: y(t) + 4, 'text-anchor': 'end' }, svg); tx.textContent = (t < 0 ? '-$' : '$') + Math.abs(t);
      });
      var d = P.map(function (p, i) { return (i ? 'L' : 'M') + x(p.t) + ',' + y(p.v); }).join('');
      el('path', { d: d, fill: 'none', stroke: css('--s1'), 'stroke-width': 2, 'stroke-linejoin': 'round' }, svg);
      if (P.length <= 40) P.forEach(function (p) { el('circle', { cx: x(p.t), cy: y(p.v), r: 4, fill: css('--s1'), stroke: css('--surface'), 'stroke-width': 2 }, svg); });
      var a = el('text', { x: L, y: H - 8 }, svg); a.textContent = new Date(t0).toLocaleDateString();
      var b = el('text', { x: W - R, y: H - 8, 'text-anchor': 'end' }, svg); b.textContent = new Date(t1).toLocaleDateString();
      var cross = el('line', { y1: T, y2: H - B, stroke: css('--axis'), 'stroke-width': 1, opacity: 0 }, svg);
      var hit = el('rect', { x: L, y: T, width: W - L - R, height: H - T - B, fill: 'transparent' }, svg);
      hit.addEventListener('mousemove', function (e) {
        var rc = svg.getBoundingClientRect(), mx = (e.clientX - rc.left) / rc.width * W, best = P[0];
        P.forEach(function (p) { if (Math.abs(x(p.t) - mx) < Math.abs(x(best.t) - mx)) best = p; });
        cross.setAttribute('x1', x(best.t)); cross.setAttribute('x2', x(best.t)); cross.setAttribute('opacity', 1);
        showTip(e, new Date(best.t).toLocaleString(), [{ color: css('--s1'), text: 'Running total: ' + money(best.v) }, { text: (best.r.result === 'win' ? 'Win' : best.r.result === 'loss' ? 'Loss' : '50/50') + ' ' + money(best.r.pnl) + ' on ' + (best.r.outcome || '') }]);
      });
      hit.addEventListener('mouseleave', function () { cross.setAttribute('opacity', 0); hideTip(); });
      host.appendChild(svg);
      tableView(host, ['Settled', 'Running total'], P.slice(-30).map(function (p) { return [new Date(p.t).toLocaleString(), money(p.v)]; }));
    }

    // histogram of fills
    var hh = $('hist'); hh.innerHTML = '';
    var fills = S.rows.map(function (r) { return r.vwap; }).filter(function (v) { return v != null; });
    if (!fills.length) { hh.innerHTML = '<div class="empty">No pretend buys yet.</div>'; }
    else {
      var edges = [0.96, 0.965, 0.97, 0.975, 0.98, 0.985, 0.99, 0.995], cats = [], cnt = [];
      for (var i = 0; i < edges.length - 1; i++) { cats.push(edges[i].toFixed(3).slice(1)); cnt.push(fills.filter(function (v) { return v >= edges[i] && (v < edges[i + 1] || (i === edges.length - 2 && v <= edges[i + 1])); }).length); }
      groupedBars(hh, cats, [{ name: 'Pretend buys', color: css('--s1'), vals: cnt }], { aria: 'Histogram of fill prices', fmt: function (v) { return String(v); }, catName: 'Price from', xTitle: 'average fill price', catSuffix: ' and up' });
    }

    // timing table
    var tm = $('timing'), T2 = S.timing;
    function trow(label, t) { return '<tr><td>' + label + '</td><td class="num">' + t.entries + '</td><td class="num">' + t.settled + '</td><td class="num">' + t.wins + '</td><td class="num">' + t.losses + '</td><td class="num">' + t.splits + '</td><td class="num">' + (t.settled ? money(t.pnl) : '-') + '</td></tr>'; }
    tm.innerHTML = '<table><thead><tr><th>When we pretended to buy</th><th class="num">Buys</th><th class="num">Settled</th><th class="num">Wins</th><th class="num">Losses</th><th class="num">50/50</th><th class="num">Fake profit</th></tr></thead><tbody>' +
      trow('After Polymarket marked the match ended', T2.ended) + trow('While the match was still in play', T2.in_play) + '</tbody></table>';

    $('evtext').textContent = S.events.seen
      ? S.events.seen + ' matches observed, ' + S.events.ended + ' seen ending' + (S.events.median_minutes ? ', typical length about ' + S.events.median_minutes + ' minutes from live to ended' : '') + '.'
      : 'No matches recorded yet.';

    // trades table
    var rows = S.rows.slice(-25).reverse();
    var icon = { win: '✓ Win', loss: '✕ Loss', split: '½ 50/50', pending: '… Waiting' };
    $('trades').innerHTML = rows.length ? '<table><thead><tr><th>Time (UTC)</th><th>Match</th><th>Bought</th><th class="num">Fill</th><th>Ended flag</th><th>Result</th><th class="num">Fake profit</th></tr></thead><tbody>' +
      rows.map(function (r) { return '<tr><td>' + esc(r.ts.replace('T', ' ').slice(0, 16)) + '</td><td>' + esc((r.question || '').slice(0, 60)) + '</td><td>' + esc(r.outcome) + '</td><td class="num">' + (r.vwap == null ? '' : r.vwap.toFixed(3)) + '</td><td>' + (r.ended_flag ? 'ended' : 'in play') + '</td><td class="res ' + r.result + '">' + icon[r.result] + '</td><td class="num">' + (r.pnl == null ? '' : money(r.pnl)) + '</td></tr>'; }).join('') + '</tbody></table>'
      : '<div class="empty">No pretend trades yet.</div>';
  }

  function drawBacktest() {
    var B = D.backtest;
    if (!B) { $('btTiles').innerHTML = '<div class="empty">No backtest summary file found.</div>'; return; }
    function bt(name, s) { return tile(s.tokens.toLocaleString(), name + ' trades tested', s.markets.toLocaleString() + ' matches over about ' + Math.round(s.days) + ' days') +
      tile(s.losses, name + ' losses', (100 * s.losses / s.tokens).toFixed(1) + '% of trades', s.losses ? 'var(--crit)' : '') +
      tile((s.ev_cents >= 0 ? '+' : '') + s.ev_cents + 'c', name + ' profit per share', 'cents after fees, optimistic', s.ev_cents < 0 ? 'var(--crit)' : 'var(--goodtext)'); }
    $('btTiles').innerHTML = bt('Esports', B.esports) + bt('Football', B.football);
    var c1 = css('--s1'), c2 = css('--s2');
    legend('lg1', [{ name: 'Esports', color: c1 }, { name: 'Football', color: c2 }]);
    legend('lg2', [{ name: 'Esports', color: c1 }, { name: 'Football', color: c2 }]);
    var labs = B.esports.buckets.map(function (b) { return b.label; });
    function byLabel(arr, key) { return labs.map(function (l) { var f = arr.filter(function (b) { return b.label === l; })[0]; return f ? f[key] : null; }); }
    groupedBars($('ev'), labs, [
      { name: 'Esports', color: c1, vals: byLabel(B.esports.buckets, 'ev_cents'), extra: labs.map(function (l) { var f = B.esports.buckets.filter(function (b) { return b.label === l; })[0]; return f ? f.n + ' trades, ' + f.losses + ' losses' : ''; }) },
      { name: 'Football', color: c2, vals: byLabel(B.football.buckets, 'ev_cents'), extra: labs.map(function (l) { var f = B.football.buckets.filter(function (b) { return b.label === l; })[0]; return f ? f.n + ' trades, ' + f.losses + ' losses' : ''; }) }
    ], { aria: 'Profit per share by price band', fmt: function (v) { return (v >= 0 ? '+' : '') + v.toFixed(2) + 'c'; }, catName: 'Entry price band', xTitle: 'price when we would have bought' });
    var tl = B.esports.timing.map(function (b) { return b.label; });
    function tv(arr, key) { return tl.map(function (l) { var f = arr.filter(function (b) { return b.label === l; })[0]; return f ? f[key] : null; }); }
    function tx(arr) { return tl.map(function (l) { var f = arr.filter(function (b) { return b.label === l; })[0]; return f ? f.n + ' trades, ' + f.losses + ' losses' : ''; }); }
    groupedBars($('tm'), tl, [
      { name: 'Esports', color: c1, vals: tv(B.esports.timing, 'loss_pct'), extra: tx(B.esports.timing) },
      { name: 'Football', color: c2, vals: tv(B.football.timing, 'loss_pct'), extra: tx(B.football.timing) }
    ], { aria: 'Loss rate by minutes before payout', fmt: function (v) { return v.toFixed(1) + '%'; }, catName: 'Minutes before payout', xTitle: 'minutes between buying and payout', catSuffix: ' min before payout' });
  }

  function drawRules() {
    var c = D.config || {}, items = [
      ['Bankroll (fake)', '$' + c.bankroll], ['Max per trade', '$' + c.max_stake_per_trade], ['Max open at once', '$' + c.max_open_total],
      ['Max open per sport', '$' + c.max_open_per_sport], ['Daily loss limit', '$' + c.daily_loss_limit], ['Pause after any loss', c.pause_on_loss ? 'yes' : 'no'],
      ['Buy price window', c.price_min + ' to ' + c.price_max], ['Min order size', c.min_shares + ' shares'], ['Sources that must agree', c.min_sources],
      ['Wait after match ends', c.confirm_minutes + ' min'], ['Sports enabled', (c.enabled_sports || []).join(', ')], ['Bet types allowed', (c.allowed_market_types || []).join(', ')]];
    $('rules').innerHTML = items.map(function (i) { return '<div>' + esc(i[0]) + ': <b>' + esc(i[1]) + '</b></div>'; }).join('');
  }
  function draw() { hideTip(); drawShadow(); drawBacktest(); drawRules(); }
  draw();
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', draw);
})();
</script>
</body>
</html>
'''

if __name__ == "__main__":
    sys.exit(main())
