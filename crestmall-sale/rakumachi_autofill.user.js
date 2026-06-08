// ==UserScript==
// @name         クレストモール 楽待 自動入力
// @namespace    iuma.crestmall
// @version      2.0
// @description  楽待の売却査定フォームをクレストモールの情報で自動入力（9ステップ：各画面で入力欄・プルダウン・ラジオを一括入力）
// @match        https://www.rakumachi.jp/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==
(function () {
  'use strict';

  // ===== クレストモールの掲載データ（SSoT）=====
  const D = {
    prefValue: '4',          // 宮城県（楽待 select value）
    cityMatch: '太白',        // 仙台市太白区（option text 部分一致）
    dimensionValue: '1002',  // 1棟アパート（楽待 select value）
    name: 'クレストモール',
    address: '宮城県仙台市太白区茂ケ崎3-3-22',
    addressBanchi: '茂ケ崎3-3-22',
    yield: '10.0',
    price_man: '2950',       // 売出価格（万円）
    area: '198.74',
    builtYear: '1985',
    builtYearWareki: '昭和60',
    units: '8',
    layout: '1K',
    genkyo: '満室',
    reason: '資産の組み替え',
    rentMonthly: '246000',
    rentAnnual: '2952000',
    structure: '木造',
    station: '長町一丁目',
    company: 'iUMAプロパティマネジメント合同会社',
    person: '手嶋 耕一',
    tel: '07086614173',
    email: 'yma.tz.28@gmail.com',
    comment:
      '【全8戸満室稼働中／表面利回り10.0%・売出2,950万円の一棟アパート】\n\n' +
      '仙台市太白区茂ケ崎の木造一棟アパート（全8戸／1K）です。地下鉄南北線「長町一丁目」駅が徒歩圏、再開発の進む人気サブ都心「長町」エリアに立地します。\n\n' +
      '2026年現在、全8戸満室で稼働中。年間賃料収入 約295万円、運営費控除後の純収益（NOI）は約281万円です。robot home仙台支店が管理しており、引継ぎ後すぐに収益化いただけます。\n\n' +
      '土地・建物を一括所有（法人名義）。抵当権は日本政策金融公庫のみで権利関係はシンプル、決済時に完済・抹消し所有権をクリアにして引渡。資料（レントロール・送金明細・固定資産税通知・火災保険証券）完備。\n\n' +
      '築年（1985年）のため現金または土地値評価でのご購入が中心。高利回り×インカム黒字を狙う投資家様に適した商品です。'
  };

  // ===== React/jQuery 両対応の値セット =====
  function setNative(el, val) {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) desc.set.call(el, val); else el.value = val;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function setSelectVal(sel, val) { sel.value = val; sel.dispatchEvent(new Event('change', { bubbles: true })); return sel.value === val; }
  function setSelectText(sel, sub) {
    const o = Array.from(sel.options).find(o => o.text.indexOf(sub) >= 0);
    if (o) { sel.value = o.value; sel.dispatchEvent(new Event('change', { bubbles: true })); return o.text; }
    return null;
  }
  function visible(el) { return el && el.offsetParent !== null; }

  // ===== 査定トップ（都道府県 / 市区郡 / 物件種別）=====
  function fillTop() {
    const forms = Array.from(document.querySelectorAll('form.assessment_form'));
    const form = forms.find(visible) || forms[0];
    if (!form) return false;
    const pref = form.querySelector('.prefecture_id');
    const city = form.querySelector('.city_id');
    const dim = form.querySelector('.dimension_type');
    if (pref) setSelectVal(pref, D.prefValue);
    if (dim) setSelectVal(dim, D.dimensionValue);
    // 市区郡は都道府県変更後に AJAX で読み込まれる → ポーリングして選択
    let tries = 0;
    const timer = setInterval(() => {
      tries++;
      if (city && city.options.length > 1) {
        const picked = setSelectText(city, D.cityMatch);
        clearInterval(timer);
        toast('トップ3項目を入力（市区郡=' + (picked || '手動で太白区を選択') + '）。「一括査定スタート」を押してください');
      } else if (tries > 25) {
        clearInterval(timer);
        toast('都道府県・物件種別は入力済。市区郡だけ手動で「太白区」を選んでください');
      }
    }, 300);
    return true;
  }

  // ===== 詳細ページ（ラベル推定・ベストエフォート）=====
  function metaText(el) {
    let s = [el.name, el.id, el.placeholder, el.getAttribute('aria-label')].filter(Boolean).join(' ');
    if (el.labels) for (const l of el.labels) s += ' ' + l.textContent;
    const cell = el.closest('td,li,dd,div,p,label,tr');
    if (cell) { const prev = cell.previousElementSibling; if (prev) s += ' ' + prev.textContent; }
    return s;
  }
  // 入力欄(text/number)用：キーワード→値
  const RULES = [
    { k: ['物件名', '名称', '建物名'], v: D.name },
    { k: ['町村番地', '番地', '丁目'], v: D.addressBanchi || '茂ケ崎3-3-22' },
    { k: ['住所', '所在地'], v: D.address },
    { k: ['表面', '利回'], v: D.yield },
    { k: ['価格', '売却', '希望額'], v: D.price_man },
    { k: ['延床', '建物面積'], v: D.area },
    { k: ['面積', '専有', '㎡'], v: D.area },
    { k: ['築年', '建築'], v: D.builtYear },
    { k: ['戸数', '部屋数', '室数'], v: D.units },
    { k: ['年間', '満室時', '想定年'], v: D.rentAnnual },
    { k: ['家賃', '賃料', '月額'], v: D.rentMonthly },
    { k: ['駅', '最寄'], v: D.station },
    { k: ['会社', '法人名', '屋号'], v: D.company },
    { k: ['氏名', '名前', '担当', 'お名前'], v: D.person },
    { k: ['電話', 'tel', '携帯'], v: D.tel },
    { k: ['mail', 'メール'], v: D.email }
  ];
  // プルダウン用：キーワード→option文字列候補（先に一致したものを選ぶ）。exact=数字一致
  const SELECT_RULES = [
    { k: ['構造'], texts: ['木造'] },
    { k: ['築年', '建築'], texts: [D.builtYear, D.builtYearWareki] },
    { k: ['間取'], texts: ['1K'] },
    { k: ['戸数', '室数'], exact: D.units },
    { k: ['現況', '入居', '稼働'], texts: ['満室'] },
    { k: ['理由'], texts: ['資産', '組み替え', 'その他'] },
    { k: ['時期', 'いつ'], texts: ['問わない', '未定', '3'] },
    { k: ['名義', '所有'], texts: ['法人'] }
  ];
  // ラジオ/チェック：自身のラベル/値にこの語を含むものをON
  const RADIO_TARGETS = ['満室', '法人'];

  function labelOf(el) {
    let s = '';
    if (el.labels) for (const l of el.labels) s += ' ' + l.textContent;
    const wrap = el.closest('label'); if (wrap) s += ' ' + wrap.textContent;
    const sib = el.nextElementSibling; if (sib && sib.tagName === 'LABEL') s += ' ' + sib.textContent;
    return s;
  }
  function pickOption(sel, texts) {
    for (const t of texts) {
      if (!t) continue;
      const o = Array.from(sel.options).find(o => o.text.indexOf(t) >= 0);
      if (o) { sel.value = o.value; sel.dispatchEvent(new Event('change', { bubbles: true })); return true; }
    }
    return false;
  }
  function pickExact(sel, num) {
    const o = Array.from(sel.options).find(o => o.text.replace(/[^0-9]/g, '') === String(num));
    if (o) { sel.value = o.value; sel.dispatchEvent(new Event('change', { bubbles: true })); return true; }
    return false;
  }

  function fillDetail() {
    let n = 0, commentDone = false;
    // 入力欄 / コメント
    document.querySelectorAll('input, textarea').forEach(el => {
      const type = (el.type || '').toLowerCase();
      if (!visible(el)) return;
      if (type === 'radio' || type === 'checkbox') {
        const t = (el.value + ' ' + labelOf(el));
        if (RADIO_TARGETS.some(x => t.indexOf(x) >= 0) && !el.checked) { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); n++; }
        return;
      }
      if (['hidden', 'submit', 'button', 'file', 'password'].indexOf(type) >= 0) return;
      const meta = metaText(el);
      if (el.tagName === 'TEXTAREA' && /備考|要望|コメント|メッセージ|その他|質問|相談|自由|アピール/.test(meta)) {
        if (!el.value) { setNative(el, D.comment); n++; } commentDone = true; return;
      }
      const m = meta.toLowerCase();
      for (const r of RULES) {
        if (r.k.some(key => m.indexOf(key.toLowerCase()) >= 0)) { if (!el.value) { setNative(el, r.v); n++; } break; }
      }
    });
    // プルダウン（トップ3select=prefecture/city/dimensionは除外）
    document.querySelectorAll('select').forEach(sel => {
      if (!visible(sel)) return;
      if (sel.classList.contains('prefecture_id') || sel.classList.contains('city_id') || sel.classList.contains('dimension_type')) return;
      if (sel.value) return; // 既に選択済みは触らない
      const m = metaText(sel);
      for (const r of SELECT_RULES) {
        if (r.k.some(k => m.indexOf(k) >= 0)) {
          const ok = r.exact ? pickExact(sel, r.exact) : pickOption(sel, r.texts);
          if (ok) n++;
          break;
        }
      }
    });
    if (!commentDone) {
      const tas = Array.from(document.querySelectorAll('textarea')).filter(visible).sort((a, b) => b.offsetHeight - a.offsetHeight);
      if (tas.length && !tas[0].value) { setNative(tas[0], D.comment); }
    }
    toast(n + '項目を入力。次へ進む前に画面を確認してください');
  }

  function run() {
    if (document.querySelector('form.assessment_form')) fillTop(); else fillDetail();
  }
  function copyComment() {
    if (navigator.clipboard) navigator.clipboard.writeText(D.comment).then(() => toast('物件紹介コメントをコピーしました'));
  }

  // ===== UI（右下フローティングパネル）=====
  function toast(msg) {
    let t = document.getElementById('cm_toast');
    if (!t) {
      t = document.createElement('div'); t.id = 'cm_toast';
      t.style.cssText = 'position:fixed;left:50%;bottom:96px;transform:translateX(-50%);background:#16243b;color:#fff;padding:10px 16px;border-radius:8px;font-size:13px;z-index:2147483647;box-shadow:0 4px 16px rgba(0,0,0,.3);max-width:90vw;transition:opacity .3s';
      document.body.appendChild(t);
    }
    t.textContent = msg; t.style.opacity = '1'; clearTimeout(t._h); t._h = setTimeout(() => t.style.opacity = '0', 4500);
  }
  function mkBtn(label, fn, gold) {
    const b = document.createElement('button'); b.textContent = label;
    b.style.cssText = 'display:block;width:100%;margin:4px 0;padding:9px 12px;border:none;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;' + (gold ? 'background:#c9a84c;color:#1a1207' : 'background:#243a5b;color:#fff');
    b.onclick = fn; return b;
  }
  function panel() {
    if (document.getElementById('cm_panel')) return;
    const p = document.createElement('div'); p.id = 'cm_panel';
    p.style.cssText = 'position:fixed;right:16px;bottom:16px;width:236px;background:#0f1117;border:1px solid #2d3348;border-radius:12px;padding:12px;z-index:2147483647;box-shadow:0 8px 24px rgba(0,0,0,.4);font-family:sans-serif';
    const h = document.createElement('div'); h.textContent = '🏠 クレストモール 自動入力';
    h.style.cssText = 'color:#c9a84c;font-size:12px;font-weight:800;margin-bottom:8px'; p.appendChild(h);
    p.appendChild(mkBtn('このステップを自動入力', run, true));
    p.appendChild(mkBtn('📋 コメントをコピー', copyComment));
    const note = document.createElement('div'); note.textContent = '各ステップでこのボタン→「次へ」を繰り返す。入力欄・プルダウン・満室/法人も自動。送信前に確認。';
    note.style.cssText = 'color:#7c8293;font-size:10px;margin-top:6px;line-height:1.4'; p.appendChild(note);
    document.body.appendChild(p);
  }
  if (document.body) panel(); else window.addEventListener('DOMContentLoaded', panel);
})();
