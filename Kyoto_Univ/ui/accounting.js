/* Memory-only accounting prototype built from a limited CSV snapshot. */
(() => {
  const seed = window.LifeAccountingData;
  const root = document.getElementById('accounting-view');
  if (!seed || !root) return;
  const transactions = structuredClone(seed.transactions);
  let tab = 'ホーム', book = 'BS', month = '2026-10', scale = 'month', selectedDay = seed.start, drawerOpen = false;
  const liabilities = new Set(['三井住友カード未払金', '楽天カード未払金']);
  const accounts = ['三井住友カード未払金', '楽天カード未払金', '三井住友銀行', '楽天銀行', 'PayPay残高', 'PayPayポイント', 'Suica', '大学生協電子マネー', '現金', '未確認口座'];
  const categories = ['未分類', '食費', '交通費', '日用雑貨', '娯楽費', '給与', 'その他'];
  const colors = ['#d7b66c', '#8fabc2', '#9b8bbd', '#80b49d', '#c98770', '#c9c3b4'];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const yen = value => `${value < 0 ? '−' : ''}¥${Math.abs(value).toLocaleString('ja-JP')}`;
  const signed = value => `${value >= 0 ? '+' : '−'}¥${Math.abs(value).toLocaleString('ja-JP')}`;
  const monthLabel = () => `${month.slice(0,4)}年${Number(month.slice(5))}月`;
  const inMonth = row => row.date.startsWith(month);
  const current = () => transactions.filter(inMonth);
  const stats = rows => ({income: rows.filter(r => r.kind === 'income').reduce((s,r) => s+r.amount,0), expense: rows.filter(r => r.kind === 'expense').reduce((s,r) => s+r.amount,0)});
  const sourceText = refs => refs.map(ref => `${ref.file}：${ref.line}行目`).join(' / ');
  const button = (label, action, value = '', active = false) => `<button type="button" data-ac-action="${action}" data-value="${esc(value)}" ${active ? 'aria-pressed="true"' : ''}>${label}</button>`;
  const empty = text => `<p class="ac-empty">${text}</p>`;
  const within = date => date >= seed.start && date <= seed.end;
  const journal = row => {
    if (row.kind === 'pending') return [];
    if (row.kind === 'transfer') return [{debit:row.to,credit:row.account,amount:row.amount}];
    if (row.kind === 'income') return [{debit:row.account,credit:row.category,amount:row.amount}];
    const parts = row.splits.length ? row.splits : [{account:row.account,amount:row.amount}];
    return parts.map(part => row.amount < 0 ? {debit:part.account,credit:row.category,amount:-part.amount} : {debit:row.category,credit:part.account,amount:part.amount});
  };
  const journalTable = rows => `<div class="ac-scroll"><table class="ac-table"><thead><tr><th>日付</th><th>借方</th><th>貸方</th><th class="ac-number">金額</th><th>状態</th></tr></thead><tbody>${rows.flatMap(row => journal(row).map(line => `<tr><td>${esc(row.date)}</td><td>${esc(line.debit)}</td><td>${esc(line.credit)}</td><td class="ac-number">${yen(line.amount)}</td><td>${esc(row.status)}</td></tr>`)).join('')}</tbody></table></div>`;
  const rowList = rows => !rows.length ? empty('この範囲に収録された取引はありません。') : `<div class="ac-scroll"><table class="ac-table"><thead><tr><th>日付 / 種類</th><th>内容 / 口座</th><th>カテゴリ</th><th class="ac-number">金額</th><th>確認</th><th></th></tr></thead><tbody>${rows.map(row => `<tr><td>${esc(row.date)}<small>${{expense:'支出',income:'収入',transfer:'振替',pending:'用途未確認'}[row.kind]}</small></td><td><span>${esc(row.memo)}</span><small>${esc(row.account)}${row.to ? ` → ${esc(row.to)}` : ''}</small></td><td>${esc(row.category)}</td><td class="ac-number ${row.kind === 'income' ? 'ac-positive' : ''}">${row.kind === 'income' || row.kind === 'pending' && row.direction === 'in' ? '+' : row.kind === 'expense' ? (row.amount < 0 ? '+' : '−') : row.kind === 'pending' ? '−' : ''}${yen(row.amount).replace('−','')}${row.amount < 0 ? '<small>返金 / 支出の減額</small>' : ''}</td><td><span class="ac-badge ${row.status === '未確認' ? 'ac-warning' : ''}">${esc(row.status)}</span></td><td>${button('詳細・編集','edit',row.id)}</td></tr>`).join('')}</tbody></table></div>`;
  const evidence = () => `<details class="ac-evidence"><summary>Zaimの内訳・未対応資料（${seed.evidence.filter(inMonth).length}件）</summary><p class="ac-muted">支払元・決済対応は未確認のため集計対象外。負数は割引。</p><div class="ac-scroll"><table class="ac-table"><thead><tr><th>日付</th><th>店 / 品目</th><th>分類</th><th class="ac-number">金額</th><th>原本</th></tr></thead><tbody>${seed.evidence.filter(inMonth).map(r => `<tr><td>${r.date}</td><td>${esc(r.store)}<small>${esc(r.item)}</small></td><td>${esc(r.category)} / ${esc(r.detail)}</td><td class="ac-number">${yen(r.amount)}</td><td>${esc(r.source.file)}<small>${r.source.line}行目</small></td></tr>`).join('')}</tbody></table></div></details>`;
  function home() {
    const rows = current(), totals = stats(rows);
    const slice = transactions.filter(r => scale === 'month' ? inMonth(r) : r.date.startsWith(month.slice(0,4)));
    const expenses = {};
    slice.filter(r => r.kind === 'expense').forEach(r => expenses[r.category] = (expenses[r.category] || 0) + r.amount);
    const groups = Object.entries(expenses).filter(([,v]) => v > 0).sort((a,b) => b[1]-a[1]);
    const total = groups.reduce((sum,[,v]) => sum+v,0);
    let cursor = 0;
    const gradient = groups.map(([,value],i) => { const start = cursor; cursor += value / total * 100; return `${colors[i % colors.length]} ${start}% ${cursor}%`; }).join(',');
    const pendingOut = rows.filter(r => r.kind === 'pending' && !r.excludeFromBalances && r.direction === 'out').reduce((sum,r) => sum+r.amount,0);
    const pendingIn = rows.filter(r => r.kind === 'pending' && !r.excludeFromBalances && r.direction === 'in').reduce((sum,r) => sum+r.amount,0);
    const covered = rows.length > 0 || month === seed.start.slice(0,7) || month === seed.end.slice(0,7);
    return `<div class="ac-home-layout"><div class="ac-metrics">${[['収入',totals.income,'ac-positive'],['支出',totals.expense,''],['収支差額',totals.income-totals.expense,'']].map(([title,value,cls]) => `<div class="ac-metric"><p>${title}</p><strong class="${cls}">${covered ? yen(value) : '—'}</strong></div>`).join('')}</div><div class="ac-pending-note">集計保留 <span>出金 ${covered ? yen(pendingOut) : '—'}</span><span>入金 ${covered ? yen(pendingIn) : '—'}</span></div><section class="ac-panel ac-home-chart"><div class="ac-panel-head"><h2>カテゴリ別支出 <small>${scale === 'month' ? monthLabel() : month.slice(0,4)+'年'}</small></h2><div class="ac-segment">${button('月','scale','month',scale === 'month')}${button('年','scale','year',scale === 'year')}</div></div>${total > 0 ? `<div class="ac-chart-layout"><div class="ac-donut" style="background:conic-gradient(${gradient})" role="img" aria-label="カテゴリ別支出。${groups.map(([name,value]) => `${esc(name)} ${yen(value)}`).join('、')}"><div><small>支出合計</small><strong>${yen(total)}</strong></div></div><div class="ac-categories">${groups.map(([name,value],i) => `<div><span><i style="background:${colors[i % colors.length]}"></i>${esc(name)}</span><strong>${yen(value)}</strong><small>${(value/total*100).toFixed(1)}%</small></div>`).join('')}</div></div>` : empty('支出データは未収録です。')}</section><div class="ac-source-disclosure">${evidence()}</div></div>`;
  }
  function dayDrawer() {
    const rows = transactions.filter(r => r.date === selectedDay);
    return `<aside class="ac-drawer" role="region" aria-labelledby="ac-drawer-title"><header><div><small>日別明細</small><h2 id="ac-drawer-title">${esc(selectedDay)}</h2></div>${button('×','close-drawer')}</header><div class="ac-drawer-body">${!within(selectedDay) ? '<p class="ac-muted">未収録の日付です。</p>' : ''}${rows.length ? rows.map(r => `<article class="ac-drawer-row"><div><span class="ac-badge">${{expense:'支出',income:'収入',transfer:'振替',pending:'用途未確認'}[r.kind]}</span><strong>${r.kind === 'expense' ? signed(-r.amount) : r.kind === 'pending' && !r.excludeFromBalances && r.direction === 'out' ? signed(-r.amount) : r.kind === 'transfer' ? yen(r.amount) : signed(r.amount)}</strong></div><p>${esc(r.memo)}</p><small>${esc(r.account)}${r.to ? ` → ${esc(r.to)}` : ''} / ${esc(r.category)}</small><footer><span class="ac-muted">${esc(r.status)}</span>${button('詳細・編集','edit',r.id)}</footer></article>`).join('') : empty('取引はありません。')}</div><footer>${button('＋ この日に追加','new',selectedDay)}</footer></aside>`;
  }
  function calendar() {
    const [year,m] = month.split('-').map(Number), count = new Date(year,m,0).getDate(), offset = new Date(year,m-1,1).getDay();
    const weeks = Math.ceil((offset+count)/7);
    const cells = Array(offset).fill('<div class="ac-day ac-blank"></div>');
    for (let day=1;day<=count;day++) {
      const date = `${month}-${String(day).padStart(2,'0')}`, rows = transactions.filter(r => r.date === date), totals = stats(rows), weekday = (offset+day-1)%7;
      const available = within(date) || rows.length;
      cells.push(`<button type="button" class="ac-day ${weekday === 0 ? 'ac-sunday' : weekday === 6 ? 'ac-saturday' : ''} ${date === selectedDay ? 'ac-selected' : ''} ${available ? '' : 'ac-outside'}" data-ac-action="day" data-value="${date}" aria-label="${date}、${available ? `${rows.length}件` : '未収録'}" aria-expanded="${drawerOpen && date === selectedDay}"><span>${day}</span>${available ? `<small class="ac-positive">+${yen(totals.income)}</small><small>−${yen(totals.expense)}</small>${rows.some(r => r.kind === 'transfer') ? '<em>振替</em>' : ''}${rows.some(r => r.kind === 'pending') ? '<em>保留あり</em>' : ''}` : '<small>—</small>'}</button>`);
    }
    while (cells.length < weeks*7) cells.push('<div class="ac-day ac-blank"></div>');
    return `<div class="ac-calendar-stage"><div class="ac-calendar"><div class="ac-week">${['日','月','火','水','木','金','土'].map((d,i) => `<span class="${i === 0 ? 'ac-sunday' : i === 6 ? 'ac-saturday' : ''}">${d}</span>`).join('')}</div><div class="ac-days" style="--weeks:${weeks}">${cells.join('')}</div></div>${drawerOpen ? dayDrawer() : '<aside class="ac-detail-placeholder"><span>日付を選択すると<br>明細を表示します。</span></aside>'}</div>`;
  }
  function ledger() {
    const rows = current(), totals = stats(rows), hasData = rows.length > 0;
    let content;
    if (book === '取引一覧') content = `<section class="ac-panel ac-list-panel">${rowList(rows)}<div class="ac-source-disclosure">${evidence()}</div></section>`;
    if (book === '仕訳') content = `<section class="ac-panel ac-list-panel"><div class="ac-panel-head"><h2>仕訳帳</h2><small class="ac-muted">用途未確認は保留</small></div>${journalTable(rows)}</section>`;
    if (book === 'PL') {
      const income = {}, expense = {};
      rows.forEach(r => { const group = r.kind === 'income' ? income : r.kind === 'expense' ? expense : null; if (group) group[r.category] = (group[r.category] || 0)+r.amount; });
      const amount = value => hasData ? yen(value) : '未収録';
      const line = (name,value,cls='') => `<div class="ac-pl-line ${cls}"><span>${esc(name)}</span><strong>${amount(value)}</strong></div>`;
      const difference = totals.income-totals.expense;
      const high = Math.max(totals.income,difference,0), low = Math.min(difference,0), range = high-low || 1;
      const y = value => 54+(high-value)/range*210;
      const zero = y(0), incomeTop = y(totals.income), differenceY = y(difference);
      const rect = (x,from,to,cls,minHeight=0) => {
        const top = Math.min(y(from),y(to)), actual = Math.abs(y(from)-y(to)), height = Math.max(actual,minHeight);
        return `<rect x="${x}" y="${top}" width="74" height="${height}" rx="3" class="${cls}"><title>${amount(Math.abs(to-from))}${actual < minHeight ? '（視認性のため最小表示高）' : ''}</title></rect>`;
      };
      const waterfall = `<svg class="ac-waterfall" viewBox="0 0 400 330" role="img" aria-label="収入${amount(totals.income)}から費用${amount(totals.expense)}を差し引き、収支差額${amount(difference)}"><line class="ac-waterfall-zero" x1="16" x2="387" y1="${zero}" y2="${zero}"/><text x="15" y="${zero-8}" class="ac-waterfall-zero-label">0</text><line class="ac-waterfall-connector" x1="111" x2="163" y1="${incomeTop}" y2="${incomeTop}"/><line class="ac-waterfall-connector" x1="237" x2="289" y1="${differenceY}" y2="${differenceY}"/>${hasData ? rect(37,0,totals.income,'ac-waterfall-income',totals.income ? 3 : 0) : ''}${difference > 0 ? rect(163,0,difference,'ac-waterfall-remainder') : ''}${hasData ? rect(163,totals.income,difference,'ac-waterfall-expense',totals.expense ? 5 : 0) : ''}${hasData ? rect(289,0,difference,difference < 0 ? 'ac-waterfall-deficit' : 'ac-waterfall-result',difference ? 3 : 0) : ''}<text x="74" y="${Math.max(24,incomeTop-14)}" class="ac-waterfall-value ac-waterfall-income-text">${amount(totals.income)}</text><text x="200" y="${Math.max(24,Math.min(incomeTop,differenceY)-14)}" class="ac-waterfall-value ac-waterfall-expense-text">${hasData ? signed(-totals.expense) : '未収録'}</text><text x="326" y="${difference < 0 ? Math.min(290,differenceY+21) : Math.max(24,differenceY-14)}" class="ac-waterfall-value ac-waterfall-result-text">${amount(difference)}</text><text x="74" y="316" class="ac-waterfall-label">収入</text><text x="200" y="316" class="ac-waterfall-label">費用控除</text><text x="326" y="316" class="ac-waterfall-label">収支差額</text></svg>`;
      content = `<div class="ac-financial-grid"><section class="ac-panel ac-financial-card"><div class="ac-panel-head"><h2>収支の流れ</h2><small class="ac-muted">収録分</small></div><div class="ac-pl-flow">${waterfall}</div></section><section class="ac-panel ac-financial-card"><div class="ac-panel-head"><h2>損益計算書</h2><small class="ac-muted">${monthLabel()}</small></div><div class="ac-financial-scroll"><div class="ac-pl-details">${line('収入合計',totals.income,'ac-pl-section ac-income-tone')}${Object.entries(income).map(([name,value]) => line(name,value)).join('')}${line('費用合計',totals.expense,'ac-pl-section ac-expense-tone')}${Object.entries(expense).map(([name,value]) => line(name,value)).join('')}${line('収支差額',totals.income-totals.expense,'ac-pl-total')}</div></div><small class="ac-card-caption">用途未確認の入出金は集計保留</small></section></div>`;
    }
    if (book === 'BS') {
      const changes = {}, pending = {};
      const change = (map,account,amount) => { map[account] = (map[account] || 0)+amount; };
      rows.forEach(r => {
        if (r.excludeFromBalances) return;
        if (r.kind === 'pending') change(pending,r.account,r.direction === 'in' ? r.amount : -r.amount);
        else if (r.kind === 'transfer') { change(changes,r.account,-r.amount); change(changes,r.to,r.amount); }
        else if (r.kind === 'income') change(changes,r.account,r.amount);
        else (r.splits.length ? r.splits : [{account:r.account,amount:r.amount}]).forEach(p => change(changes,p.account,-p.amount));
      });
      const allNames = [...new Set([...Object.keys(changes),...Object.keys(pending)])];
      const names = allNames.filter(name => !liabilities.has(name));
      const debtNames = allNames.filter(name => liabilities.has(name));
      content = `<div class="ac-financial-grid"><section class="ac-panel ac-financial-card"><div class="ac-panel-head"><h2>資産の構成</h2><small class="ac-muted">BS</small></div><div class="ac-bs-diagram" role="img" aria-label="貸借対照表の構成。左が資産、右上が負債、右下が純資産。残高は未設定で面積は比率を示しません。"><div class="ac-bs-asset"><strong>資産</strong></div><div class="ac-bs-liability"><strong>負債</strong></div><div class="ac-bs-equity"><strong>純資産</strong></div><span class="ac-bs-unset">未設定</span></div></section><section class="ac-panel ac-financial-card"><div class="ac-panel-head"><h2>貸借対照表</h2><small class="ac-muted">残高不明・変動のみ</small></div><div class="ac-financial-scroll"><div class="ac-balance-columns"><div class="ac-balance-side"><h3 class="ac-income-tone">資産</h3>${names.length ? names.map(name => `<div class="ac-balance-account"><div><strong>${esc(name)}</strong><span>残高不明</span></div><small>変動 ${signed(changes[name] || 0)}</small>${pending[name] ? `<small class="ac-warning">保留 ${signed(pending[name])}</small>` : ''}</div>`).join('') : '<p class="ac-muted">未収録</p>'}<div class="ac-balance-total"><span>資産合計</span><strong>不明</strong></div></div><div class="ac-balance-side"><section><h3 class="ac-expense-tone">負債</h3>${debtNames.map(name => `<div class="ac-balance-account"><div><strong>${esc(name)}</strong><span>残高不明</span></div><small>変動 ${signed(-(changes[name] || 0))}</small></div>`).join('')}<div class="ac-balance-account"><div><span>負債合計</span><strong>不明</strong></div></div></section><section class="ac-equity-section"><h3 class="ac-equity-tone">純資産</h3><div class="ac-balance-account"><div><span>純資産合計</span><strong>不明</strong></div></div></section><div class="ac-balance-total"><span>負債・純資産</span><strong>不明</strong></div></div></div></div></section></div>`;
    }
    return `<div class="ac-ledger-layout"><div class="ac-book-tabs" aria-label="帳簿の表示">${['BS','PL','取引一覧','仕訳'].map(name => button(name,'book',name,book === name)).join('')}</div><div class="ac-ledger-content">${content}</div></div>`;
  }
  function render() {
    root.innerHTML = `<header class="page-head ac-head"><h1>家計</h1>${button('＋ 取引を追加','new')}</header><nav class="tabs ac-tabs" aria-label="家計の画面">${['ホーム','カレンダー','帳簿'].map(name => `<button type="button" data-ac-action="tab" data-value="${name}" aria-selected="${tab === name}">${name}</button>`).join('')}</nav><div class="ac-period"><div>${button('‹','month',-1)}<h2>${monthLabel()}</h2>${button('›','month',1)}</div>${button('対象月へ','reset-month')}<span class="ac-muted">${current().length}件</span></div><div id="ac-content">${tab === 'ホーム' ? home() : tab === 'カレンダー' ? calendar() : ledger()}</div><footer class="ac-scope-note">収録：2026年9〜10月（提供CSVの範囲） <span>・</span> 編集は再読み込みでリセット</footer><div id="ac-live" class="ac-sr-only" role="status" aria-live="polite"></div>`;
  }
  const dialog = document.createElement('dialog'); dialog.className = 'ac-dialog'; document.body.append(dialog);
  let edited = null;
  function editor(id, date) {
    edited = transactions.find(r => r.id === id) || null;
    const row = edited || {kind:'expense',date:date || month+'-01',amount:'',account:'PayPay残高',to:'Suica',category:'未分類',memo:'',sources:[],splits:[]};
    const options = (values,selected) => [...new Set([...values,selected])].filter(Boolean).map(value => `<option ${value === selected ? 'selected' : ''}>${esc(value)}</option>`).join('');
    dialog.innerHTML = `<form id="ac-form"><header><h2>${edited ? '取引の詳細・編集' : '取引を追加'}</h2><button type="button" data-close aria-label="閉じる">×</button></header><p class="ac-muted">保存内容はこの画面を開いている間だけ有効です。</p><div class="ac-form-grid"><label>種類<select name="kind">${[['expense','支出'],['income','収入'],['transfer','振替'],...(edited?.kind === 'pending' ? [['pending','用途未確認']] : [])].map(([v,n]) => `<option value="${v}" ${row.kind === v ? 'selected' : ''}>${n}</option>`).join('')}</select></label><label>日付<input name="date" type="date" min="2000-01-01" max="2100-12-31" value="${esc(row.date)}" required></label><label>金額（円）<input name="amount" type="number" step="1" min="-999999999" max="999999999" value="${row.amount}" required><small>支出の返金は負数。0円は保存できません。</small></label><label><span id="ac-account-label">口座</span><select name="account">${options(accounts,row.account)}</select></label><label id="ac-to-field">振替先<select name="to">${options(accounts,row.to || 'Suica')}</select></label><label id="ac-category-field">カテゴリ<input name="category" list="ac-category-options" value="${esc(row.category)}" maxlength="40" required><datalist id="ac-category-options">${categories.map(c => `<option value="${c}">`).join('')}</datalist></label><label class="ac-full">メモ<textarea name="memo" rows="2" maxlength="300">${esc(row.memo)}</textarea></label></div>${row.splits.length ? `<p class="ac-warning">原本の決済内訳：${row.splits.map(p => `${esc(p.account)} ${yen(p.amount)}`).join(' / ')}。金額・口座・種類を変更すると、この内訳を解除して選択口座1つで再計算します。</p>` : ''}<details ${edited ? 'open' : ''}><summary>仕訳詳細</summary><div id="ac-journal-preview"></div></details>${edited ? `<details><summary>出典・確認状態</summary><p class="ac-muted">${esc(row.status)}。${row.sources.length ? esc(sourceText(row.sources)) : 'この画面で追加した取引です。'}</p>${row.categoryBasis ? `<p class="ac-muted">分類根拠：${esc(row.categoryBasis)}</p>` : ''}</details>` : ''}<p id="ac-form-error" class="ac-error" role="alert"></p><footer><button type="button" data-close>キャンセル</button><button class="ac-primary" type="submit">${edited ? '変更を保存' : '追加する'}</button></footer></form>`;
    const bills = (seed.bills || []).filter(b => b.paymentTransactionIds?.includes(id));
    if (bills.length) {
      dialog.querySelector('form > footer').insertAdjacentHTML('beforebegin', bills.map(b => `<details open class="ac-bill-details"><summary>${esc(b.account)}・${esc(b.billingMonth)}請求の内訳</summary><p class="ac-muted">請求額 ${yen(b.total)} / 利用日ベースの明細。引き落とし時に支出を重ねて計上しません。</p><div class="ac-scroll"><table class="ac-table"><thead><tr><th>利用日</th><th>利用先</th><th class="ac-number">利用額</th></tr></thead><tbody>${b.items.map(item => `<tr><td>${esc(item.date)}</td><td>${esc(item.memo)}</td><td class="ac-number">${yen(item.amount)}</td></tr>`).join('')}</tbody></table></div></details>`).join(''));
    }
    const form = dialog.querySelector('form');
    const draft = () => {
      const values = Object.fromEntries(new FormData(form));
      const r = {...row,...values,amount:Number(values.amount)};
      r.splits = edited && r.amount === edited.amount && r.account === edited.account && r.kind === edited.kind ? edited.splits : [];
      r.to = r.kind === 'transfer' ? r.to : '';
      r.category = r.kind === 'transfer' ? '振替' : r.category.trim();
      return r;
    };
    const preview = () => {
      const r = draft();
      dialog.querySelector('#ac-to-field').hidden = r.kind !== 'transfer';
      dialog.querySelector('#ac-category-field').hidden = r.kind === 'transfer';
      form.elements.category.required = r.kind !== 'transfer';
      dialog.querySelector('#ac-account-label').textContent = r.kind === 'transfer' ? '振替元' : '口座';
      dialog.querySelector('#ac-journal-preview').innerHTML = r.kind === 'pending' ? '<p class="ac-warning">用途と相手勘定が未確認のため、仕訳を保留しています。支出・収入・振替へ区分すると、仕訳が表示されます。</p>' : r.amount && Number.isFinite(r.amount) ? journalTable([r]) : '<p class="ac-muted">金額を入力すると表示します。</p>';
    };
    form.addEventListener('input',preview); form.addEventListener('change',preview); preview();
    dialog.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click',() => dialog.close()));
    form.addEventListener('submit',event => {
      event.preventDefault();
      const r = draft(), error = dialog.querySelector('#ac-form-error');
      if (!Number.isSafeInteger(r.amount) || !r.amount || Math.abs(r.amount)>999999999 || r.kind !== 'expense' && r.amount < 0) { error.textContent = '金額を整数で入力してください。収入・振替は1円以上、支出の返金は負数で入力できます。'; return; }
      if (!/^\d{4}-\d{2}-\d{2}$/.test(r.date) || r.date < '2000-01-01' || r.date > '2100-12-31') { error.textContent = '有効な日付を入力してください。'; return; }
      if (r.kind === 'transfer' && r.account === r.to) { error.textContent = '振替元と振替先に別の口座を選んでください。'; return; }
      if (r.kind !== 'transfer' && !r.category) { error.textContent = 'カテゴリを入力してください。'; return; }
      r.status = edited ? '画面で編集' : '画面で追加';
      if (edited) transactions[transactions.indexOf(edited)] = r;
      else transactions.push({...r,id:`manual-${crypto.randomUUID()}`,sources:[]});
      month = r.date.slice(0,7); selectedDay = r.date; dialog.close(); render();
      root.querySelector('#ac-live').textContent = '取引を反映しました。再読み込みすると元に戻ります。';
      root.querySelector('[data-ac-action="new"]').focus();
    });
    dialog.showModal();
  }
  root.addEventListener('click',event => {
    const target = event.target.closest('[data-ac-action]'); if (!target) return;
    const action = target.dataset.acAction, value = target.dataset.value;
    if (action === 'new' || action === 'edit') { editor(action === 'edit' ? value : null,action === 'new' ? value : null); return; }
    if (action === 'tab') { tab = value; drawerOpen = false; }
    if (action === 'book') book = value;
    if (action === 'scale') scale = value;
    if (action === 'day') { selectedDay = value; drawerOpen = true; }
    if (action === 'close-drawer') drawerOpen = false;
    if (action === 'month') { drawerOpen = false; const [y,m] = month.split('-').map(Number), d = new Date(y,m-1+Number(value),1); month = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`; selectedDay = month+'-01'; }
    if (action === 'reset-month') { drawerOpen = false; month = '2026-10'; selectedDay = month+'-01'; }
    render();
    if (action === 'close-drawer') { root.querySelector(`[data-ac-action="day"][data-value="${selectedDay}"]`)?.focus({preventScroll:true}); return; }
    const replacement = [...root.querySelectorAll('[data-ac-action]')].find(b => b.dataset.acAction === action && b.dataset.value === value);
    replacement?.focus({preventScroll:true});
  });
  document.addEventListener('keydown',event => {
    if (!drawerOpen || dialog.open || root.hidden) return;
    if (event.key === 'Escape') {
      event.preventDefault(); drawerOpen = false; render();
      root.querySelector(`[data-ac-action="day"][data-value="${selectedDay}"]`)?.focus({preventScroll:true});
    }

  });
  window.LifeAccounting = {render};
})();
