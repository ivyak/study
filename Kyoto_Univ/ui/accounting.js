/* Read-only accounting view. Published DB data replaces the retained demo snapshot. */
(() => {
  const demoSeed = window.LifeAccountingData;
  let seed = demoSeed;
  const root = document.getElementById('accounting-view');
  if (!seed || !root) return;
  const categoryName = name => ['交通','交通費'].includes(name) ? '交通' : ['美容','衣服','美容・衣服'].includes(name) ? '美容・衣服' : name;
  let transactions, apiState = {ready:false}, apiLoadedAt = 0, apiLoading = false;
  function normalizeTransactions() {
    transactions = structuredClone(seed.transactions);
    transactions.forEach(row => {
      if (row.categoryAmounts?.length) {
        const amounts = {};
        row.categoryAmounts.forEach(c => { const name = categoryName(c.category); amounts[name] = (amounts[name] || 0)+c.amount; });
        row.categoryAmounts = Object.entries(amounts).map(([category,amount]) => ({category,amount}));
        row.category = Object.keys(amounts).join(' / ');
      } else row.category = categoryName(row.category);
      row.zaimItems?.forEach(item => { item.category = categoryName(item.category); });
    });
  }
  normalizeTransactions();
  async function refreshDatabase() {
    if (apiLoading || Date.now()-apiLoadedAt < 30000) return;
    apiLoading = true;
    try {
      const base = location.protocol === 'file:' ? 'http://127.0.0.1:8765' : '';
      const response = await fetch(base+'/api/accounting/snapshot',{cache:'no-store',signal:AbortSignal.timeout(15000)});
      if (!response.ok) throw new Error('家計APIに接続できません。');
      const data = await response.json();
      apiState = data;
      if (data.ready) {
        seed = data;
        normalizeTransactions();
        if (!transactions.some(inMonth) && apiLoadedAt === 0 && seed.end) month = seed.end.slice(0,7);
      } else {
        seed = demoSeed;
        normalizeTransactions();
      }
    } catch (error) {
      apiState = {...apiState, unavailable:true};
    } finally {
      apiLoadedAt = Date.now();
      apiLoading = false;
      render();
    }
  }
  const privacyStorageKey = 'life.accounting.hideAmounts';
  function savedPrivacy() {
    try { return window.localStorage.getItem(privacyStorageKey) === 'true'; }
    catch { return false; }
  }
  let tab = 'ホーム', book = '取引', report = 'BS', month = '2026-10', scale = 'month', selectedDay = seed.start, drawerOpen = false, hideAmounts = savedPrivacy(), excludeRemittance = false, transactionSort = 'date-asc', transactionKind = '', transactionCategory = '';
  const liabilities = new Set(['三井住友カード未払金', '楽天カード未払金', 'クレジットカード未払金']);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const yen = value => `${value < 0 ? '−' : ''}¥${Math.abs(value).toLocaleString('ja-JP')}`;
  const signed = value => `${value >= 0 ? '+' : '−'}¥${Math.abs(value).toLocaleString('ja-JP')}`;
  const monthLabel = () => `${month.slice(0,4)}年${Number(month.slice(5))}月`;
  const inMonth = row => row.date.startsWith(month);
  const annual = () => scale === 'year' && tab !== 'カレンダー';
  const periodLabel = () => annual() ? month.slice(0,4)+'年' : monthLabel();
  const inPeriod = row => row.date.startsWith(annual() ? month.slice(0,4) : month);
  const current = () => transactions.filter(inPeriod);
  const stats = rows => ({income: rows.filter(r => r.kind === 'income').reduce((s,r) => s+r.amount,0), expense: rows.filter(r => r.kind === 'expense').reduce((s,r) => s+r.amount,0)});
  const sourceText = refs => refs.map(ref => `${ref.file}：${ref.line}行目`).join(' / ');
  const button = (label, action, value = '', active = false) => `<button type="button" data-ac-action="${action}" data-value="${esc(value)}" ${active ? 'aria-pressed="true"' : ''}>${label}</button>`;
  const empty = text => `<p class="ac-empty">${text}</p>`;
  const loading = text => `<div class="ac-loading-state" role="status"><span class="ac-loading-spinner" aria-hidden="true"></span><span>${text}</span></div>`;
  const within = date => date >= seed.start && date <= seed.end;
  const categoriesFor = row => row.categoryAmounts?.length ? row.categoryAmounts : [{category:row.category,amount:row.amount}];
  const categoryPalette = {
    '食費':'#b8d866',
    '日用雑貨':'#7dcede',
    '交通':'#b69ad8', '交通費':'#b69ad8',
    'エンタメ':'#e6a36a', '娯楽費':'#e6a36a',
    '教育':'#bb9674', '教育・教養':'#bb9674', '書籍・教材費':'#bb9674',
    '美容':'#78bc8c', '美容・衣服':'#78bc8c',
    'その他':'#a4a4a4', '未分類':'#a4a4a4',
    '交際費':'#d86c87', 'クルマ':'#e57d73', '医療・保険':'#e0cc65', '医療保険':'#e0cc65',
    '水道光熱費':'#e0cc65', '水道光熱':'#e0cc65', '水道高熱':'#e0cc65',
    '通信・サブスク':'#7da9e4', '通信サブスク':'#7da9e4',
    '大型出費/旅行':'#a4a4a4', '振替':'#d7b66c'
  };
  const categoryColor = name => seed.categoryColors?.[categoryName(name)] || categoryPalette[categoryName(name)] || categoryPalette['その他'];
  const warningIcon = '<svg class="ac-warning-icon" viewBox="0 0 24 24" role="img" aria-label="確認待ち"><path d="M10.3 3.9a2 2 0 0 1 3.4 0l8.2 14.2a2 2 0 0 1-1.7 3H3.8a2 2 0 0 1-1.7-3z" fill="currentColor"/><path d="M12 8v6" stroke="#17150c" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="17.5" r="1.1" fill="#17150c"/></svg>';
  const monthButton = delta => `<button type="button" class="ac-month-arrow" data-ac-action="month" data-value="${delta}" aria-label="${delta < 0 ? '前' : '次'}の${annual() ? '年' : '月'}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${delta < 0 ? 'M14 6l-6 6 6 6' : 'M10 6l6 6-6 6'}"/></svg></button>`;
  const categoryLabels = row => categoriesFor(row).map(c => `<span style="color:${categoryColor(c.category)}">${esc(c.category)}${c.category === '未分類' ? warningIcon : ''}</span>`).join('<span class="ac-category-divider"> / </span>');
  const displayAmount = row => row.amount === 0 ? yen(0) : row.kind === 'expense' ? signed(-row.amount) : ['transfer','opening'].includes(row.kind) ? yen(row.amount) : signed(row.kind === 'pending' && row.direction === 'out' ? -row.amount : row.amount);
  const journal = row => {
    if (row.journalEntries) return row.journalEntries;
    if (row.kind === 'pending') return [];
    if (row.kind === 'transfer') return [{debit:row.to,credit:row.account,amount:row.amount}];
    if (row.kind === 'income') return [{debit:row.account,credit:row.category,amount:row.amount}];
    const parts = row.splits.length ? row.splits : [{account:row.account,amount:row.amount}];
    if (row.categoryAmounts?.length) {
      const credits = parts.map(p => ({...p,remaining:p.amount}));
      return categoriesFor(row).flatMap(c => {
        let remaining = c.amount;
        const lines = [];
        for (const p of credits) {
          const value = Math.min(remaining,p.remaining);
          if (value > 0) lines.push({debit:c.category,credit:p.account,amount:value});
          remaining -= value; p.remaining -= value;
        }
        return lines;
      });
    }
    return parts.map(part => row.amount < 0 ? {debit:part.account,credit:row.category,amount:-part.amount} : {debit:row.category,credit:part.account,amount:part.amount});
  };
  const journalAccount = name => (seed.categoryColors?.[name] || categoryPalette[name]) && name !== '振替' ? `<span style="color:${categoryColor(name)}">${esc(name)}</span>` : esc(name);
  const journalTable = rows => `<div class="ac-scroll"><table class="ac-table"><thead><tr><th>日付</th><th>借方</th><th>貸方</th><th class="ac-number">金額</th></tr></thead><tbody>${rows.flatMap(row => journal(row).map(line => `<tr><td>${esc(row.date)}</td><td>${journalAccount(line.debit)}</td><td>${journalAccount(line.credit)}</td><td class="ac-number">${yen(line.amount)}</td></tr>`)).join('')}</tbody></table></div>`;
  const kindNames = {expense:'支出',income:'収入',transfer:'振替',opening:'開始残高',pending:'用途未確認'};
  const transactionLabels = row => `<span class="ac-card-labels"><span class="ac-badge ac-kind-${row.kind}">${kindNames[row.kind]}</span>${row.kind !== 'transfer' ? `<span class="ac-category-divider">/</span><span class="ac-card-category">${categoryLabels(row)}</span><span class="ac-category-divider">/</span><span class="ac-list-account">${esc(row.account)}${row.to ? ` → ${esc(row.to)}` : ''}</span>` : ''}</span>`;
  const rowList = (rows, emptyMessage = 'この範囲に収録された取引はありません。') => !rows.length ? empty(emptyMessage) : `<div class="ac-transaction-list">${rows.map(row => `<button type="button" class="ac-transaction-card ac-ledger-row${row.zaimItems?.length ? ' ac-has-zaim' : ''}" data-ac-action="edit" data-value="${esc(row.id)}"><span class="ac-list-date">${esc(row.date)}</span><span class="ac-list-summary">${transactionLabels(row)}<span class="ac-card-title">${esc(row.memo)}</span></span><strong class="ac-card-amount">${displayAmount(row)}</strong></button>`).join('')}</div>`;
  const evidence = (format = yen) => !seed.evidence.some(r => inPeriod(r) && !r.matchedTransactionId) ? '' : `<details class="ac-evidence"><summary>Zaimの未対応資料（${seed.evidence.filter(r => inPeriod(r) && !r.matchedTransactionId).length}件）</summary><p class="ac-muted">支払元・決済対応は未確認のため集計対象外。負数は割引。</p><div class="ac-scroll"><table class="ac-table"><thead><tr><th>日付</th><th>店 / 品目</th><th>分類</th><th class="ac-number">金額</th><th>原本</th></tr></thead><tbody>${seed.evidence.filter(r => inPeriod(r) && !r.matchedTransactionId).map(r => `<tr><td>${r.date}</td><td>${esc(r.store)}<small>${esc(r.item)}</small></td><td>${esc(r.category)} / ${esc(r.detail)}</td><td class="ac-number">${format(r.amount)}</td><td>${esc(r.source.file)}<small>${r.source.line}行目</small></td></tr>`).join('')}</tbody></table></div></details>`;
  const zaimDetails = row => {
    const items = row.itemDetails ?? row.zaimItems;
    if (!items?.length) return '';
    const label = row.itemSourceLabel ?? 'Zaim';
    const status = row.zaimMatch?.status ?? row.status ?? '';
    const store = row.zaimMatch?.store ?? items[0].store ?? '';
    return `<details class="ac-zaim-items" open><summary>${esc(label)}の品目内訳（${items.length}行）<span class="ac-badge">${esc(status)}</span></summary><p class="ac-zaim-store">${esc(store)}</p>${row.receiptTotal ? `<p class="ac-muted">会計 ${yen(row.receiptTotal)} ／ 自己負担 ${yen(row.amount)} ／ 立替 ${yen(row.advanceAmount)}</p>` : ''}<div class="ac-scroll"><table class="ac-table"><thead><tr><th>品目 / 分類</th><th class="ac-number">金額</th></tr></thead><tbody>${items.map(z => `<tr><td>${esc(z.item)}<span class="ac-zaim-category" style="color:${categoryColor(z.category)}">${esc(z.category)}${z.detail ? ` / ${esc(z.detail)}` : ''}</span></td><td class="ac-number">${yen(z.amount)}</td></tr>`).join('')}</tbody></table></div></details>`;
  };
  function home() {
    const rows = current(), totals = stats(rows);
    const slice = rows;
    const expenses = {};
    slice.filter(r => r.kind === 'expense').forEach(r => categoriesFor(r).forEach(c => expenses[c.category] = (expenses[c.category] || 0) + c.amount));
    let excluded = 0;
    const excludedByPurpose = {};
    if (excludeRemittance) {
      Object.entries(seed.remittanceAdjustments || {}).filter(([key]) => key.startsWith(annual() ? month.slice(0,4) : month)).forEach(([,adjustment]) => {
        excluded += adjustment.amount;
        Object.entries(adjustment.expenseByCategory).forEach(([category,amount]) => expenses[category] = (expenses[category] || 0)-amount);
        Object.entries(adjustment.expenseByPurpose || adjustment.expenseByCategory).forEach(([name,amount]) => excludedByPurpose[name] = (excludedByPurpose[name] || 0)+amount);
      });
      totals.income -= excluded;
      totals.expense -= excluded;
    }
    const groups = Object.entries(expenses).filter(([,v]) => v > 0).sort((a,b) => b[1]-a[1]);
    const total = groups.reduce((sum,[,v]) => sum+v,0);
    const pendingOut = rows.filter(r => r.kind === 'pending' && !r.excludeFromBalances && r.direction === 'out').reduce((sum,r) => sum+r.amount,0);
    const pendingIn = rows.filter(r => r.kind === 'pending' && !r.excludeFromBalances && r.direction === 'in').reduce((sum,r) => sum+r.amount,0);
    const covered = rows.length > 0 || inPeriod({date:seed.start}) || inPeriod({date:seed.end});
    const money = value => hideAmounts ? '---' : yen(value);
    const excludedDetails = Object.entries(excludedByPurpose).map(([name,amount]) => `${esc(name)} ${money(amount)}`).join(' ／ ');
    let angle = -Math.PI/2;
    const donutSegments = groups.map(([name,value]) => {
      const end = angle+value/total*Math.PI*2;
      const point = a => `${50+44*Math.cos(a)} ${50+44*Math.sin(a)}`;
      const path = groups.length === 1 ? 'M50 6 A44 44 0 1 1 50 94 A44 44 0 1 1 50 6'
        : `M${point(angle)} A44 44 0 ${value/total > .5 ? 1 : 0} 1 ${point(end)}`;
      angle = end;
      return `<path class="ac-home-chart-category" d="${path}" stroke="${categoryColor(name)}" data-ac-action="home-filter" data-value="${esc(name)}" role="button" tabindex="0" aria-label="${esc(name)} ${money(value)}の取引を見る"><title>${esc(name)} ${money(value)}</title></path>`;
    }).join('');
    const remittanceControl = `<div class="ac-home-options"><button type="button" class="ac-remittance-toggle" data-ac-action="remittance" aria-pressed="${excludeRemittance}" title="家賃・新幹線代・免許合宿・参考書・コンタクト代を、同月の仕送り額を上限に収入と支出の両方から除きます。仕送り不足時は対象カテゴリの支出額に応じて配分します。">仕送りによる立替を除く</button>${excludeRemittance ? `<span class="ac-muted">${excludedDetails ? '除外：'+excludedDetails : '除外対象なし'}</span>` : ''}</div>`;
    const pendingWarning = title => {
      const value = title === '収入' ? pendingIn : title === '支出' ? pendingOut : 0;
      return value ? `<span class="ac-pending-hint" tabindex="0" aria-label="集計保留 ${money(value)}">${warningIcon}<span class="ac-pending-tooltip" role="tooltip">集計保留 ${money(value)}</span></span>` : '';
    };
    return `<div class="ac-home-layout">${remittanceControl}<div class="ac-metrics">${[['収入',totals.income,'ac-positive'],['支出',totals.expense,''],['収支差額',totals.income-totals.expense,totals.income < totals.expense ? 'ac-negative' : '']].map(([title,value,cls]) => `<div class="ac-metric"><p>${title}${pendingWarning(title)}</p><strong class="${cls}">${covered ? money(value) : '—'}</strong></div>`).join('')}</div><section class="ac-panel ac-home-chart"><div class="ac-panel-head"><h2>カテゴリ別支出 <small>${periodLabel()}</small></h2></div>${total > 0 ? `<div class="ac-chart-layout"><div class="ac-donut"><svg class="ac-donut-segments" viewBox="0 0 100 100" role="group" aria-label="カテゴリ別支出。クリックすると取引一覧を表示">${donutSegments}</svg><div><small>支出合計</small><strong>${money(total)}</strong></div></div><div class="ac-categories">${groups.map(([name,value]) => `<button type="button" data-ac-action="home-filter" data-value="${esc(name)}" aria-label="${esc(name)}の取引を見る"><span><i style="background:${categoryColor(name)}"></i>${esc(name)}</span><strong>${money(value)}</strong><small>${(value/total*100).toFixed(1)}%</small></button>`).join('')}</div></div>` : empty('支出データは未収録です。')}</section><div class="ac-source-disclosure">${evidence(money)}</div></div>`;
  }
  const unmatchedZaim = date => seed.evidence.filter(z => z.date === date && !z.matchedTransactionId);
  const unmatchedZaimDetails = date => {
    const items = unmatchedZaim(date);
    return !items.length ? '' : `<section class="ac-zaim-items"><h3>未照合のZaim記録（${items.length}行）</h3><p class="ac-muted">支払元・決済対応が未確認のため、上の収支には含めていません。</p>${items.map(z => `<article class="ac-drawer-row"><div><span class="ac-badge">Zaim・未照合</span><strong>${yen(z.amount)}</strong></div><p>${esc(z.store)}</p>${z.item ? `<p>${esc(z.item)}</p>` : ''}<span class="ac-zaim-category" style="color:${categoryColor(z.category)}">${esc(z.category)}${z.detail ? ` / ${esc(z.detail)}` : ''}</span></article>`).join('')}</section>`;
  };
  function dayDrawer() {
    const rows = transactions.filter(r => r.date === selectedDay);
    return `<aside class="ac-drawer" role="region" aria-labelledby="ac-drawer-title"><header><div><small>日別明細</small><h2 id="ac-drawer-title">${esc(selectedDay)}</h2></div>${button('×','close-drawer')}</header><div class="ac-drawer-body">${rows.length ? rows.map(r => `<button type="button" class="ac-transaction-card${r.zaimItems?.length ? ' ac-has-zaim' : ''}" data-ac-action="edit" data-value="${esc(r.id)}">${transactionLabels(r)}<strong class="ac-card-amount">${displayAmount(r)}</strong><span class="ac-card-title">${esc(r.memo)}</span></button>`).join('') : empty('決済の記録はありません。')}${unmatchedZaimDetails(selectedDay)}</div></aside>`;
  }
  function calendar() {
    const [year,m] = month.split('-').map(Number), count = new Date(year,m,0).getDate(), offset = new Date(year,m-1,1).getDay();
    const weeks = Math.ceil((offset+count)/7);
    const cells = Array(offset).fill('<div class="ac-day ac-blank"></div>');
    for (let day=1;day<=count;day++) {
      const date = `${month}-${String(day).padStart(2,'0')}`, rows = transactions.filter(r => r.date === date), totals = stats(rows), weekday = (offset+day-1)%7;
      const available = within(date) || rows.length;
      const transferTotal = rows.filter(r => r.kind === 'transfer').reduce((sum,r) => sum+Math.abs(r.amount),0);
      cells.push(`<button type="button" class="ac-day ${weekday === 0 ? 'ac-sunday' : weekday === 6 ? 'ac-saturday' : ''} ${date === selectedDay ? 'ac-selected' : ''} ${available ? '' : 'ac-outside'}" data-ac-action="day" data-value="${date}" aria-label="${date}、${available ? `${rows.length}件` : '未収録'}" aria-expanded="${drawerOpen && date === selectedDay}"><span class="ac-day-heading"><span>${day}</span>${rows.some(r => r.kind === 'pending' || r.category === '未分類') || unmatchedZaim(date).length ? warningIcon : ''}</span>${available ? ` ${totals.income ? `<small class="ac-positive">${signed(totals.income)}</small>` : ''}${totals.expense ? `<small>${signed(-totals.expense)}</small>` : ''}${transferTotal ? `<small class="ac-transfer-total" aria-label="振替 ${yen(transferTotal)}"><span>${yen(transferTotal)}</span></small>` : ''}${unmatchedZaim(date).length ? `<em>Zaim未照合 ${unmatchedZaim(date).length}行</em>` : ''}` : '<small>—</small>'}</button>`);
    }
    while (cells.length < weeks*7) cells.push('<div class="ac-day ac-blank"></div>');
    return `<div class="ac-calendar-stage"><div class="ac-calendar"><div class="ac-week">${['日','月','火','水','木','金','土'].map((d,i) => `<span class="${i === 0 ? 'ac-sunday' : i === 6 ? 'ac-saturday' : ''}">${d}</span>`).join('')}</div><div class="ac-days" style="--weeks:${weeks}">${cells.join('')}</div></div>${drawerOpen ? dayDrawer() : '<aside class="ac-detail-placeholder"><span>日付を選択すると<br>明細を表示します。</span></aside>'}</div>`;
  }
  function ledger() {
    const rows = current(), totals = stats(rows), hasData = rows.length > 0;
    const plView = report === 'PL-表' ? '表' : '図';
    let content, toolbar = '';
    if (book === '取引') {
      const categories = [...new Set(transactions.filter(row => row.kind !== 'transfer').flatMap(row => categoriesFor(row).map(c => c.category)))].sort((a,b) => a.localeCompare(b,'ja'));
      const filtered = rows.filter(row => (!transactionKind || row.kind === transactionKind) && (!transactionCategory || (row.kind !== 'transfer' && categoriesFor(row).some(c => c.category === transactionCategory))));
      const [sortField,sortDirection] = transactionSort.split('-');
      filtered.sort((a,b) => {
        const comparison = sortField === 'amount' ? a.amount-b.amount : a.date.localeCompare(b.date);
        const tied = a.date.localeCompare(b.date) || String(a.id).localeCompare(String(b.id),'en',{numeric:true});
        return (comparison || tied)*(sortDirection === 'desc' ? -1 : 1);
      });
      toolbar = `<div class="ac-transaction-filters"><div class="ac-segment ac-kind-filter" role="group" aria-label="取引の種類">${[['すべて',''],['収入','income'],['支出','expense'],['振替','transfer'],['要確認','pending'],...(rows.some(r => r.kind === 'opening') ? [['開始残高','opening']] : [])].map(([name,value]) => button(name,'filter-kind',value,transactionKind === value)).join('')}</div><label class="ac-category-filter">カテゴリ<select data-ac-filter="category" aria-label="カテゴリで絞り込み"><option value="">すべて</option>${categories.map(name => `<option value="${esc(name)}"${transactionCategory === name ? ' selected' : ''}>${esc(name)}</option>`).join('')}</select></label><label class="ac-category-filter ac-sort-filter">並び順<select data-ac-filter="sort" aria-label="取引の並び順">${[['date-asc','日付：昇順'],['date-desc','日付：降順'],['amount-asc','金額：昇順'],['amount-desc','金額：降順']].map(([value,label]) => `<option value="${value}"${transactionSort === value ? ' selected' : ''}>${label}</option>`).join('')}</select></label><span class="ac-filter-count" role="status">${filtered.length} / ${rows.length}件</span>${transactionKind || transactionCategory ? button('解除','clear-filters') : ''}</div>`;
      content = `<section class="ac-panel ac-list-panel">${rowList(filtered,'条件に一致する取引はありません。')}<div class="ac-source-disclosure">${evidence()}</div></section>`;
    }
    if (book === '仕訳') content = `<section class="ac-panel ac-list-panel"><div class="ac-panel-head"><h2>仕訳帳</h2><small class="ac-muted">用途未確認は保留</small></div>${journalTable(rows)}</section>`;
    if (book === '決算書' && report !== 'BS') {
      const income = {}, expense = {};
      rows.forEach(r => { const group = r.kind === 'income' ? income : r.kind === 'expense' ? expense : null; if (group) categoriesFor(r).forEach(c => group[c.category] = (group[c.category] || 0)+c.amount); });
      const amount = value => hasData ? yen(value) : '未収録';
      const line = (name,value,cls='',kind='') => {
        const filterKind = kind || (name === '収入合計' ? 'income' : name === '費用合計' ? 'expense' : '');
        const tag = filterKind ? 'button' : 'div';
        return `<${tag} class="ac-pl-line ${cls}"${filterKind ? ` type="button" data-ac-action="pl-filter" data-value="${cls ? '' : esc(name)}" data-kind="${filterKind}" aria-label="${esc(name)}の取引を見る"` : ''}><span${!cls ? ` style="color:${categoryColor(name)}"` : ''}>${esc(name)}</span><strong>${amount(value)}</strong></${tag}>`;
      };
      const difference = totals.income-totals.expense;
      const expenseGroups = Object.entries(expense).filter(([,value]) => value !== 0).sort((a,b) => b[1]-a[1]);
      let running = totals.income;
      const steps = [{name:'収入',from:0,to:totals.income,value:totals.income,type:'income'}];
      expenseGroups.forEach(([name,value]) => { steps.push({name,from:running,to:running-value,value:-value,type:value > 0 ? 'expense' : 'income'}); running -= value; });
      steps.push({name:'収支差額',from:0,to:difference,value:difference,type:difference < 0 ? 'deficit' : 'result'});
      const high = Math.max(0,...steps.flatMap(step => [step.from,step.to]));
      const low = Math.min(0,...steps.flatMap(step => [step.from,step.to]));
      const range = high-low || 1;
      const y = value => 48+(high-value)/range*250;
      const pitch = 100, barWidth = 58, chartWidth = steps.length*pitch+40;
      const waterfall = `<svg class="ac-waterfall ac-category-waterfall" viewBox="0 0 ${chartWidth} 390" role="group" aria-label="収入${amount(totals.income)}からカテゴリ別の費用を差し引き、収支差額${amount(difference)}"><line class="ac-waterfall-zero" x1="12" x2="${chartWidth-12}" y1="${y(0)}" y2="${y(0)}"/>${steps.map((step,index) => {
        const x = 28+index*pitch, top = Math.min(y(step.from),y(step.to));
        const actualHeight = Math.abs(y(step.from)-y(step.to));
        const label = step.name.match(/.{1,5}/gu) || [''];
        const bar = hasData ? `<rect x="${x}" y="${top}" width="${barWidth}" height="${step.value ? Math.max(actualHeight,3) : 0}" rx="3" class="ac-waterfall-${step.type}"><title>${esc(step.name)} ${yen(step.value)}${actualHeight < 3 && step.value ? '（視認性のため最小表示高）' : ''}</title></rect>` : '';
        const clickable = index < steps.length-1;
        return `${clickable ? `<g class="ac-pl-chart-category" role="button" tabindex="0" data-ac-action="pl-filter" data-value="${index ? esc(step.name) : ''}" data-kind="${index ? 'expense' : 'income'}" aria-label="${esc(step.name)}の取引を見る"><rect class="ac-chart-hit-area" x="${x-16}" y="0" width="${pitch}" height="385" rx="6"/>` : ''}${index ? `<line class="ac-waterfall-connector" x1="${x-pitch+barWidth}" x2="${x}" y1="${y(index === steps.length-1 ? step.to : step.from)}" y2="${y(index === steps.length-1 ? step.to : step.from)}"/>` : ''}${bar}<text x="${x+barWidth/2}" y="${Math.max(16,top-10)}" class="ac-waterfall-value">${hasData ? (step.type === 'expense' ? signed(step.value) : yen(step.value)) : '未収録'}</text><text x="${x+barWidth/2}" y="338" class="ac-waterfall-label" style="fill:${index > 0 && index < steps.length-1 ? categoryColor(step.name) : '#c4c0b4'}">${label.map((part,i) => `<tspan x="${x+barWidth/2}" dy="${i ? 16 : 0}">${esc(part)}</tspan>`).join('')}</text>${clickable ? '</g>' : ''}`;
      }).join('')}</svg>`;
      content = `<div class="ac-pl-page"><section class="ac-panel ac-financial-card ${plView === '図' ? 'ac-pl-diagram-page' : 'ac-pl-table-page'}">${plView === '図' ? `<div class="ac-panel-head"><h2>収支の流れ</h2><small class="ac-muted">${periodLabel()}</small></div><div class="ac-pl-flow" tabindex="0" aria-label="カテゴリ別収支の流れ">${waterfall}</div>` : `<div class="ac-panel-head"><h2>損益計算書</h2><small class="ac-muted">${periodLabel()}</small></div><div class="ac-financial-scroll"><div class="ac-pl-details" style="--pl-rows:${Object.keys(income).length+Object.keys(expense).length+3}">${line('収入合計',totals.income,'ac-pl-section ac-income-tone')}${Object.entries(income).map(([name,value]) => line(name,value,'','income')).join('')}${line('費用合計',totals.expense,'ac-pl-section ac-expense-tone')}${Object.entries(expense).map(([name,value]) => line(name,value,'','expense')).join('')}${line('収支差額',totals.income-totals.expense,`ac-pl-total${difference < 0 ? ' ac-negative' : ''}`)}</div></div><small class="ac-card-caption">用途未確認の入出金は集計保留</small>`}</section></div>`;
    }
    if (book === '決算書' && report === 'BS') {
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
    if (book === '決算書' && report === 'BS' && apiState.ready) content = databaseBalanceSheet();
    if (book === '決算書') toolbar = `<div class="ac-segment ac-report-tabs" aria-label="決算書の表示">${['BS','PL-グラフ','PL-表'].map(name => button(name,'report',name,report === name)).join('')}</div>`;
    return `<div class="ac-ledger-layout"><div class="ac-ledger-toolbar"><div class="ac-book-tabs" aria-label="帳簿の表示">${['取引','仕訳','決算書'].map(name => button(name,'book',name,book === name)).join('')}</div>${toolbar}</div><div class="ac-ledger-content">${content}</div></div>`;
  }
  const balanceRequests = new Set();
  function databaseBalanceSheet() {
    const period = annual() ? month.slice(0,4) : month;
    const sheets = annual() ? (seed.yearlyBalanceSheets ||= {}) : (seed.balanceSheets ||= {});
    const sheet = sheets[period];
    if (!sheet) {
      const key = `${apiState.publishedBatch}:${period}`;
      if (!balanceRequests.has(key)) {
        balanceRequests.add(key);
        const original = seed;
        fetch(`/api/accounting/bs?${annual() ? 'year' : 'month'}=${period}`,{cache:'no-store'})
          .then(response => { if (!response.ok) throw new Error(); return response.json(); })
          .then(data => { if (seed === original) { sheets[period] = data; render(); } })
          .catch(() => { balanceRequests.delete(key); });
      }
      return loading('貸借対照表を取得しています。');
    }
    const money = value => value === null ? '不明' : yen(value);
    const accounts = type => sheet.accounts.filter(a => a.type === type).map(a => `<div class="ac-balance-account"><div><strong>${esc(a.name)}</strong><span>${money(a.balance)}</span></div><small>${annual() ? '年間' : '月間'}変動 ${signed(a.change)}</small></div>`).join('') || '<p class="ac-muted">未収録</p>';
    const ratioKnown = sheet.complete && sheet.assets > 0 && sheet.liabilities >= 0 && sheet.netAssets >= 0;
    const debt = ratioKnown ? sheet.liabilities/sheet.assets*100 : 50;
    return `<div class="ac-financial-grid"><section class="ac-panel ac-financial-card"><div class="ac-panel-head"><h2>資産の構成</h2><small class="ac-muted">BS</small></div><div class="ac-bs-diagram" style="grid-template-rows:${debt}fr ${100-debt}fr" role="img" aria-label="${ratioKnown ? '資産・負債・純資産の金額比率' : '残高未設定または負数を含むため面積は比率を示しません。'}"><div class="ac-bs-asset"><strong>資産</strong><span>${money(sheet.assets)}</span></div><div class="ac-bs-liability"><strong>負債</strong><span>${money(sheet.liabilities)}</span></div><div class="ac-bs-equity"><strong>純資産</strong><span>${money(sheet.netAssets)}</span></div>${ratioKnown ? '' : '<span class="ac-bs-unset">比率未表示</span>'}</div></section><section class="ac-panel ac-financial-card"><div class="ac-panel-head"><h2>貸借対照表</h2><small class="ac-muted">${annual() ? month.slice(0,4)+'年12月' : monthLabel()}末</small></div><div class="ac-financial-scroll"><div class="ac-balance-columns"><div class="ac-balance-side"><h3 class="ac-income-tone">資産</h3>${accounts('asset')}<div class="ac-balance-total"><span>資産合計</span><strong>${money(sheet.assets)}</strong></div></div><div class="ac-balance-side"><h3 class="ac-expense-tone">負債</h3>${accounts('liability')}<div class="ac-balance-total"><span>負債合計</span><strong>${money(sheet.liabilities)}</strong></div><section class="ac-equity-section"><h3 class="ac-equity-tone">純資産</h3><div class="ac-balance-total"><span>純資産合計</span><strong>${money(sheet.netAssets)}</strong></div></section></div></div></div></section></div>`;
  }
  function dataUpdateLabel() {
    if (!apiState.dataUpdatedAt) return '';
    const updated = new Date(apiState.dataUpdatedAt);
    if (Number.isNaN(updated.getTime())) return '';
    const label = new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(updated);
    return `<span class="ac-data-updated" title="帳簿データを最後に確定・変更した日時（日本時間）">最終更新：<time datetime="${esc(apiState.dataUpdatedAt)}">${esc(label)}</time></span>`;
  }
  function render() {
    void refreshDatabase();
    root.setAttribute('aria-busy', String(apiLoading && !apiLoadedAt));
    root.innerHTML = `<header class="page-head ac-head"><h1>家計</h1><div class="ac-update-state">${apiLoading && apiLoadedAt ? '<span class="ac-loading-spinner" role="status" aria-label="家計データを読み込み中"></span>' : ''}${dataUpdateLabel()}</div></header><nav class="tabs ac-tabs" aria-label="家計の画面">${['ホーム','カレンダー','帳簿'].map(name => `<button type="button" data-ac-action="tab" data-value="${name}" aria-selected="${tab === name}">${name}</button>`).join('')}</nav><div class="ac-period"><div>${monthButton(-1)}<h2>${periodLabel()}</h2>${monthButton(1)}</div>${tab !== 'カレンダー' ? `<div class="ac-segment ac-period-scale" role="group" aria-label="集計単位">${button('月','scale','month',scale === 'month')}${button('年','scale','year',scale === 'year')}</div>` : ''}${button(annual() ? '今年' : '今月','reset-month')}${tab === 'ホーム' ? `<button type="button" class="ac-privacy-switch" data-ac-action="privacy" role="switch" aria-checked="${hideAmounts}" aria-label="金額を隠す"><span class="ac-privacy-label">金額を隠す</span><span class="ac-switch-track" aria-hidden="true"><span></span></span></button>` : `<span class="ac-muted">${current().length}件</span>`}</div><div id="ac-content">${apiLoading && !apiLoadedAt ? loading('家計データを読み込んでいます。') : tab === 'ホーム' ? home() : tab === 'カレンダー' ? calendar() : ledger()}</div><footer class="ac-scope-note">${apiState.ready ? `収録：${esc(seed.start)}〜${esc(seed.end)}（確定分）` : 'デモ：2026年9〜10月'} <span>・</span> 修正はZaim・対応付けはCodex</footer><div id="ac-live" class="ac-sr-only" role="status" aria-live="polite"></div>`;
  }
  const dialog = document.createElement('dialog'); dialog.className = 'ac-dialog'; document.body.append(dialog);
  function viewer(id) {
    const row = transactions.find(r => r.id === id);
    if (!row) return;
    const bills = (seed.bills || []).filter(b => b.paymentTransactionIds?.includes(id));
    dialog.innerHTML = `<header><h2>取引の詳細</h2><button type="button" data-close aria-label="閉じる">×</button></header><div class="ac-dialog-body" tabindex="0" aria-label="取引の詳細内容"><dl class="ac-readonly-fields"><div><dt>日付</dt><dd>${esc(row.date)}</dd></div><div><dt>内容</dt><dd>${esc(row.memo)}</dd></div><div><dt>金額</dt><dd>${yen(row.amount)}</dd></div><div><dt>口座</dt><dd>${esc(row.account)}${row.to ? ` → ${esc(row.to)}` : ''}</dd></div><div><dt>分類</dt><dd>${categoryLabels(row)}</dd></div></dl><h3>仕訳</h3>${row.kind === 'pending' ? '<p class="ac-muted">回答待ちです。</p>' : journalTable([row])}${zaimDetails(row)}${bills.map(b => `<details open><summary>${esc(b.account)}・${esc(b.billingMonth)}請求の内訳</summary><p class="ac-muted">請求額 ${yen(b.total)}</p><div class="ac-scroll ac-bill-scroll"><table class="ac-table"><thead><tr><th>利用日</th><th>利用先</th><th class="ac-number">金額</th></tr></thead><tbody>${b.items.map(item => `<tr><td>${esc(item.date)}</td><td>${esc(item.memo)}</td><td class="ac-number">${yen(item.amount)}</td></tr>`).join('')}</tbody></table></div></details>`).join('')}<details><summary>出典・判断の根拠</summary><p class="ac-muted">${esc(row.status)}。${esc(sourceText(row.sources)) || 'Codexセッションで確認した精算記録。'}</p>${row.categoryBasis ? `<p class="ac-muted">${esc(row.categoryBasis)}</p>` : ''}${row.assumptions?.length ? `<ul class="ac-muted">${row.assumptions.map(note => `<li>${esc(note)}</li>`).join('')}</ul>` : ''}</details></div>`;
    dialog.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click',() => dialog.close()));
    dialog.showModal();
  }
  root.addEventListener('click',event => {
    const target = event.target.closest('[data-ac-action]'); if (!target) return;
    const action = target.dataset.acAction, value = target.dataset.value;
    if (action === 'edit') { viewer(value); return; }
    if (action === 'tab') { tab = value; drawerOpen = false; }
    if (action === 'book') book = value;
    if (action === 'scale') scale = value;
    if (action === 'privacy') {
      hideAmounts = !hideAmounts;
      try { window.localStorage.setItem(privacyStorageKey, String(hideAmounts)); }
      catch { /* 保存できない環境では、現在の画面内で切り替える。 */ }
    }
    if (action === 'remittance') excludeRemittance = !excludeRemittance;
    if (action === 'report') report = value;
    if (action === 'filter-kind') transactionKind = value;
    if (action === 'pl-filter' || action === 'home-filter') { tab = '帳簿'; book = '取引'; transactionKind = action === 'home-filter' ? 'expense' : target.dataset.kind; transactionCategory = value; }
    if (action === 'clear-filters') { transactionKind = ''; transactionCategory = ''; }
    if (action === 'day') { selectedDay = value; drawerOpen = true; }
    if (action === 'close-drawer') drawerOpen = false;
    if (action === 'month') { drawerOpen = false; const [y,m] = month.split('-').map(Number), d = new Date(y,m-1+Number(value)*(annual() ? 12 : 1),1); month = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`; selectedDay = month+'-01'; }
    if (action === 'reset-month') {
      drawerOpen = false;
      const today = new Date();
      month = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}`;
      selectedDay = `${month}-${String(today.getDate()).padStart(2,'0')}`;
    }
    render();
    if (action === 'month' && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      root.querySelector('#ac-content').animate([{opacity:0,transform:`translateX(${Number(value)*24}px)`},{opacity:1,transform:'translateX(0)'}],{duration:180,easing:'cubic-bezier(.2,.7,.3,1)'});
    }
    if (action === 'pl-filter' || action === 'home-filter') { root.querySelector('[data-ac-action="book"][data-value="取引"]')?.focus({preventScroll:true}); return; }
    if (action === 'close-drawer') { root.querySelector(`[data-ac-action="day"][data-value="${selectedDay}"]`)?.focus({preventScroll:true}); return; }
    const replacement = [...root.querySelectorAll('[data-ac-action]')].find(b => b.dataset.acAction === action && b.dataset.value === value);
    replacement?.focus({preventScroll:true});
  });
  root.addEventListener('change',event => {
    const filter = event.target.dataset.acFilter;
    if (filter === 'category') transactionCategory = event.target.value;
    else if (filter === 'sort' && ['date-asc','date-desc','amount-asc','amount-desc'].includes(event.target.value)) transactionSort = event.target.value;
    else return;
    render();
    root.querySelector(`[data-ac-filter="${filter}"]`)?.focus({preventScroll:true});
  });
  root.addEventListener('keydown',event => {
    if (!event.target.matches('.ac-pl-chart-category, .ac-home-chart-category') || !['Enter',' '].includes(event.key)) return;
    event.preventDefault();
    event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));
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
