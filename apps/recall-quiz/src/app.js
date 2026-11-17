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
  const stretchContent = document.querySelector('.stretch-content');
  let pullGesture = null, spring = null;
  let disclosureCleanups = [];
  let shopOpen = false;
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
      // Use a stretchable overbar instead of the spacing macron emitted for \bar.
      // Reserve a small gap so the bar does not touch italic capitals.
      if (node.localName === 'mo' && ['ˉ', '‾'].includes(node.textContent) &&
        node.parentElement?.localName === 'mover' && node.parentElement.getAttribute('accent') === 'true') {
        node.textContent = '‾';
        node.setAttribute('stretchy', 'true');
        node.setAttribute('class', 'math-overbar');
      }
      for (const attr of [...node.attributes]) {
        if (!(mathAttrs.has(attr.name) || (node.localName === 'span' && attr.name === 'class') ||
          (node.localName === 'mo' && attr.name === 'class' && attr.value === 'math-overbar'))) node.removeAttribute(attr.name);
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
  function animalImage(item, className = '') {
    return `<img class="${className}" src="${window.GARDEN_ASSETS[item.asset]}" alt="${escape(item.name)}" draggable="false">`;
  }
  function gardenLandscape() {
    return `<svg class="garden-landscape" viewBox="0 0 600 1100" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs><linearGradient id="garden-sky" x2="0" y2="1"><stop stop-color="#edc9b6"/><stop offset="1" stop-color="#fae9c9"/></linearGradient><linearGradient id="garden-water" x2="0" y2="1"><stop stop-color="#a3c3b7"/><stop offset="1" stop-color="#6b9d9b"/></linearGradient></defs>
      <path fill="url(#garden-sky)" d="M0 0h600v1100H0z"/><circle cx="445" cy="225" r="67" fill="#fff1c2"/>
      <path d="m0 330 90-99 75 80 69-109 129 152 71-60 75 22 91-94v315H0Z" fill="#b5a6ac"/>
      <path d="m165 311 69-109 39 112-36-19-18 28-15-45Z" fill="#e5d6cd"/><path d="m364 354 70-60 75 22 91-94v219H0V330l90-99 53 97-66-27 30 76Z" fill="#a79da4"/>
      <path d="m0 409 101-76 130 102 113-68 109 72 147-85v746H0Z" fill="#8d9e8b"/>
      <path d="m0 409 101-76-25 177 155-75 70 143 152-139 147-85v746H0Z" fill="#a7b692"/>
      <path d="m0 522 121-73 180 129 122-81 177 42v561H0Z" fill="#c1c49c"/>
      <path d="m0 522 121-73 37 156 143-27 122-81-10 194 187-152v561H0Z" fill="#b7be95"/>
      <path d="m0 633 158-28 106 108 149-22 187 46v363H0Z" fill="#ccd0a7"/>
      <path d="m0 633 158-28L67 797l197-84 34 184 115-206 187 46v363H0Z" fill="#b7c09a"/>
      <path d="m0 748 67-13 63 35 34 66-27 71-137 49Z" fill="#90afa4"/><path d="m0 763 70-8 49 35 26 49-23 53L0 936Z" fill="url(#garden-water)"/>
      <path d="m0 830 62-36 83 45-23 53L0 936Z" fill="#85aea6"/><path d="m12 840 32-5m16 18 46-8M5 882l68-12" fill="none" stroke="#d9e1c6" stroke-width="3" opacity=".6"/>
      <path d="m600 574-78 39-68 72-30 147-85 129-29 139h58l18-134 80-121 32-143 68-64 34-13Z" fill="#e4d6b4"/>
      <path d="m600 574-40 48-80 73-30 146-83 129-29 130h30l18-134 80-121 32-143 68-64 34-13Z" fill="#d6c9aa"/>
      <g fill="#677f70"><path d="m35 285-47 133h94Z"/><path d="m91 321-45 130h90Z"/><path d="m552 353-48 148h96Z"/></g>
      <g fill="#87987a"><path d="m35 285 10 133h37Z"/><path d="m91 321 3 130h42Z"/><path d="m552 353 9 148h39Z"/></g>
      <g stroke="#796f59" stroke-width="7"><path d="M35 413v30m56-3v23m461 24v30"/></g>
      <g><path d="m420 485 20-112 30 112Z" fill="#758d76"/><path d="m440 373 2 112h28Z" fill="#9cab83"/><path d="M440 480v18" stroke="#86765e" stroke-width="6"/></g>
      <g fill="#8d9c7c"><path d="m194 798 18-16 32 9 8 21-41 10Z"/><path d="m473 917 22-22 35 9 12 29-45 11Z"/></g>
      <g fill="#c6c1a5"><path d="m27 665 13-20 27 5 13 19-33 12Z"/><path d="m490 752 19-13 22 5 7 21-35 3Z"/></g>
      <g fill="#e9d7b1"><path d="m27 665 13-20 11 18Z"/><path d="m490 752 19-13 8 17Z"/></g>
      <g fill="#efdfb7"><circle cx="220" cy="642" r="3"/><circle cx="233" cy="648" r="2"/><circle cx="216" cy="655" r="2"/><circle cx="509" cy="846" r="3"/><circle cx="524" cy="849" r="2"/></g>
    </svg>`;
  }
  function sourceToggles(q) {
    return q.sources.map(source => source.imageKey && deck.sourceImages && deck.sourceImages[source.imageKey] ?
      `<details class="source-toggle" data-source="${escape(source.imageKey)}" data-scale="100"><summary>原典を見る（p.${source.page}）</summary><p class="source-caption">${escape(source.file)} · p.${source.page}</p><div class="source-zoom-controls"><button type="button" data-zoom="-25" aria-label="原典を縮小（p.${source.page}）">−</button><input type="range" min="50" max="300" step="25" value="100" aria-label="原典の表示倍率（p.${source.page}）"><button type="button" data-zoom="25" aria-label="原典を拡大（p.${source.page}）">＋</button><output>100%</output><button type="button" data-zoom="reset">全体</button></div><div class="source-viewport"><img alt="${escape(source.file)} p.${source.page} の原典ページ"></div><p class="helper">拡大後は画像内を上下左右にスクロールできます。</p></details>` : '').join('');
  }
  function renderQuiz() {
    const s = state.session;
    if (!s || s.closed || s.index >= s.queue.length) {
      const count = s ? s.index : 0;
      content.innerHTML = `<p class="eyebrow">A LITTLE RECALL, EVERY DAY</p><h1 class="page-title">${count ? '今日は、ここまででも。' : 'いまは、ひと休み。'}</h1><p class="lead">${count ? `${count}回の想起を記録しました。<br>また少し時間を空けて、思い出そう。` : 'いま出す問題はありません。<br>新しい教材や、別の日の復習でまた会おう。'}</p><div class="stack"><button class="primary" data-action="start">あと3問</button></div><p class="helper center">休んでも、コインや動物はなくなりません。</p>`;
      content.querySelector('[data-action="start"]').disabled = RecallCore.select(state, deck, new Date()).length === 0;
      return;
    }
    const q = deck.questions.find(q => q.id === s.queue[s.index].id);
    content.innerHTML = `<p class="eyebrow">${escape(deck.title)}</p><p class="course">${escape(deck.subtitle || '')}</p><div class="question-head"><span class="step">${s.index + 1} / ${s.queue.length} 問</span><span class="dots" aria-hidden="true">${s.queue.map((_, i) => `<i class="${i < s.index ? 'done' : i === s.index ? 'current' : ''}"></i>`).join('')}</span></div><h1 class="question math-text">${text(q, 'prompt')}</h1>${s.answerShown ? `<div class="answer-reveal"><section class="answer"><p class="label">ANSWER</p><div class="answer-main math-text">${text(q, 'answer')}</div><div class="criterion math-text">${text(q, 'criterion')}</div><details><summary>補足と出典</summary><div class="math-text">${text(q, 'explanation')}</div><div class="sources">${q.sources.map(s => `${escape(s.file)} · p.${s.page}`).join('<br>')}</div></details></section><p class="reward-hint">どちらを押しても ＋1コイン</p><div class="ratings"><button class="secondary" data-result="again">出なかった</button><button class="primary" data-result="good">思い出せた</button></div><p class="helper center">読んで納得しただけなら「出なかった」でOK。</p></div>` : '<p class="helper">頭の中で答えるだけ。わからなければ、すぐ見よう。</p><button class="primary" data-action="reveal">答えを見る</button>'}<div class="center"><button class="quiet" data-action="finish">今日はここまで</button></div>`;
  }
  function renderGarden() {
    const residents = boot.shop.filter(item => state.garden.items.includes(item.id));
    content.innerHTML = `<section class="garden-stage" aria-label="動物たちの庭">${gardenLandscape()}<div class="garden-caption"><p class="eyebrow">LITTLE WILD GARDEN</p><h1>ひとつの庭</h1><p>${residents.length ? `${residents.length}匹が、のんびり暮らしています。` : '学んだぶんだけ、仲間が増えていく。'}</p></div><div class="garden-residents">${residents.map(item => `<button class="garden-animal animal-${item.asset}" aria-label="${escape(item.name)}に声をかける"><span class="animal-shadow"></span><span class="animal-roam"><span class="animal-body">${animalImage(item)}</span></span><span class="animal-name">${escape(item.name)}</span></button>`).join('')}</div>${!residents.length ? '<div class="garden-invitation"><span class="invitation-line"></span><p>最初の仲間を、迎えよう。</p><small>右下のショップで出会えます。</small></div>' : ''}<button class="open-garden-shop" aria-haspopup="dialog"><svg viewBox="0 0 32 32" aria-hidden="true"><path d="M6 12h20l-2 16H8ZM11 12V9a5 5 0 0 1 10 0v3"/></svg><span>ショップ</span></button><p class="garden-tip">${residents.length ? '動物にタッチしてみよう。' : 'クイズの答え合わせ1回で、1コイン。'}</p></section><dialog class="garden-shop" aria-labelledby="garden-shop-title"><div class="shop-sheet"><div class="shop-grip" aria-hidden="true"></div><div class="garden-shop-header"><div><p class="eyebrow">WELCOME A LITTLE FRIEND</p><h2 id="garden-shop-title">庭の仲間を迎える</h2></div><button class="close-garden-shop" aria-label="ショップを閉じる">×</button></div><p class="shop-balance"><span class="coin-dot"></span> ${state.garden.coins} <span>コイン</span></p><div class="animal-shop-list">${boot.shop.map(item => {
      const owned = state.garden.items.includes(item.id);
      const short = Math.max(0, item.cost - state.garden.coins);
      return `<article class="animal-shop-card">${animalImage(item, 'shop-animal-image')}<div class="animal-shop-info"><h3>${escape(item.name)}</h3><p>${escape(item.description)}</p><button data-buy="${item.id}" ${owned || short ? 'disabled' : ''}>${owned ? 'お迎え済み' : `${item.cost} コイン`}</button>${!owned && short ? `<small>あと${short}コイン</small>` : ''}</div></article>`;
    }).join('')}</div><p class="shop-footnote">答え合わせ1回で1コイン。正解でもミスでも増えます。</p></div></dialog>`;
  }
  function setupGardenShop() {
    const dialog = content.querySelector('.garden-shop');
    if (!dialog) return;
    const sheet = dialog.querySelector('.shop-sheet');
    const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    content.querySelector('.open-garden-shop').onclick = () => {
      shopOpen = true;
      dialog.inert = false;
      dialog.showModal();
      if (!reduced()) sheet.animate([{ transform: 'translateY(100%)' }, { transform: 'translateY(0)' }], {
        duration: 320, easing: 'cubic-bezier(.2,.7,.2,1)'
      });
    };
    async function closeShop() {
      if (dialog.dataset.closing) return;
      dialog.dataset.closing = 'true';
      dialog.inert = true;
      if (!reduced()) await sheet.animate([{ transform: 'translateY(0)' }, { transform: 'translateY(100%)' }], {
        duration: 220, easing: 'ease-in', fill: 'forwards'
      }).finished;
      shopOpen = false;
      dialog.close();
      dialog.inert = false;
      delete dialog.dataset.closing;
      sheet.getAnimations().forEach(animation => animation.cancel());
    }
    dialog.querySelector('.close-garden-shop').onclick = closeShop;
    dialog.addEventListener('cancel', event => { event.preventDefault(); closeShop(); });
    dialog.addEventListener('click', event => { if (event.target === dialog) closeShop(); });
    content.querySelectorAll('.garden-animal').forEach(animal => animal.onclick = () => {
      animal.classList.remove('says-hello');
      void animal.offsetWidth;
      animal.classList.add('says-hello');
    });
    if (shopOpen) dialog.showModal();
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
  function slideDisclosures() {
    for (const details of content.querySelectorAll('details')) {
      const summary = details.querySelector(':scope > summary');
      if (!summary) continue;
      const body = document.createElement('div');
      body.className = 'disclosure-body';
      const inner = document.createElement('div');
      inner.className = 'disclosure-content';
      for (const node of [...details.childNodes]) if (node !== summary) inner.appendChild(node);
      body.appendChild(inner);
      details.appendChild(body);
      let expanded = details.open, animation = null;
      function slide(open) {
        const from = details.open ? body.getBoundingClientRect().height : 0;
        if (animation) animation.cancel();
        animation = null;
        expanded = open;
        summary.setAttribute('aria-expanded', String(open));
        body.inert = !open;
        details.open = true;
        const to = open ? inner.getBoundingClientRect().height : 0;
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !body.animate || Math.abs(from - to) < 1) {
          details.open = open;
          updateScrollFade();
          return;
        }
        const active = body.animate([{ height: `${from}px` }, { height: `${to}px` }], {
          duration: 280, easing: 'cubic-bezier(.2,.7,.2,1)', fill: 'both'
        });
        animation = active;
        active.onfinish = () => {
          if (animation !== active) return;
          animation = null;
          details.open = open;
          active.cancel();
          updateScrollFade();
        };
      }
      summary.setAttribute('aria-expanded', String(expanded));
      summary.addEventListener('click', event => {
        if (event.target.closest('a, button, input, select')) return;
        event.preventDefault();
        slide(!expanded);
      });
      const observer = window.ResizeObserver ? new ResizeObserver(() => {
        if (animation && expanded) slide(true);
      }) : null;
      if (observer) observer.observe(inner);
      disclosureCleanups.push(() => { if (animation) animation.cancel(); if (observer) observer.disconnect(); });
    }
  }
  function releasePull(animate = true) {
    pullGesture = null;
    const transform = stretchContent.style.transform;
    if (spring) spring.cancel();
    spring = null;
    stretchContent.style.transform = '';
    if (animate && transform && stretchContent.animate && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      spring = stretchContent.animate([
        { transform }, { transform: 'scaleY(.995)', offset: .65 }, { transform: 'scaleY(1)' }
      ], { duration: 420, easing: 'cubic-bezier(.2,.75,.25,1)' });
      spring.onfinish = () => { spring = null; updateScrollFade(); };
    }
    updateScrollFade();
  }
  function startPull(event) {
    releasePull(false);
    if (event.touches.length !== 1 || window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
      scrollRegion.scrollHeight <= scrollRegion.clientHeight + 1) return;
    // Leave independently scrollable PDF images, formulas and form controls alone.
    for (let node = event.target; node && node !== scrollRegion; node = node.parentElement) {
      if (node.matches('input, select, textarea') ||
        ((node.scrollHeight > node.clientHeight + 1 || node.scrollWidth > node.clientWidth + 1) &&
          /auto|scroll/.test(getComputedStyle(node).overflow))) return;
    }
    const touch = event.touches[0];
    pullGesture = { x: touch.clientX, y: touch.clientY, lastY: touch.clientY,
      limit: scrollRegion.scrollHeight - scrollRegion.clientHeight, edge: null, originY: touch.clientY };
  }
  function movePull(event) {
    if (!pullGesture) return;
    if (event.touches.length !== 1) { releasePull(false); return; }
    const touch = event.touches[0], gesture = pullGesture;
    if (Math.abs(touch.clientX - gesture.x) > Math.abs(touch.clientY - gesture.y)) { releasePull(); return; }
    const dy = touch.clientY - gesture.lastY;
    const edge = scrollRegion.scrollTop <= 1 && dy > 0 ? 'top' :
      scrollRegion.scrollTop >= gesture.limit - 1 && dy < 0 ? 'bottom' : null;
    if (!gesture.edge && edge) {
      gesture.edge = edge;
      gesture.originY = gesture.lastY;
      stretchContent.style.transformOrigin = edge === 'top' ? 'center top' : 'center bottom';
    }
    gesture.lastY = touch.clientY;
    if (!gesture.edge) return;
    const distance = (touch.clientY - gesture.originY) * (gesture.edge === 'top' ? 1 : -1);
    if (distance <= 0) { releasePull(); return; }
    if (event.cancelable) event.preventDefault();
    // Increasing resistance keeps even a long pull within a small visual stretch.
    const stretch = 54 * (1 - Math.exp(-distance / 160));
    stretchContent.style.transform = `scaleY(${1 + stretch / scrollRegion.clientHeight})`;
  }
  function updateScrollFade() {
    scrollRegion.classList.toggle('has-more-above', scrollRegion.scrollTop > 1);
    scrollRegion.classList.toggle('has-more-below', scrollRegion.scrollHeight - scrollRegion.clientHeight - scrollRegion.scrollTop > 1);
  }
  function render() {
    document.body.classList.toggle('garden-mode', page === 'garden');
    if (page !== 'garden') shopOpen = false;
    disclosureCleanups.forEach(dispose => dispose());
    disclosureCleanups = [];
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
      const answerReveal = page === 'quiz' && !changedPage ? content.querySelector('.answer-reveal') : null;
      if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && content.animate) {
        if (answerReveal) {
          answerReveal.animate([{ height: '0px' }, { height: `${answerReveal.scrollHeight}px` }], {
            duration: 300, easing: 'cubic-bezier(.2,.7,.2,1)'
          });
        } else {
          const order = ['quiz', 'calendar', 'garden', 'catalog', 'settings'];
          const direction = order.indexOf(page) >= order.indexOf(renderedPage) ? 1 : -1;
          content.animate([
            { opacity: 0, transform: changedPage ? `translateX(${direction * 18}px)` : 'translateY(10px)' },
            { opacity: 1, transform: 'translate(0, 0)' }
          ], { duration: changedPage ? 320 : 220, easing: 'cubic-bezier(.2,.7,.2,1)' });
        }
      }
      releasePull(false);
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
    setupGardenShop();
    slideDisclosures();
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
    updateScrollFade();
    content.querySelectorAll('[data-result]').forEach(b => b.onclick = () => act('rate', {
      eventId: `${state.session.id}:${state.session.index}`, result: b.dataset.result
    }));
  }
  scrollRegion.addEventListener('touchstart', startPull, { passive: true });
  scrollRegion.addEventListener('touchmove', movePull, { passive: false });
  scrollRegion.addEventListener('touchend', () => releasePull());
  scrollRegion.addEventListener('touchcancel', () => releasePull());
  scrollRegion.addEventListener('scroll', updateScrollFade, { passive: true });
  scrollRegion.addEventListener('toggle', updateScrollFade, true);
  window.addEventListener('resize', () => { releasePull(false); updateScrollFade(); });
  if (window.ResizeObserver) {
    const observer = new ResizeObserver(updateScrollFade);
    observer.observe(scrollRegion);
    observer.observe(content);
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
