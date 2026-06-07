(function () {
  function fire(el) { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }
  function setNative(el, val) { var p = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; var d = Object.getOwnPropertyDescriptor(p, 'value'); if (d && d.set) { d.set.call(el, val); } else { el.value = val; } fire(el); }
  function vis(el) { return el && el.offsetParent !== null; }
  function meta(el) { var s = [el.name, el.id, el.placeholder, el.getAttribute('aria-label')].filter(Boolean).join(' '); if (el.labels) { [].forEach.call(el.labels, function (l) { s += ' ' + l.textContent; }); } var c = el.closest('td,li,dd,div,p,label,tr'); if (c) { var pv = c.previousElementSibling; if (pv) s += ' ' + pv.textContent; } return s; }
  function lbl(el) { var s = ''; if (el.labels) { [].forEach.call(el.labels, function (l) { s += ' ' + l.textContent; }); } var w = el.closest('label'); if (w) s += ' ' + w.textContent; var nx = el.nextElementSibling; if (nx && nx.tagName === 'LABEL') s += ' ' + nx.textContent; return s; }
  var D = { name: 'クレストモール', banchi: '茂ケ崎3-3-22', addr: '宮城県仙台市太白区茂ケ崎3-3-22', price: '2950', yield: '10.0', area: '198.74', by: '1985', units: '8', rentM: '246000', rentY: '2952000', station: '長町一丁目', company: 'iUMAプロパティマネジメント合同会社', person: '手嶋 耕一', tel: '07086614173', email: 'yma.tz.28@gmail.com', comment: '【全8戸満室稼働中／表面利回り10.0%・売出2,950万円の一棟アパート】\n\n仙台市太白区茂ケ崎の木造一棟アパート（全8戸／1K）。地下鉄南北線「長町一丁目」駅徒歩圏。2026年現在 全8戸満室、年間賃料 約295万円、NOI 約281万円。robot home仙台支店が管理。土地建物一括所有（法人）、抵当権は公庫のみ・残債小。資料完備。築1985年のため現金／土地値評価の投資家様向け、表面10.0%。' };
  var TR = [['物件名|名称|建物名', D.name], ['町村番地|丁目', D.banchi], ['住所|所在地', D.addr], ['表面|利回', D.yield], ['希望額|価格', D.price], ['延床|建物面積', D.area], ['面積|専有|㎡', D.area], ['築年|建築', D.by], ['戸数|室数', D.units], ['年間|満室時|想定年', D.rentY], ['家賃|賃料|月額', D.rentM], ['駅|最寄', D.station], ['会社|法人名|屋号', D.company], ['氏名|名前|担当', D.person], ['電話|tel|携帯', D.tel], ['mail|メール', D.email]];
  var SR = [['構造', ['木造']], ['築年|建築', ['1985', '昭和60']], ['間取', ['1K']], ['現況|入居|稼働', ['満室']], ['理由', ['資産', '組み替え', 'その他']], ['時期|いつ', ['問わない', '未定', '3']], ['名義|所有', ['法人']]];
  var top = document.querySelector('form.assessment_form');
  if (top) {
    var pf = top.querySelector('.prefecture_id'), ci = top.querySelector('.city_id'), di = top.querySelector('.dimension_type');
    if (pf) { pf.value = '4'; fire(pf); }
    if (di) { di.value = '1002'; fire(di); }
    var k = 0, tm = setInterval(function () { k++; if (ci && ci.options.length > 1) { var o = [].slice.call(ci.options).filter(function (x) { return x.text.indexOf('太白') >= 0; })[0]; if (o) { ci.value = o.value; fire(ci); } clearInterval(tm); } else if (k > 25) { clearInterval(tm); } }, 300);
    if (navigator.clipboard) navigator.clipboard.writeText(D.comment);
    alert('宮城県・太白区・1棟アパートをセット、紹介コメントをコピーしました');
    return;
  }
  var n = 0;
  [].forEach.call(document.querySelectorAll('input,textarea'), function (el) {
    var ty = (el.type || '').toLowerCase();
    if (!vis(el)) return;
    if (ty === 'radio' || ty === 'checkbox') { var tt = el.value + ' ' + lbl(el); if ((tt.indexOf('満室') >= 0 || tt.indexOf('法人') >= 0) && !el.checked) { el.checked = true; fire(el); n++; } return; }
    if (['hidden', 'submit', 'button', 'file', 'password'].indexOf(ty) >= 0) return;
    var m = meta(el);
    if (el.tagName === 'TEXTAREA' && /備考|要望|希望|コメント|メッセージ|その他|質問|相談|自由|アピール|PR/.test(m)) { if (!el.value) { setNative(el, D.comment); n++; } return; }
    var ml = m.toLowerCase();
    TR.some(function (r) { if (new RegExp(r[0], 'i').test(ml)) { if (!el.value) { setNative(el, r[1]); n++; } return true; } return false; });
  });
  [].forEach.call(document.querySelectorAll('select'), function (sel) {
    if (!vis(sel)) return;
    var cn = sel.className || '';
    if (cn.indexOf('prefecture_id') >= 0 || cn.indexOf('city_id') >= 0 || cn.indexOf('dimension_type') >= 0) return;
    if (sel.value) return;
    var m = meta(sel);
    if (/戸数|室数/.test(m)) { var oo = [].slice.call(sel.options).filter(function (o) { return o.text.replace(/[^0-9]/g, '') === '8'; })[0]; if (oo) { sel.value = oo.value; fire(sel); n++; } return; }
    SR.some(function (r) { if (new RegExp(r[0]).test(m)) { r[1].some(function (t) { var o = [].slice.call(sel.options).filter(function (o) { return o.text.indexOf(t) >= 0; })[0]; if (o) { sel.value = o.value; fire(sel); n++; return true; } return false; }); return true; } return false; });
  });
  alert(n + '項目を入力しました。内容を確認して「次へ」を押してください。');
})();
