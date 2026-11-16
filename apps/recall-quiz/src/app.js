(() => {
  const boot = window.BOOT;
  const initialPage = !boot.native ? new URLSearchParams(location.search).get('screen') : null;
  let state = boot.state, deck = boot.deck, page = ['garden', 'settings', 'calendar', 'catalog'].includes(initialPage) ? initialPage : 'quiz', busy = false, serial = 0;
  let decks = boot.decks || [deck];
  let month = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  let selectedDay = RecallCore.day(new Date()), subject = '';
  let renderedKey = '', renderedPage = page;
  const content = document.querySelector('#content');
  const scrollRegion = document.querySelector('.scroll-region');
  const status = document.querySelector('#status');
  const queue = [], pending = new Map();
  let nativeWaiter = null;
  const escape = text => String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const allowedMath = new Set('span math semantics mrow mi mn mo mtext mspace mfrac msqrt mroot msup msub msubsup mover munder munderover mtable mtr mtd menclose mpadded mstyle mphantom annotation'.split(' '));
  const mathAttrs = new Set('xmlns display mathvariant stretchy fence separator accent accentunder largeop movablelimits lspace rspace width height depth columnalign rowalign columnspacing rowspacing notation encoding scriptlevel displaystyle'.split(' '));
  function safeMath(markup) {
    const template = document.createElement('template');
    template.innerHTML = markup;
    for (const node of [...template.content.querySelectorAll('*')]) {
      if (!allowedMath.has(node.localName)) { node.replaceWith(document.createTextNode(node.textContent)); continue; }
      for (const attr of [...node.attributes]) {
        if (!(mathAttrs.has(attr.name) || (node.localName === 'span' && attr.name === 'class'))) node.removeAttribute(attr.name);
      }
    }
    return template.innerHTML;
  }
  const text = (q, name) => q[`${name}Html`] ? safeMath(q[`${name}Html`]) : escape(q[name]);
  window.takeNativeCommand = callback => {
    if (queue.length) callback(queue.shift());
    else nativeWaiter = callback;
  };
  window.resolveNativeCommand = (id, response) => {
    const resolve = pending.get(id);
    if (resolve) { pending.delete(id); resolve(response); }
  };
  async function call(action, payload) {
    if (!boot.native) {
      if (action === 'export') {
        const url = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' }));
        const link = document.createElement('a'); link.href = url; link.download = 'recall-quiz-preview-state.json'; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        return { ok: true, state, deck, message: 'PCプレビューの記録を書き出しました。' };
      }
      if (['importDeck', 'importState', 'testNotification', 'settings'].includes(action)) {
        throw Error('通知・読み込みの実機操作は、iPhoneのScriptable版で使えます。');
      }
      if (action === 'selectDeck') {
        const selected = decks.find(item => item.id === payload.id);
        if (!selected) throw Error('教材が見つかりません。');
        if (selected.id !== deck.id) state = RecallCore.start(state, selected, new Date());
        deck = selected;
        localStorage.setItem('recall-quiz-preview-deck', deck.id);
        localStorage.setItem('recall-quiz-preview-v1', JSON.stringify(state));
        return { ok: true, state, deck, decks };
      }
      const next = RecallCore.dispatch(state, deck, action, payload);
      localStorage.setItem('recall-quiz-preview-v1', JSON.stringify(next));
      return { ok: true, state: next, deck, message: '' };
    }
    return new Promise(resolve => {
      const command = { id: String(++serial), action, payload };
      pending.set(command.id, resolve);
      if (nativeWaiter) { const waiter = nativeWaiter; nativeWaiter = null; waiter(command); }
      else queue.push(command);
    });
  }
  async function act(action, payload = {}) {
    if (busy) return;
    busy = true;
    status.textContent = '保存・処理中…';
    document.querySelectorAll('header button, .main-nav button, #content button').forEach(b => { b.disabled = true; });
    const slow = setTimeout(() => {
      status.textContent = '処理を待っています。反応が戻らない場合は、一度閉じて開き直してください。';
    }, 15000);
    try {
      const result = await call(action, payload);
      if (!result.ok) throw Error(result.error);
      state = result.state;
      if (result.deck) deck = result.deck;
      if (result.decks) decks = result.decks;
      if (['start', 'importDeck', 'importState', 'selectDeck'].includes(action)) page = 'quiz';
      status.textContent = result.message || (action === 'rate' ? '＋1コイン。思い出そうとした1回を記録しました。' : '');
    } catch (error) {
      status.textContent = String(error.message || error);
    } finally {
      clearTimeout(slow);
      busy = false;
      render();
    }
  }
  function scene() {
    return `<div class="garden" aria-label="あなたの小さな庭"><div class="sun"></div><div class="hill back"></div><div class="hill"></div><div class="plants">${state.garden.items.length ? state.garden.items.map(id => `<span>${boot.shop.find(i => i.id === id).icon}</span>`).join('') : '<span class="empty-garden">ここに、少しずつ育てよう。</span>'}</div></div>`;
  }
  function sourceToggles(q) {
    return q.sources.map(source => source.imageKey && deck.sourceImages && deck.sourceImages[source.imageKey] ?
      `<details class="source-toggle" data-source="${escape(source.imageKey)}" data-scale="100"><summary>原典を見る（p.${source.page}）</summary><p class="source-caption">${escape(source.file)} · p.${source.page}</p><div class="source-zoom-controls"><button type="button" data-zoom="-25" aria-label="原典を縮小（p.${source.page}）">−</button><input type="range" min="50" max="300" step="25" value="100" aria-label="原典の表示倍率（p.${source.page}）"><button type="button" data-zoom="25" aria-label="原典を拡大（p.${source.page}）">＋</button><output>100%</output><button type="button" data-zoom="reset">全体</button></div><div class="source-viewport"><img alt="${escape(source.file)} p.${source.page} の原典ページ"></div><p class="helper">拡大後は画像内を上下左右にスクロールできます。</p></details>` : '').join('');
  }
  function renderQuiz() {
    const s = state.session;
    if (!s || s.closed || s.index >= s.queue.length) {
      const count = s ? s.index : 0;
      content.innerHTML = `<p class="eyebrow">A LITTLE RECALL, EVERY DAY</p><h1 class="page-title">${count ? '今日は、ここまででも。' : 'いまは、ひと休み。'}</h1><p class="lead">${count ? `${count}回の想起を記録しました。<br>また少し時間を空けて、思い出そう。` : 'いま出す問題はありません。<br>新しい教材や、別の日の復習でまた会おう。'}</p>${scene()}<div class="stack"><button class="primary" data-action="start">あと3問</button></div><p class="helper center">休んでも、コインや植物はなくなりません。</p>`;
      content.querySelector('[data-action="start"]').disabled = RecallCore.select(state, deck, new Date()).length === 0;
      return;
    }
    const q = deck.questions.find(q => q.id === s.queue[s.index].id);
    content.innerHTML = `<p class="eyebrow">${escape(deck.title)}</p><p class="course">${escape(deck.subtitle || '')}</p><div class="question-head"><span class="step">${s.index + 1} / ${s.queue.length} 問</span><span class="dots" aria-hidden="true">${s.queue.map((_, i) => `<i class="${i < s.index ? 'done' : i === s.index ? 'current' : ''}"></i>`).join('')}</span></div><h1 class="question math-text">${text(q, 'prompt')}</h1>${s.answerShown ? `<section class="answer"><p class="label">ANSWER</p><div class="answer-main math-text">${text(q, 'answer')}</div><div class="criterion math-text">${text(q, 'criterion')}</div><details><summary>補足と出典</summary><div class="math-text">${text(q, 'explanation')}</div><div class="sources">${q.sources.map(s => `${escape(s.file)} · p.${s.page}`).join('<br>')}</div></details></section><p class="reward-hint">どちらを押しても ＋1コイン</p><div class="ratings"><button class="secondary" data-result="again">出なかった</button><button class="primary" data-result="good">思い出せた</button></div><p class="helper center">読んで納得しただけなら「出なかった」でOK。</p>` : '<p class="helper">頭の中で答えるだけ。わからなければ、すぐ見よう。</p><button class="primary" data-action="reveal">答えを見る</button>'}<div class="center"><button class="quiet" data-action="finish">今日はここまで</button></div>`;
  }
  function renderGarden() {
    content.innerHTML = `<p class="eyebrow">YOUR LITTLE GARDEN</p><h1 class="page-title">想起のあとに、小さな庭。</h1><p class="lead">正解でも、出なかった日でも。<br>ひとつ取り組むたびに、1コイン。</p>${scene()}<div class="shop">${boot.shop.map(item => `<div class="shop-item"><div><span class="plant">${item.icon}</span>${item.name}</div><button data-buy="${item.id}" ${state.garden.items.includes(item.id) || state.garden.coins < item.cost ? 'disabled' : ''}>${state.garden.items.includes(item.id) ? '庭にいます' : `${item.cost} コイン`}</button></div>`).join('')}</div>`;
  }
  function renderSettings() {
    const settings = state.settings;
    content.innerHTML = `<p class="eyebrow">MAKE IT EASY TO RETURN</p><h1 class="page-title">自分のペースで。</h1>${!boot.native ? '<p class="badge">PCプレビュー · iPhoneの記録とは別です</p>' : ''}<form id="settings-form" class="panel"><label class="field">昼の通知<input id="notify" type="checkbox" ${settings.notificationEnabled ? 'checked' : ''}></label><label class="field">通知する時刻<input id="notify-time" type="time" value="${settings.notificationTime}" required></label><p class="helper">1日1回、追撃なし。夜のバイト中を避けた時刻に。</p><label class="field">iCloudへ記録をバックアップ<input id="cloud" type="checkbox" ${settings.iCloudBackup ? 'checked' : ''}></label><p class="helper">本体保存の後にコピーします。初期値はOFF。端末間の即時同期ではありません。</p><button class="primary" type="submit" ${boot.native ? '' : 'disabled'}>設定を保存</button></form><div class="stack"><button class="secondary" data-action="testNotification" ${boot.native ? '' : 'disabled'}>1分後の通知をテスト</button><button class="secondary" data-action="importDeck" ${boot.native ? '' : 'disabled'}>教材を読み込む</button><button class="secondary" data-action="export">学習記録を書き出す</button><button class="secondary" data-action="importState" ${boot.native ? '' : 'disabled'}>学習記録を復元する</button></div><p class="helper">教材：${escape(deck.subtitle || deck.title)}、${deck.questions.length}問。復習の間隔は初版では1・3・7・14・30日。誤答は翌日と、他の問題を挟んだ当日の再確認候補になります。同日だけの成功で間隔は延びません。</p><p class="helper">出題は短い区切りです。試験の計算演習も別に確認してください。</p>`;
    document.querySelector('#settings-form').onsubmit = event => {
      event.preventDefault();
      act('settings', {
        notificationEnabled: document.querySelector('#notify').checked,
        notificationTime: document.querySelector('#notify-time').value,
        iCloudBackup: document.querySelector('#cloud').checked
      });
    };
  }
  function renderCalendar() {
    const stats = RecallCore.statistics(state);
    const year = month.getFullYear(), m = month.getMonth();
    const count = new Date(year, m + 1, 0).getDate();
    let cells = '<span class="calendar-blank" aria-hidden="true"></span>'.repeat(month.getDay());
    let total = 0, activeDays = 0;
    for (let date = 1; date <= count; date++) {
      const key = RecallCore.day(new Date(year, m, date));
      const answers = stats.days[key] || 0;
      total += answers;
      if (answers) activeDays++;
      cells += `<button class="calendar-day ${answers ? 'has-answers' : ''} ${key === RecallCore.day(new Date()) ? 'is-today' : ''}" data-day="${key}" aria-pressed="${key === selectedDay}" aria-label="${year}年${m + 1}月${date}日、${answers}回答"><span>${date}</span><small>${answers ? `${answers}回` : '·'}</small></button>`;
    }
    const [sy, sm, sd] = selectedDay.split('-');
    content.innerHTML = `<h1 class="page-title">学習カレンダー</h1><p class="lead">答え合わせを終えた回数を記録します。同じ問題の復習も1回に数えます。</p><section class="panel"><div class="month-nav"><button data-month="-1" aria-label="前の月">‹</button><h2>${year}年${m + 1}月</h2><button data-month="1" aria-label="次の月">›</button></div><div class="calendar-grid">${['日', '月', '火', '水', '木', '金', '土'].map(d => `<span class="weekday">${d}</span>`).join('')}${cells}</div><div class="month-total"><span>この月の回答 <strong>${total}回</strong></span><span>学習した日 <strong>${activeDays}日</strong></span></div><button class="quiet" data-today>今月に戻る</button></section><section class="panel day-detail"><h2>${sy}年${sm}月${sd}日</h2><p class="day-count">${stats.days[selectedDay] || 0}<span>回回答</span></p></section>`;
  }
  function resultCounts(n) {
    return `<span class="count-presented" aria-label="出題${n.presented}回">出題 <strong>${n.presented}</strong></span><span class="result-badge correct" aria-label="正解${n.correct}回"><span class="result-symbol" aria-hidden="true">○</span><strong aria-hidden="true">${n.correct}</strong></span><span class="result-badge mistake" aria-label="ミス${n.mistakes}回"><span class="result-symbol" aria-hidden="true">×</span><strong aria-hidden="true">${n.mistakes}</strong></span>`;
  }
  function renderCatalog() {
    const stats = RecallCore.statistics(state);
    const subjects = [...new Set(decks.map(item => item.title))];
    if (!subjects.includes(subject)) subject = subjects[0];
    const items = decks.filter(item => item.title === subject);
    content.innerHTML = `<h1 class="page-title">クイズ一覧</h1><label class="subject-field">教科<select id="subject" aria-label="教科">${subjects.map(title => `<option ${title === subject ? 'selected' : ''}>${escape(title)}</option>`).join('')}</select></label><p class="helper">○は正解、×はミス。問題を押すと解答が開きます。</p><details class="count-note"><summary>回数の数え方</summary>出題は問題を開いた回数です。旧版での回答も含みます。更新前の未回答の出題は記録されていません。</details>${items.map(item => {
      const rows = item.questions.map((q, index) => {
        const n = RecallCore.questionStatistics(stats, item.id, q.id);
        return `<details class="catalog-question"><summary><span class="question-number">${index + 1}</span><span class="catalog-prompt math-text">${text(q, 'prompt')}</span><span class="question-counts">${resultCounts(n)}</span></summary><div class="catalog-answer"><p class="label">解答</p><div class="math-text">${text(q, 'answer')}</div><p class="criterion math-text">${text(q, 'criterion')}</p></div></details>`;
      }).join('');
      const retired = Object.entries(stats.questions).filter(([key]) => {
        const [deckId, questionId] = JSON.parse(key);
        return deckId === item.id && !item.questions.some(q => q.id === questionId);
      }).map(([key, n]) => `<div class="retired-question"><p>旧版の問題 <small>${escape(JSON.parse(key)[1])}</small></p><div class="question-counts">${resultCounts(n)}</div></div>`).join('');
      return `<section class="lesson"><div class="lesson-head"><div><h2>${escape(item.subtitle || item.title)}</h2><p class="helper">${item.questions.length}問${item.id === deck.id ? ' · 選択中' : ''}</p></div>${item.id === deck.id ? '' : `<button class="lesson-start" data-deck="${escape(item.id)}">この教材で学習</button>`}</div>${rows}${retired ? `<details><summary>更新で除かれた問題の記録</summary>${retired}</details>` : ''}</section>`;
    }).join('')}`;
  }
  function render() {
    if (!boot.native && /^https?:$/.test(location.protocol)) {
      const url = new URL(location.href);
      url.searchParams.set('screen', page);
      history.replaceState(null, '', url);
    }
    document.querySelector('#coins').innerHTML = `<span class="coin-dot" aria-hidden="true"></span>${state.garden.coins}`;
    document.querySelectorAll('header button, .main-nav button').forEach(b => { b.disabled = busy; });
    document.querySelectorAll('[data-screen]').forEach(button => button.setAttribute('aria-current', button.dataset.screen === page ? 'page' : 'false'));
    if (page === 'calendar') renderCalendar();
    else if (page === 'catalog') renderCatalog();
    else if (page === 'garden') renderGarden();
    else if (page === 'settings') renderSettings();
    else renderQuiz();
    if (page === 'quiz' && state.session && state.session.answerShown) {
      const current = state.session.queue[state.session.index];
      const q = current && deck.questions.find(q => q.id === current.id);
      if (q) {
        const section = content.querySelector('.answer');
        if (section) section.insertAdjacentHTML('beforeend', `<div class="source-toggles">${sourceToggles(q)}</div>`);
      }
    }
    const key = `${page}:${state.session?.id}:${state.session?.index}:${state.session?.answerShown}`;
    if (key !== renderedKey) {
      const changedPage = page !== renderedPage;
      if (content.getAnimations) content.getAnimations().forEach(animation => animation.cancel());
      if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && content.animate) {
        const order = ['quiz', 'calendar', 'garden', 'catalog', 'settings'];
        const direction = order.indexOf(page) >= order.indexOf(renderedPage) ? 1 : -1;
        content.animate([
          { opacity: 0, transform: changedPage ? `translateX(${direction * 18}px)` : 'translateY(10px)' },
          { opacity: 1, transform: 'translate(0, 0)' }
        ], { duration: changedPage ? 320 : 220, easing: 'cubic-bezier(.2,.7,.2,1)' });
      }
      scrollRegion.scrollTop = 0;
      renderedKey = key;
      renderedPage = page;
    }
    content.querySelectorAll('.source-toggle').forEach(toggle => {
      const image = toggle.querySelector('img');
      const slider = toggle.querySelector('input');
      function zoom(value) {
        const scale = Math.max(50, Math.min(300, value));
        toggle.dataset.scale = String(scale);
        image.style.width = `${scale}%`;
        slider.value = String(scale);
        toggle.querySelector('output').textContent = `${scale}%`;
        toggle.querySelector('[data-zoom="-25"]').disabled = scale === 50;
        toggle.querySelector('[data-zoom="25"]').disabled = scale === 300;
      }
      toggle.addEventListener('toggle', () => {
        if (!toggle.open) { image.removeAttribute('src'); return; }
        const url = deck.sourceImages[toggle.dataset.source];
        if (/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(url || '')) image.src = url;
      });
      slider.oninput = () => zoom(Number(slider.value));
      toggle.querySelectorAll('[data-zoom]').forEach(button => button.onclick = () => {
        const scale = button.dataset.zoom === 'reset' ? 100 : Number(toggle.dataset.scale) + Number(button.dataset.zoom);
        zoom(scale);
      });
    });
    content.querySelectorAll('[data-month]').forEach(button => button.onclick = () => {
      month = new Date(month.getFullYear(), month.getMonth() + Number(button.dataset.month), 1);
      selectedDay = RecallCore.day(month);
      render();
    });
    content.querySelectorAll('[data-day]').forEach(button => button.onclick = () => { selectedDay = button.dataset.day; render(); });
    const today = content.querySelector('[data-today]');
    if (today) today.onclick = () => { month = new Date(new Date().getFullYear(), new Date().getMonth(), 1); selectedDay = RecallCore.day(new Date()); render(); };
    const filter = content.querySelector('#subject');
    if (filter) filter.onchange = () => { subject = filter.value; render(); };
    content.querySelectorAll('[data-deck]').forEach(button => button.onclick = () => act('selectDeck', { id: button.dataset.deck }));
    content.querySelectorAll('[data-action]').forEach(b => b.onclick = () => act(b.dataset.action));
    content.querySelectorAll('[data-buy]').forEach(b => b.onclick = () => act('buy', { id: b.dataset.buy }));
    content.querySelectorAll('[data-result]').forEach(b => b.onclick = () => act('rate', {
      eventId: `${state.session.id}:${state.session.index}`, result: b.dataset.result
    }));
  }
  document.querySelectorAll('[data-screen]').forEach(button => button.onclick = () => { page = button.dataset.screen; status.textContent = ''; render(); });
  document.querySelector('#home').onclick = () => { page = 'quiz'; render(); };
  document.querySelector('#settings-nav').onclick = () => { page = 'settings'; render(); };
  if (!boot.native) {
    try {
      const selected = localStorage.getItem('recall-quiz-preview-deck');
      deck = decks.find(item => item.id === selected) || deck;
      const saved = localStorage.getItem('recall-quiz-preview-v1');
      state = RecallCore.ensureSession(saved ? RecallCore.validateState(JSON.parse(saved)) : state, deck, new Date());
    } catch (error) { status.textContent = 'PCプレビューの保存を利用できません。iPhone版は別のファイル保存です。'; }
  }
  if (boot.notice) {
    const notice = document.querySelector('#notice'); notice.textContent = boot.notice; notice.hidden = false;
  }
  render();
})();
