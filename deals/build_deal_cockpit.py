#!/usr/bin/env python3
"""
Deal Cockpit Generator (build_deal_cockpit.py)
------------------------------------------------------------
1物件の YAML（deals/*.yaml）を読み、対話型の投資判断シミュレーター
HTML を output/ に生成する。計算は全てブラウザ内 JS（サーバー不要・
スライダーで即再計算）。Python は YAML → JSON 埋め込みのみ。

Usage:
    python deals/build_deal_cockpit.py deals/placespot-shinbashi.yaml
    python deals/build_deal_cockpit.py            # 引数なし=全 deals/*.yaml
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEALS_DIR = ROOT / "deals"
OUTPUT_DIR = ROOT / "output"


def load_deal(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_html(cfg: dict) -> str:
    deal = cfg["deal"]
    data_json = json.dumps(cfg, ensure_ascii=False)
    title = f"{deal['name']} 投資判断シミュレーター"
    return _TEMPLATE.replace("__TITLE__", title).replace("__DATA_JSON__", data_json)


# ============================================================
# HTML template (iUMA Dark design system)
# ============================================================
_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0f1117; --surface:#1a1d27; --surface2:#242836; --card:#1a1d27;
  --border:#2d3348; --border-light:#3d4460;
  --gold:#c9a84c; --accent:#6366f1; --accent2:#8b5cf6; --blue:#3b82f6;
  --green:#22c55e; --green-light:#4ade80; --red:#ef4444; --red-light:#f87171;
  --yellow:#eab308; --amber:#fbbf24;
  --text:#e4e4e7; --text-secondary:#9ca3af; --text-muted:#7c8293;
  --font:'Inter','Noto Sans JP',sans-serif; --mono:'JetBrains Mono',monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--font);line-height:1.6;padding:24px;max-width:1280px;margin:0 auto}
h1{font-size:24px;font-weight:800;letter-spacing:-.02em}
h2{font-size:15px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.05em;margin-bottom:14px}
.sub{color:var(--text-muted);font-size:13px;margin-top:4px}
.badge{display:inline-block;background:var(--gold);color:#1a1207;font-size:11px;font-weight:700;padding:2px 8px;border-radius:6px;margin-left:8px;vertical-align:middle}
.badge.est{background:var(--amber)}
.badge.warn{background:var(--red);color:#fff}
header{border-bottom:1px solid var(--border);padding-bottom:18px;margin-bottom:24px}
.meta{display:flex;gap:18px;flex-wrap:wrap;margin-top:10px;font-size:13px;color:var(--text-secondary)}
.meta b{color:var(--text)}
section{margin-bottom:28px}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.controls{display:grid;grid-template-columns:repeat(3,1fr);gap:18px 28px}
.ctrl label{display:block;font-size:12px;color:var(--text-secondary);margin-bottom:6px;font-weight:500}
.ctrl .val{color:var(--gold);font-family:var(--mono);font-weight:700}
input[type=range]{width:100%;accent-color:var(--accent);height:4px}
.toggle-row{display:flex;align-items:center;gap:10px;margin-top:6px;font-size:13px;color:var(--text-secondary)}
.toggle-row input{accent-color:var(--accent);width:16px;height:16px}
/* scenario cards */
.scn{position:relative;overflow:hidden}
.scn h3{font-size:16px;font-weight:700;margin-bottom:2px}
.scn .tag{font-size:11px;color:var(--text-muted);margin-bottom:14px;display:block;min-height:30px}
.scn.win{border-color:var(--green);box-shadow:0 0 0 1px var(--green)}
.scn .winflag{position:absolute;top:0;right:0;background:var(--green);color:#04210f;font-size:10px;font-weight:800;padding:3px 10px;border-bottom-left-radius:8px}
.kpi{display:flex;justify-content:space-between;align-items:baseline;padding:7px 0;border-bottom:1px dashed var(--border)}
.kpi:last-child{border-bottom:none}
.kpi .k{font-size:12px;color:var(--text-secondary)}
.kpi .v{font-family:var(--mono);font-weight:700;font-size:14px}
.kpi .v.big{font-size:18px}
.pos{color:var(--green-light)} .neg{color:var(--red-light)} .neu{color:var(--text)}
.hero{margin:10px 0 4px;padding:12px;background:var(--surface2);border-radius:10px;text-align:center}
.hero .label{font-size:11px;color:var(--text-muted)}
.hero .num{font-family:var(--mono);font-size:26px;font-weight:800;margin-top:2px}
/* verdict */
.verdict{background:linear-gradient(135deg,var(--surface2),var(--surface));border:1px solid var(--border-light);border-radius:14px;padding:18px 22px}
.verdict .line{font-size:15px;margin:4px 0}
.verdict .em{color:var(--gold);font-weight:700}
/* breakeven table */
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:right;padding:9px 12px;border-bottom:1px solid var(--border)}
th:first-child,td:first-child{text-align:left}
th{color:var(--text-muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
td.mono{font-family:var(--mono);font-weight:700}
.delta-up{color:var(--green-light)} .delta-dn{color:var(--red-light)}
/* yakuin inputs */
.yk-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.yk-grid .f label{font-size:12px;color:var(--text-secondary);display:block;margin-bottom:4px}
.yk-grid input[type=number]{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:8px;color:var(--text);padding:8px 10px;font-family:var(--mono)}
.note{font-size:12px;color:var(--text-muted);line-height:1.7;margin-top:10px}
.callout{background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.35);border-radius:10px;padding:12px 14px;font-size:13px;color:var(--red-light);margin-top:14px}
.callout b{color:#fff}
footer{margin-top:36px;padding-top:18px;border-top:1px solid var(--border);font-size:11px;color:var(--text-muted)}
@media(max-width:900px){.grid3,.controls{grid-template-columns:1fr}.yk-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1 id="dealName"></h1>
  <div class="sub" id="dealAddr"></div>
  <div class="meta" id="dealMeta"></div>
</header>

<!-- Controls -->
<section class="card">
  <h2>前提を動かす（スライダー＝即再計算）</h2>
  <div class="controls">
    <div class="ctrl"><label>取得価格 <span class="val" id="lblPrice"></span></label>
      <input type="range" id="price" min="15000000" max="40000000" step="500000"></div>
    <div class="ctrl"><label>金利（年） <span class="val" id="lblRate"></span></label>
      <input type="range" id="rate" min="1.0" max="4.5" step="0.05"></div>
    <div class="ctrl"><label>返済年数 <span class="val" id="lblYears"></span></label>
      <input type="range" id="years" min="10" max="35" step="1"></div>
    <div class="ctrl"><label>自己資金比率 <span class="val" id="lblDown"></span></label>
      <input type="range" id="down" min="0" max="100" step="5"></div>
    <div class="ctrl"><label>民泊・稼働率 <span class="val" id="lblOccM"></span></label>
      <input type="range" id="occM" min="30" max="95" step="1"></div>
    <div class="ctrl"><label>民泊・ADR（泊単価） <span class="val" id="lblAdrM"></span></label>
      <input type="range" id="adrM" min="10000" max="40000" step="500"></div>
    <div class="ctrl"><label>旅館・稼働率 <span class="val" id="lblOccR"></span></label>
      <input type="range" id="occR" min="30" max="95" step="1"></div>
    <div class="ctrl"><label>旅館・ADR（泊単価） <span class="val" id="lblAdrR"></span></label>
      <input type="range" id="adrR" min="10000" max="40000" step="500"></div>
    <div class="ctrl"><label>賃貸・想定家賃（月） <span class="val" id="lblRent"></span></label>
      <input type="range" id="rent" min="90000" max="200000" step="2000"></div>
    <div class="ctrl" style="grid-column:span 3">
      <label>前提プリセット（ワンタッチで稼働率・ADRを切替）</label>
      <div id="presetBtns" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px"></div>
      <div class="toggle-row"><input type="checkbox" id="capToggle" checked>
        <span>民泊に新法180日上限を適用（福岡市＝特区外なのでON推奨）</span></div>
      <div class="toggle-row"><input type="checkbox" id="renoRental" checked>
        <span>賃貸でもフルリノベ726万を計上（OFF=軽改装200万で試算）</span></div>
      <div class="toggle-row"><input type="checkbox" id="licToggle" checked>
        <span>旅館業の追加コスト（許可・消防点検）を算入</span></div>
    </div>
  </div>
  <div class="callout" style="background:rgba(251,191,36,.08);border-color:rgba(251,191,36,.4);color:var(--amber)">
    <b>前提の最重要論点：</b>業者ADR（民泊36,600/旅館38,400円）は中洲の実勢ADR（12,000〜15,000円）の2倍超。ADR次第で投資判断が黒字↔赤字で反転する。<b>「リサーチ標準/保守」プリセットで必ず両にらみすること。</b>実勢ADRはAirDNA等で5名定員コンプを実測して確定すべき（現状リサーチ推計）。
  </div>
</section>

<!-- Verdict -->
<section class="verdict" id="verdict"></section>

<!-- Scenario cards -->
<section>
  <h2>3つの運用シナリオ（取得価格・前提に対する実力）</h2>
  <div class="grid3" id="scnCards"></div>
</section>

<!-- Break-even -->
<section class="card">
  <h2>損益分岐：いくらまで下がれば「化ける」か</h2>
  <table id="beTable">
    <thead><tr><th>シナリオ</th><th>今の前提で月CF</th><th>CF黒字化する取得価格</th><th>CCR10%達成価格</th><th>今の2,500万との差</th></tr></thead>
    <tbody></tbody>
  </table>
  <div class="note" id="beNote"></div>
</section>

<!-- Yakuin -->
<section class="card">
  <h2>薬院物件（現拠点）— 賃貸 vs 売却して移動</h2>
  <div class="yk-grid">
    <div class="f"><label>現在の想定売却価格（円）</label><input type="number" id="yk_value" placeholder="例: 28000000"></div>
    <div class="f"><label>残債（円）</label><input type="number" id="yk_loan" placeholder="例: 18000000"></div>
    <div class="f"><label>賃貸に出した場合の家賃（月・円）</label><input type="number" id="yk_rent" placeholder="例: 120000"></div>
    <div class="f"><label>保有コスト（月・円：返済+管理+固都税）</label><input type="number" id="yk_hold" placeholder="例: 85000"></div>
  </div>
  <div class="note" id="ykOut"></div>
  <div class="note" id="ykNoteSrc"></div>
</section>

<!-- Licensing & scheme comparison -->
<section class="card">
  <h2>制度・許可：民泊新法 vs 旅館業（簡易宿所）</h2>
  <table id="schemeTable">
    <thead><tr><th>項目</th><th>民泊新法</th><th>旅館業（簡易宿所）</th><th>特区民泊</th></tr></thead>
    <tbody></tbody>
  </table>
  <div class="note" id="schemeConcl"></div>
  <div class="callout" id="blockers" style="background:rgba(239,68,68,.08);border-color:rgba(239,68,68,.35);color:var(--red-light)"></div>
</section>

<!-- Licensing costs -->
<section class="card">
  <h2>旅館業（簡易宿所）化のコストと必要経費</h2>
  <div class="grid3" id="licCost"></div>
  <div class="note" id="licReq"></div>
</section>

<!-- Occupancy basis / research -->
<section class="card">
  <h2>稼働率「183日」の根拠とゼロベース見込み</h2>
  <div class="note" id="occBasis"></div>
  <table id="occTable">
    <thead><tr><th>ゼロベース・シナリオ</th><th>稼働率</th><th>想定ADR</th><th>年間泊数</th><th>想定年間売上</th></tr></thead>
    <tbody></tbody>
  </table>
  <div class="note" id="mktFacts"></div>
  <div class="note" id="sources"></div>
</section>

<footer id="footer"></footer>

<script>
const CFG = __DATA_JSON__;
const yen = n => '¥'+Math.round(n).toLocaleString('ja-JP');
const man = n => (n/10000);
const manFmt = n => '¥'+(Math.round(n/10000)).toLocaleString('ja-JP')+'万';
const pct = n => (n*100).toFixed(2)+'%';
const cls = n => n>0?'pos':(n<0?'neg':'neu');

// annual debt service per 1 yen of principal
function annuityFactorAnnual(rateAnnual, years){
  const r = rateAnnual/12, n = years*12;
  if(r===0) return 12/n;
  const m = r*Math.pow(1+r,n)/(Math.pow(1+r,n)-1);
  return m*12;
}

function readControls(){
  return {
    price:+price.value, rate:+rate.value/100, years:+years.value,
    down:+down.value/100, occM:+occM.value/100, occR:+occR.value/100,
    adrM:+adrM.value, adrR:+adrR.value,
    rent:+rent.value, applyCap:capToggle.checked, renoRental:renoRental.checked,
    lic:licToggle.checked
  };
}

// NOI is independent of price/financing → compute once per scenario
function noiOf(key, c){
  const acq = CFG.acquisition, s = CFG.scenarios[key];
  if(key==='rental'){
    const gross = c.rent*12;
    const eff = gross*(1-s.vacancy_rate);
    const opex = eff*s.pm_fee_rate + s.fixed_annual_yen;
    return {revenue:gross, noi:eff-opex};
  }
  const occ = key==='minpaku'? c.occM : c.occR;
  const adr = key==='minpaku'? c.adrM : c.adrR;
  const cap = (key==='minpaku' && c.applyCap) ? s.legal_day_cap : 365;
  const nights = Math.min(365*occ, cap);
  const revenue = adr*nights;
  const licRun = (c.lic && s.needs_setup && CFG.licensing) ? (CFG.licensing.running_cost_extra_yen||0) : 0;
  const noi = revenue - revenue*s.var_opex_rate - s.fixed_annual_yen - licRun;
  return {revenue, noi, nights};
}

function setupCost(key, c){
  const s = CFG.scenarios[key], acq = CFG.acquisition;
  let reno = acq.renovation_yen;
  if(key==='rental' && !c.renoRental) reno = 2000000; // 軽改装試算
  let setup = s.needs_setup ? acq.minpaku_setup_yen : 0;
  if(c.lic && s.needs_setup && CFG.licensing) setup += (CFG.licensing.init_cost_extra_yen||0); // 旅館業追加許可コスト
  return {reno, setup};
}

function finance(key, c, price){
  const acq = CFG.acquisition;
  const {revenue, noi, nights} = noiOf(key, c);
  const {reno, setup} = setupCost(key, c);
  const acqCost = price*acq.acquisition_cost_rate;
  const total = price + acqCost + reno + setup;
  const selfCap = total*c.down;
  const loan = total - selfCap;
  const af = annuityFactorAnnual(c.rate, c.years);
  const debt = loan*af;
  const cf = noi - debt;
  return {revenue, noi, nights, reno, setup, acqCost, total, selfCap, loan, debt, cf, af,
    grossYield: revenue/price, fcr: noi/total, ccr: selfCap>0? cf/selfCap : Infinity,
    payback: cf>0? selfCap/cf : Infinity};
}

// break-even acquisition price for CF=0 and for target CCR
function breakevenPrice(key, c, targetCCR){
  const acq = CFG.acquisition;
  const {noi} = noiOf(key, c);
  const {reno, setup} = setupCost(key, c);
  const af = annuityFactorAnnual(c.rate, c.years);
  // CF=0: total = noi/((1-down)*af)
  const denom0 = (1-c.down)*af;
  const totalCF0 = denom0>0 ? noi/denom0 : Infinity;
  // target CCR: total = noi/((1-down)*af + target*down)
  const denomT = (1-c.down)*af + targetCCR*c.down;
  const totalT = denomT>0 ? noi/denomT : Infinity;
  const toPrice = t => (t - reno - setup)/(1+acq.acquisition_cost_rate);
  return {cf0: toPrice(totalCF0), target: toPrice(totalT)};
}

function render(){
  const c = readControls();
  // labels
  lblPrice.textContent = manFmt(c.price);
  lblRate.textContent = (c.rate*100).toFixed(2)+'%';
  lblYears.textContent = c.years+'年';
  lblDown.textContent = (c.down*100).toFixed(0)+'%';
  lblOccM.textContent = (c.occM*100).toFixed(0)+'%';
  lblOccR.textContent = (c.occR*100).toFixed(0)+'%';
  lblAdrM.textContent = yen(c.adrM);
  lblAdrR.textContent = yen(c.adrR);
  lblRent.textContent = yen(c.rent);

  const keys = ['rental','minpaku','ryokan'];
  const res = {}; keys.forEach(k=> res[k]=finance(k,c,c.price));
  // winner by CCR (CF>0 only)
  let win=null, best=-Infinity;
  keys.forEach(k=>{ const r=res[k]; if(r.cf>0 && r.ccr>best){best=r.ccr; win=k;} });

  // scenario cards
  scnCards.innerHTML = keys.map(k=>{
    const s=CFG.scenarios[k], r=res[k], isWin=k===win, est=s.is_estimate;
    const capWarn = (k==='minpaku' && c.applyCap) ? `<div class="callout"><b>新法180日上限を適用中</b>：年${Math.round(r.nights)}泊で頭打ち。${s.cap_note}</div>`:'';
    const nightsRow = k==='rental'? '' : `<div class="kpi"><span class="k">年間稼働日数</span><span class="v">${Math.round(r.nights)}泊</span></div>`;
    return `<div class="card scn ${isWin?'win':''}">
      ${isWin?'<div class="winflag">BEST CCR</div>':''}
      <h3>${s.label}${est?'<span class="badge est">推計</span>':''}</h3>
      <span class="tag">${s.cap_note||s.rent_psm_note||''}</span>
      <div class="hero"><div class="label">税引前キャッシュフロー（月）</div>
        <div class="num ${cls(r.cf)}">${yen(r.cf/12)}</div></div>
      <div class="kpi"><span class="k">年間売上</span><span class="v">${manFmt(r.revenue)}</span></div>
      ${nightsRow}
      <div class="kpi"><span class="k">NOI（運営純収益）</span><span class="v">${manFmt(r.noi)}</span></div>
      <div class="kpi"><span class="k">初期投資総額</span><span class="v">${manFmt(r.total)}</span></div>
      <div class="kpi"><span class="k">自己資金</span><span class="v">${manFmt(r.selfCap)}</span></div>
      <div class="kpi"><span class="k">年間返済</span><span class="v">${manFmt(r.debt)}</span></div>
      <div class="kpi"><span class="k">税引前CF（年）</span><span class="v big ${cls(r.cf)}">${manFmt(r.cf)}</span></div>
      <div class="kpi"><span class="k">表面利回り</span><span class="v">${pct(r.grossYield)}</span></div>
      <div class="kpi"><span class="k">実質利回り(FCR)</span><span class="v">${pct(r.fcr)}</span></div>
      <div class="kpi"><span class="k">自己資金配当率(CCR)</span><span class="v ${cls(r.ccr)}">${isFinite(r.ccr)?pct(r.ccr):'—'}</span></div>
      <div class="kpi"><span class="k">自己資金回収年数</span><span class="v">${isFinite(r.payback)?r.payback.toFixed(1)+'年':'回収不能'}</span></div>
      ${capWarn}
    </div>`;
  }).join('');

  // verdict
  const th=CFG.thresholds;
  let v='';
  if(win){
    const r=res[win], s=CFG.scenarios[win];
    const judge = r.ccr*100>=th.target_ccr_pct ? `<span class="em">化ける水準（CCR≥${th.target_ccr_pct}%）</span>` :
                  r.ccr*100>=th.min_acceptable_ccr_pct ? `<span class="em" style="color:var(--amber)">許容圏（CCR≥${th.min_acceptable_ccr_pct}%）だが妙味は薄い</span>` :
                  `<span class="em" style="color:var(--red-light)">この価格では物足りない</span>`;
    v=`<div class="line">取得価格 <b>${manFmt(c.price)}</b>・金利 <b>${(c.rate*100).toFixed(2)}%</b> なら、最も効率が良いのは <span class="em">${s.label}</span>。</div>
       <div class="line">月CF <b class="${cls(r.cf)}">${yen(r.cf/12)}</b> ／ CCR <b class="${cls(r.ccr)}">${pct(r.ccr)}</b> ／ 回収 <b>${isFinite(r.payback)?r.payback.toFixed(1)+'年':'—'}</b> → ${judge}</div>`;
  } else {
    v=`<div class="line"><span class="em" style="color:var(--red-light)">現在の前提では全シナリオが月CFマイナス。</span>取得価格を下げるか、自己資金比率・稼働率の前提を見直す必要がある。</div>`;
  }
  verdict.innerHTML = v;

  // break-even table
  const tbody = beTable.querySelector('tbody');
  tbody.innerHTML = keys.map(k=>{
    const s=CFG.scenarios[k], r=res[k];
    const be = breakevenPrice(k,c,th.target_ccr_pct/100);
    const delta = be.target - c.price; // 化ける価格 vs 現価格
    const dcls = be.target>=c.price ? 'delta-up':'delta-dn';
    const dtxt = be.target>=c.price ? `今の価格でOK（+${manFmt(be.target-c.price).replace('¥','')}余裕）` : `あと ${manFmt(c.price-be.target).replace('¥','')} 下げたい`;
    return `<tr><td>${s.label}</td>
      <td class="mono ${cls(r.cf)}">${yen(r.cf/12)}</td>
      <td class="mono">${be.cf0>0?manFmt(be.cf0):'—'}</td>
      <td class="mono">${be.target>0?manFmt(be.target):'—'}</td>
      <td class="mono ${dcls}">${dtxt}</td></tr>`;
  }).join('');
  beNote.innerHTML = `「CF黒字化する取得価格」=この価格以下なら月CFがプラスに転じる線。「CCR10%達成価格」=自己資金に対し年10%回る＝<b>化ける</b>と判断する線（閾値はYAMLで調整可）。改装726万・諸費用${(CFG.acquisition.acquisition_cost_rate*100)}%・現在の金利/稼働率を織り込み済み。`;

  renderYakuin(c, res);
}

// --- static sections (rendered once): licensing, scheme, research ---
function renderStatic(){
  const L = CFG.licensing, R = CFG.research;
  if(L){
    const sc = L.schemes_compared;
    const row = (lbl,a,b,c)=>`<tr><td>${lbl}</td><td>${a}</td><td>${b}</td><td>${c}</td></tr>`;
    schemeTable.querySelector('tbody').innerHTML =
      row('営業日数上限', sc.minpaku_law.day_cap+'日', '上限なし(365日)', sc.special_zone.available_fukuoka?'導入':'<b style="color:var(--red-light)">福岡市は非導入</b>')
    + row('許可/届出', sc.minpaku_law.permit, sc.ryokan_simple.permit, '—')
    + row('フロント', sc.minpaku_law.front_desk, sc.ryokan_simple.front_desk, '—')
    + row('消防要件', sc.minpaku_law.fire_req, sc.ryokan_simple.fire_req, '—')
    + row('初期コスト感', sc.minpaku_law.init_cost_yen, sc.ryokan_simple.init_cost_yen, '—')
    + row('主リスク', sc.minpaku_law.risk, sc.ryokan_simple.risk, '—');
    schemeConcl.innerHTML = `<b>結論：</b>福岡市は特区民泊が使えず、純民泊は新法180日上限で収益が頭打ち。中洲のように通年需要が強い立地は<b>旅館業（簡易宿所・日数無制限）が本命</b>。ただし許可・消防・管理規約のハードルを越えられる前提。`;
    blockers.innerHTML = '<b>購入前の致命的チェック：</b><br>' + L.blockers.map(b=>`・<b>${b.title}</b>：${b.detail}`).join('<br>');
    // costs
    const initRef = Object.entries(L.init_cost_breakdown_ref||{}).map(([k,v])=>`<div class="kpi"><span class="k">${k}</span><span class="v">¥${v}</span></div>`).join('');
    licCost.innerHTML = `
      <div class="card"><h3 style="font-size:15px;margin-bottom:10px">初期コスト（フルレンジ・参考）</h3>${initRef}
        <div class="note">※太字の一部はF-areaセットアップ190万に既に含む。重複を避けた<b>追加分だけで約${manFmt(L.init_cost_extra_yen)}</b>を試算に算入（トグルON時）。</div></div>
      <div class="card"><h3 style="font-size:15px;margin-bottom:10px">年間ランニング（旅館業特有の追加）</h3>
        <div class="kpi"><span class="k">消防設備 法定点検</span><span class="v">¥36,000〜48,000</span></div>
        <div class="kpi"><span class="k">許可更新(3年/16,500)按分</span><span class="v">¥5,500</span></div>
        <div class="kpi"><span class="k">衛生備品ほか</span><span class="v">¥30,000〜50,000</span></div>
        <div class="note">合計 約${manFmt(L.running_cost_extra_yen)}/年を算入。光熱・清掃・宿泊税・OTAは各シナリオの変動経費率に既に算入済（二重計上しない）。</div></div>
      <div class="card"><h3 style="font-size:15px;margin-bottom:10px">許可の要件（簡易宿所）</h3>
        ${L.requirements_ryokan.map(r=>`<div style="font-size:12px;color:var(--text-secondary);padding:3px 0;border-bottom:1px dashed var(--border)">・${r}</div>`).join('')}</div>`;
    licReq.innerHTML = `推奨スキーム：<b>${sc[L.recommended_scheme].label}</b>。出典：` + L.sources.map(s=>{const m=s.match(/(https?:\/\/\S+)/);const u=m?m[1]:'';const t=s.replace(u,'').trim();return u?`<a href="${u}" target="_blank" style="color:var(--blue)">${t}</a>`:t;}).join(' ／ ');
  }
  if(R){
    occBasis.innerHTML = `<b>「年183日」の正体：</b>${R.occupancy_basis.replace(/\n/g,' ')}`;
    // zero-base scenarios from presets research_*
    const P = CFG.presets;
    const rows = [['research_cons','保守'],['research_base','標準']].map(([k,jp])=>{
      const p=P[k]; const occ=p.ryokan.occupancy, adr=p.ryokan.adr_yen, nights=365*occ, rev=adr*nights;
      return `<tr><td>${jp}（旅館業ベース）</td><td class="mono">${(occ*100).toFixed(0)}%</td><td class="mono">${yen(adr)}</td><td class="mono">${Math.round(nights)}泊</td><td class="mono">${manFmt(rev)}</td></tr>`;
    }).join('');
    // vendor row for contrast
    const v=P.vendor; const vnights=365*v.ryokan.occupancy, vrev=v.ryokan.adr_yen*vnights;
    const vrow=`<tr><td>参考：業者想定</td><td class="mono">${(v.ryokan.occupancy*100).toFixed(0)}%</td><td class="mono">${yen(v.ryokan.adr_yen)}</td><td class="mono">${Math.round(vnights)}泊</td><td class="mono">${manFmt(vrev)}</td></tr>`;
    occTable.querySelector('tbody').innerHTML = rows + vrow;
    mktFacts.innerHTML = '<b>市場の事実：</b><br>' + R.market_facts.map(f=>'・'+f).join('<br>') + `<br><span style="color:var(--amber)">${R.adr_caveat.replace(/\n/g,' ')}</span>`;
    sources.innerHTML = '稼働・ADR出典：' + R.sources.map(s=>{const m=s.match(/(https?:\/\/\S+)/);const u=m?m[1]:'';const t=s.replace(u,'').trim();return u?`<a href="${u}" target="_blank" style="color:var(--blue)">${t}</a>`:t;}).join(' ／ ');
  }
}

function applyPreset(key){
  const p = CFG.presets[key]; if(!p) return;
  occM.value=p.minpaku.occupancy*100; adrM.value=p.minpaku.adr_yen;
  occR.value=p.ryokan.occupancy*100; adrR.value=p.ryokan.adr_yen;
  render();
}

function renderYakuin(c, res){
  const v=+yk_value.value, l=+yk_loan.value, rent=+yk_rent.value, hold=+yk_hold.value;
  if(!(v||l||rent||hold)){
    ykOut.innerHTML = '数値を入れると、薬院を「賃貸」or「売却」した場合のしんばし投資との合算が出る（プレースホルダー）。';
    return;
  }
  const sellNet = v - l;                       // 売却純手取り（概算・税/手数料前）
  const rentNetMonth = rent - hold;            // 賃貸の月ネット
  const bestShin = (()=>{ // しんばしの月CF最大シナリオ
    let m=-Infinity; ['rental','minpaku','ryokan'].forEach(k=>{ if(res[k].cf/12>m) m=res[k].cf/12; }); return m;
  })();
  ykOut.innerHTML = `
    <b>売却して移動</b>：純手取り 約 ${manFmt(sellNet)}（税・諸費用前）。これをしんばしの頭金/繰上返済に充てると借入が圧縮され月CFが改善。<br>
    <b>賃貸に出して移動</b>：薬院の月ネット ${yen(rentNetMonth)} ＋ しんばし最良シナリオ月CF ${yen(bestShin)} = 合算 <b class="${rentNetMonth+bestShin>0?'':''}">${yen(rentNetMonth+bestShin)}/月</b>。<br>
    <span style="color:var(--text-muted)">※売却の税（譲渡所得）・賃貸の空室は未織り込み。正確化は数値投入後に別途。</span>`;
}

function init(){
  const d=CFG.deal, acq=CFG.acquisition, fin=CFG.financing, s=CFG.scenarios;
  dealName.textContent = d.name + ' 投資判断シミュレーター';
  dealAddr.textContent = d.address + '　|　' + d.layout;
  dealMeta.innerHTML = [
    `面積 <b>${d.area_sqm}㎡</b>`, `最大 <b>${d.max_guests}名</b>`,
    `改装 <b>${manFmt(acq.renovation_yen)}</b>`, `民泊セットアップ <b>${manFmt(acq.minpaku_setup_yen)}</b>`,
    `<span style="color:var(--amber)">${d.area_note}</span>`
  ].join('');
  // init control values
  price.value=acq.asking_price_yen; rate.value=(fin.loan_rate_annual*100).toFixed(2);
  years.value=fin.loan_years; down.value=(fin.down_payment_ratio*100);
  occM.value=(s.minpaku.occupancy*100); occR.value=(s.ryokan.occupancy*100);
  adrM.value=s.minpaku.adr_yen; adrR.value=s.ryokan.adr_yen;
  rent.value=s.rental.monthly_rent_yen;
  // preset buttons
  if(CFG.presets){
    presetBtns.innerHTML = Object.keys(CFG.presets).map(k=>
      `<button data-k="${k}" style="background:var(--surface2);border:1px solid var(--border-light);color:var(--text);padding:6px 12px;border-radius:8px;font-size:12px;cursor:pointer">${CFG.presets[k].label}</button>`).join('');
    presetBtns.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>applyPreset(b.dataset.k)));
  }
  ['input','change'].forEach(ev=>{
    [price,rate,years,down,occM,occR,adrM,adrR,rent,capToggle,renoRental,licToggle,yk_value,yk_loan,yk_rent,yk_hold]
      .forEach(el=>el.addEventListener(ev, render));
  });
  renderStatic();
  footer.innerHTML = `出典: ${d.source_docs.join(' / ')}。<br>前提: 取得諸費用 ${(acq.acquisition_cost_rate*100)}% / 元利均等 / NOI=売上−運営経費（返済前）。自己資金=総事業費×自己資金比率、借入=残り。賃貸の家賃・薬院の数値は推計/未確定。投資判断は最終的に実地確認と税理士・金融機関の確認を要する。`;
  render();
}
init();
</script>
</body>
</html>
"""


def main(argv: list[str]) -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)
    if len(argv) > 1:
        paths = [Path(argv[1])]
    else:
        paths = sorted(DEALS_DIR.glob("*.yaml"))
    if not paths:
        print("no deal yaml found in deals/", file=sys.stderr)
        return 1
    out_files = []
    for p in paths:
        cfg = load_deal(p)
        html = build_html(cfg)
        out = OUTPUT_DIR / f"deal-{cfg['deal']['id']}.html"
        out.write_text(html, encoding="utf-8")
        out_files.append(out)
        print(f"generated: {out.resolve()}")
    # open the first one
    subprocess.run(["open", str(out_files[0].resolve())])
    print(f"フォルダを表示した: {out_files[0].resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
