(() => {
  const boot = window.BOOT;
  const runtime = window.RecallRuntime;
  const initialPage = new URLSearchParams(location.search).get('screen');
  let state = boot.state, deck = boot.deck, page = ['garden', 'settings', 'calendar', 'catalog', 'history'].includes(initialPage) ? initialPage : 'quiz', busy = false;
  let decks = boot.decks || [deck];
  let month = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  let selectedDay = RecallCore.day(new Date()), subject = new URLSearchParams(location.search).get('subject') || '';
  let catalogLesson = new URLSearchParams(location.search).get('lesson') || '';
  let historyPage = Math.max(1, parseInt(new URLSearchParams(location.search).get('historyPage'), 10) || 1);
  const requestedStudyType = new URLSearchParams(location.search).get('studyType');
  let studyType = ['knowledge', 'exercise'].includes(requestedStudyType) ? requestedStudyType :
    boot.decks.find(item => item.id === catalogLesson)?.studyType ||
    (page === 'quiz' && boot.state.session?.mode === 'exercise' ? 'exercise' : 'knowledge');
  let studySubject = boot.decks[0].title;
  const availableDecks = () => decks.filter(item => (item.studyType || 'knowledge') === studyType);
  const modeTabs = () => `<div class="study-tabs" aria-label="問題の種類">${[['knowledge', '用語・知識'], ['exercise', '演習問題']].map(([mode, label]) => `<button data-study-type="${mode}" aria-pressed="${studyType === mode}">${label}</button>`).join('')}</div>`;
  const historyReviews = () => state.reviews.filter(review => (review.studyType || decks.find(item => item.id === review.deckId)?.studyType || 'knowledge') === studyType);
  const catalogErrors = new Map();
  let quizTimer = null, countdown = null;
  let renderedKey = '', renderedPage = page, renderedHistoryPage = historyPage;
  const catalogRequests = new Map();
  const content = document.querySelector('#content');
  const quizControls = document.querySelector('#quiz-controls');
  const scrollRegion = document.querySelector('.scroll-region');
  const stretchContent = document.querySelector('.stretch-content');
  let pullGesture = null, spring = null;
  let disclosureCleanups = [];
  let shopOpen = false, gachaView = 'draw', drawResult = null, lineupAnimal = null, shownDrawId = null;
  const status = document.querySelector('#status');
  const escape = text => String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const allowedMath = new Set('input div p table caption colgroup col thead tbody tr th td br span math semantics mrow mi mn mo mtext mspace mfrac msqrt mroot msup msub msubsup mover munder munderover mtable mtr mtd menclose mpadded mstyle mphantom annotation'.split(' '));
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
        if (!(mathAttrs.has(attr.name) || (['input', 'span', 'div', 'p', 'table', 'col', 'th', 'td', 'tr'].includes(node.localName) && attr.name === 'class') ||
          (['th', 'td'].includes(node.localName) && attr.name === 'colspan' && /^[1-9]\d*$/.test(attr.value)) ||
          (node.localName === 'input' && ((attr.name === 'type' && attr.value === 'text') ||
            (attr.name === 'data-field' && /^b\d+-(?:r\d+-c\d+|s\d+-r\d+-(?:account|amount))$/.test(attr.value)) ||
            (attr.name === 'aria-label') || (attr.name === 'autocomplete' && attr.value === 'off') ||
            (attr.name === 'spellcheck' && attr.value === 'false'))) ||
          (node.localName === 'th' && attr.name === 'scope' && ['row', 'col'].includes(attr.value)) ||
          (node.localName === 'mo' && attr.name === 'class' && attr.value === 'math-overbar'))) node.removeAttribute(attr.name);
      }
    }
    return template.innerHTML;
  }
  const text = (q, name) => q[`${name}Html`] ? safeMath(q[`${name}Html`]) : escape(q[name]);
  function subjectPicker(id, label, value, name) {
    return `<div class="subject-field">${label ? `<span id="${id}-label">${label}</span>` : ''}<button type="button" id="${id}" class="subject-picker" role="combobox" aria-label="${name}" aria-haspopup="listbox" aria-expanded="false" aria-controls="${id}-options" data-value="${escape(value)}"><span>${escape(value)}</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button></div>`;
  }
  function setupSubjectPickers() {
    const subjects = [...new Set(availableDecks().map(item => item.title))];
    content.querySelectorAll('.subject-picker').forEach(button => {
      const menu = document.createElement('div');
      menu.id = button.getAttribute('aria-controls');
      menu.className = 'subject-options';
      menu.setAttribute('role', 'listbox');
      menu.setAttribute('aria-label', button.getAttribute('aria-label'));
      menu.hidden = true;
      menu.innerHTML = subjects.map(title => `<button type="button" role="option" tabindex="-1" aria-selected="${title === button.dataset.value}" data-value="${escape(title)}"><span>${escape(title)}</span>${title === button.dataset.value ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>' : ''}</button>`).join('');
      document.body.appendChild(menu);
      const options = [...menu.querySelectorAll('[role="option"]')];
      function close(focus = false) {
        menu.hidden = true;
        button.setAttribute('aria-expanded', 'false');
        if (focus) button.focus({ preventScroll: true });
      }
      function open(index = subjects.indexOf(button.dataset.value)) {
        const box = button.getBoundingClientRect();
        const below = innerHeight - box.bottom - 12, above = box.top - 12;
        const down = below >= Math.min(280, above);
        menu.style.left = `${box.left}px`;
        menu.style.width = `${box.width}px`;
        menu.style.maxHeight = `${Math.min(280, down ? below : above)}px`;
        menu.hidden = false;
        menu.style.top = `${down ? box.bottom + 6 : box.top - menu.offsetHeight - 6}px`;
        button.setAttribute('aria-expanded', 'true');
        const option = options[Math.max(0, index)];
        option.focus({ preventScroll: true });
        option.scrollIntoView({ block: 'nearest' });
      }
      function choose(option) {
        const value = option.dataset.value;
        close();
        if (button.id === 'subject') { subject = value; catalogNavigate(); }
        else { studySubject = value; render(); }
        document.getElementById(button.id)?.focus({ preventScroll: true });
      }
      button.onclick = () => menu.hidden ? open() : close(true);
      button.onkeydown = event => {
        if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
          event.preventDefault();
          open(event.key === 'End' || event.key === 'ArrowUp' ? options.length - 1 : event.key === 'Home' ? 0 : undefined);
        }
      };
      menu.onclick = event => {
        const option = event.target.closest('[role="option"]');
        if (option) choose(option);
      };
      menu.onkeydown = event => {
        const index = options.indexOf(document.activeElement);
        const move = { ArrowDown: Math.min(options.length - 1, index + 1), ArrowUp: Math.max(0, index - 1), Home: 0, End: options.length - 1 };
        if (event.key in move) { event.preventDefault(); options[move[event.key]].focus(); }
        else if (event.key === 'Escape') { event.preventDefault(); close(true); }
        else if (event.key === 'Tab') close(true);
      };
      const outside = event => { if (!button.contains(event.target) && !menu.contains(event.target)) close(); };
      const dismiss = () => close();
      document.addEventListener('pointerdown', outside);
      window.addEventListener('resize', dismiss);
      scrollRegion.addEventListener('scroll', dismiss);
      disclosureCleanups.push(() => {
        document.removeEventListener('pointerdown', outside);
        window.removeEventListener('resize', dismiss);
        scrollRegion.removeEventListener('scroll', dismiss);
        menu.remove();
      });
    });
  }
  function pickRecord() {
    return new Promise((resolve, reject) => {
      const input = document.createElement('input');
      input.type = 'file'; input.accept = '.json,application/json'; input.hidden = true;
      document.body.appendChild(input);
      input.addEventListener('change', async () => {
        try {
          if (!input.files.length) throw Error('ファイル選択を取り消しました。');
          resolve(JSON.parse(await input.files[0].text()));
        } catch (error) { reject(error); }
        finally { input.remove(); }
      }, { once: true });
      input.addEventListener('cancel', () => { input.remove(); reject(Error('ファイル選択を取り消しました。')); }, { once: true });
      input.click();
    });
  }
  async function showCountdown() {
    page = 'quiz';
    status.textContent = '';
    try {
      for (const label of ['3', '2', '1', 'スタート']) {
        countdown = label;
        render();
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    } finally {
      countdown = null;
    }
  }
  async function call(action, payload) {
    if (action === 'export') {
      const url = URL.createObjectURL(new Blob([JSON.stringify(await runtime.export(), null, 2)], { type: 'application/json' }));
      const link = document.createElement('a'); link.href = url; link.download = 'recall-quiz-state.json'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return { ok: true, ...await runtime.refresh(), message: '学習記録を書き出しました。' };
    }
    if (action === 'importState') {
      const data = await pickRecord();
      const restored = RecallCore.validateState(data.state || data);
      if (!window.confirm(`${restored.reviews.length}件の回答、${restored.garden.coins}コインの記録に置き換えます。`)) return { ok: true, ...runtime.boot() };
      return { ok: true, ...await runtime.restore(data), message: '学習記録を読み込みました。' };
    }
    if (['start', 'startAll', 'startSubject', 'selectDeck'].includes(action)) {
      const scope = action === 'startAll' ? { type: 'all' } :
        action === 'startSubject' ? { type: 'subject', title: studySubject } :
        action === 'selectDeck' ? { type: 'lesson', id: payload.id } :
        state.session?.scope || deck.studyScope || { type: 'lesson', id: deck.id };
      if (studyType === 'exercise') scope.studyType = 'exercise';
      await runtime.studyDeck(scope);
      await showCountdown();
      return { ok: true, ...await runtime.dispatch('startStudy', { scope }) };
    }
    return { ok: true, ...await runtime.dispatch(action, payload) };
  }
  async function act(action, payload = {}) {
    if (busy) return;
    busy = true;
    status.textContent = '保存・処理中…';
    document.querySelectorAll('header button, .main-nav button, #content button, #quiz-controls button').forEach(b => { b.disabled = true; });
    const slow = setTimeout(() => {
      status.textContent = '処理を待っています。反応が戻らない場合は、一度閉じて開き直してください。';
    }, 15000);
    try {
      const result = await call(action, payload);
      if (!result.ok) throw Error(result.error);
      state = result.state;
      if (result.deck) deck = result.deck;
      if (state.session && ['start', 'startAll', 'startSubject', 'selectDeck', 'importState'].includes(action)) {
        studyType = state.session.mode === 'exercise' ? 'exercise' : 'knowledge';
      }
      if (result.decks) decks = result.decks;
      if (action === 'draw') {
        drawResult = state.garden.draws?.find(draw => draw.id === payload.eventId) || null;
        gachaView = 'draw';
      }
      if (['start', 'startAll', 'startSubject', 'home', 'importState', 'selectDeck'].includes(action)) page = 'quiz';
      status.textContent = result.message || (action === 'rate' ? (payload.result === 'good' ? '正解。＋1コイン。' : payload.result === 'uncertain' ? 'あやふやを記録しました。' : 'ミスを記録しました。') : '');
    } catch (error) {
      if (error.name === 'ConflictError') {
        const current = await runtime.refresh();
        state = current.state; deck = current.deck; decks = current.decks;
      }
      status.textContent = error.name === 'QuotaExceededError' ? 'ブラウザの保存領域が不足しています。記録は更新していません。' : String(error.message || error);
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
  function sourceToggles(q, sourceDeck = deck) {
    return q.sources.map(source => source.imageKey && sourceDeck.sourceImages?.[source.imageKey] ?
      `<details class="source-toggle" data-source="${escape(source.imageKey)}" data-source-url="${escape(sourceDeck.sourceImages[source.imageKey])}" data-scale="100"><summary>原典を見る（p.${source.page}）</summary><p class="source-caption">${escape(source.file)} · p.${source.page}</p><div class="source-zoom-controls"><button type="button" data-zoom="-25" aria-label="原典を縮小（p.${source.page}）">−</button><input type="range" min="50" max="300" step="25" value="100" aria-label="原典の表示倍率（p.${source.page}）"><button type="button" data-zoom="25" aria-label="原典を拡大（p.${source.page}）">＋</button><output>100%</output><button type="button" data-zoom="reset">全体</button></div><div class="source-viewport"><img alt="${escape(source.file)} p.${source.page} の原典ページ"></div><p class="helper">拡大後は画像内を上下左右にスクロールできます。</p></details>` : '').join('');
  }
  function renderQuiz() {
    if (countdown !== null) {
      content.innerHTML = `<div class="start-countdown" role="status" aria-live="assertive" aria-atomic="true"><p class="countdown-label">まもなく始まります</p><p class="countdown-number ${countdown === 'スタート' ? 'countdown-start' : ''}">${countdown}</p></div>`;
      return;
    }
    const s = state.session;
    if (!s) {
      const subjects = [...new Set(availableDecks().map(item => item.title))];
      if (!subjects.includes(studySubject)) studySubject = subjects[0];
      content.innerHTML = `<p class="eyebrow">QUIZ</p><h1 class="page-title">${studyType === 'exercise' ? '演習問題' : '今日のクイズ'}</h1>${modeTabs()}<p class="lead">${studyType === 'exercise' ? '時間制限なしで、範例を順番に解きます。' : '思い出せた回数が少ない問題から、ランダムに5問。'}</p><div class="stack quiz-start"><button class="primary" data-action="startAll">全教科から始める</button></div><section class="subject-start">${subjectPicker('study-subject', '教科を指定する', studySubject, '出題する教科')}<button class="secondary" data-action="startSubject">この教科で始める</button></section>`;
      return;
    }
    const scope = s.scope || { type: 'lesson', id: s.deckId };
    const scopeLabel = scope.type === 'all' ? '全教科' : scope.type === 'subject' ? scope.title :
      decks.find(item => item.id === scope.id)?.subtitle || deck.title;
    if (s.closed || s.index >= s.queue.length) {
      const completed = s.index >= s.queue.length;
      content.innerHTML = `<p class="eyebrow">${escape(scopeLabel)}</p><h1 class="page-title">${completed ? `${s.queue.length}問、おつかれさま。` : '今日は、ここまで。'}</h1><p class="lead">${s.index ? `${s.index}問に回答しました。` : '答え合わせをした問題はありません。'}<br>思い出せた問題は${s.correct}問です。</p><div class="stack quiz-start"><button class="primary" data-action="home">最初の画面に戻る</button><button class="secondary" data-action="start">${s.mode === 'exercise' ? 'もう一度解く' : scope.type === 'all' ? 'あと5問' : scope.type === 'subject' ? '同じ教科であと5問' : '同じ回であと5問'}</button>${scope.type !== 'all' ? '<button class="quiet" data-action="startAll">全教科から始める</button>' : ''}</div><p class="helper center">回答の記録とコインは保存されています。</p>`;
      return;
    }
    const q = deck.questions.find(q => q.id === s.queue[s.index].id);
    if (s.mode === 'exercise') {
      content.innerHTML = `<div class="question-head"><span class="step">${s.index + 1} / ${s.queue.length} 問</span></div><h1 class="exercise-title">${escape(q.label || '演習問題')}</h1><div class="exercise-question" data-draft-key="${escape(`${s.id}:${s.index}`)}">${text(q, 'prompt')}</div>${s.answerShown ? `<div class="answer-reveal"><section class="answer"><p class="label">解答</p><div class="answer-main math-text">${text(q, 'answer')}</div><p class="criterion">${text(q, 'criterion')}</p><details><summary>補足</summary><p>${text(q, 'explanation')}</p></details></section><div class="ratings"><button class="secondary" data-result="again"><span class="rating-symbol mistake" aria-hidden="true">×</span><span>できなかった</span></button><button class="secondary uncertain" data-result="uncertain"><span class="rating-symbol uncertain" aria-hidden="true">△</span><span>あやふや</span></button><button class="primary" data-result="good"><span class="rating-symbol correct" aria-hidden="true">○</span><span>できた</span></button></div></div>` : '<div class="exercise-actions"><button class="primary" data-action="reveal">解答を見る</button></div>'}<div class="center"><button class="quiet" data-action="finish">今日はここまで</button></div>`;
      return;
    }
    content.innerHTML = `<div class="question-head"><span class="step">${s.index + 1} / ${s.queue.length} 問</span><span class="dots" aria-hidden="true">${s.queue.map((_, i) => `<i class="${i < s.index ? 'done' : i === s.index ? 'current' : ''}"></i>`).join('')}</span></div><div class="quiz-timer"><div class="timer-caption"><span>${s.answerShown ? '次の問題まで' : '答えの表示まで'}</span><span data-timer-seconds>15秒</span></div><div class="timer-track" role="progressbar" aria-label="残り時間" aria-valuemin="0" aria-valuemax="15" aria-valuenow="15"><div class="timer-fill"></div></div></div><h1 class="question math-text">${text(q, 'prompt')}</h1>${s.answerShown ? `<div class="answer-reveal"><section class="answer"><p class="label">ANSWER</p><div class="answer-main math-text">${text(q, 'answer')}</div><div class="criterion math-text">${text(q, 'criterion')}</div><details><summary>補足と出典</summary><div class="math-text">${text(q, 'explanation')}</div><div class="sources">${q.sources.map(s => `${escape(s.file)} · p.${s.page}`).join('<br>')}</div></details></section><p class="reward-hint">正解すると ＋1コイン</p><div class="ratings"><button class="secondary" data-result="again" aria-label="出なかった"><span class="rating-symbol mistake" aria-hidden="true">×</span><span>出なかった</span></button><button class="secondary uncertain" data-result="uncertain" aria-label="あやふや"><span class="rating-symbol uncertain" aria-hidden="true">△</span><span>あやふや</span></button><button class="primary" data-result="good" aria-label="思い出せた"><span class="rating-symbol correct" aria-hidden="true">○</span><span>思い出せた</span></button></div><p class="helper center">15秒以内に選んでください。未選択なら出なかったとして次に進みます。</p></div>` : '<p class="helper">頭の中で答えるだけ。わからなければ、すぐ見よう。</p><button class="primary" data-action="reveal">答えを見る</button>'}<div class="center"><button class="quiet" data-action="finish">今日はここまで</button></div>`;
  }
  function gachaContents() {
    const available = boot.shop.filter(item => !state.garden.items.includes(item.id));
    if (gachaView === 'lineup') {
      const selected = boot.shop.find(item => item.id === lineupAnimal && state.garden.items.includes(item.id));
      if (selected) return `<div class="lineup-detail"><button class="lineup-back">‹ ラインナップに戻る</button>${animalImage(selected)}<h3>${escape(selected.name)}</h3><p>${escape(selected.description)}</p></div>`;
      return `<div class="animal-lineup">${boot.shop.map((item, index) => {
        const owned = state.garden.items.includes(item.id);
        return owned ? `<button class="lineup-card owned" data-lineup="${item.id}">${animalImage(item)}<span class="lineup-name">${escape(item.name)}</span><small>No.${String(index + 1).padStart(2, '0')}</small></button>` : `<div class="lineup-card locked" aria-label="未入手の動物 ${index + 1}"><span class="unknown-animal" aria-hidden="true">?</span><span class="lineup-name">未入手</span><small>No.${String(index + 1).padStart(2, '0')}</small></div>`;
      }).join('')}</div>`;
    }
    const result = drawResult && boot.shop.find(item => item.id === drawResult.animalId && state.garden.items.includes(item.id));
    const visual = result ? `<div class="gacha-result" role="status"><p class="eyebrow">NEW FRIEND</p>${animalImage(result, 'draw-animal-image')}<h3>${escape(result.name)}</h3><p>${escape(result.description)}</p></div>` : `<div class="gacha-welcome"><div class="gacha-capsule" aria-hidden="true"><span>?</span></div></div>`;
    return `${visual}<div class="gacha-controls"><button class="draw-gacha primary" ${state.garden.coins < RecallCore.gachaCost || !available.length ? 'disabled' : ''}>${available.length ? '10コインで1回まわす' : 'コンプリート'}</button>
      </div>`;
  }
  function renderGarden() {
    const residents = boot.shop.filter(item => state.garden.items.includes(item.id));
    content.innerHTML = `<section class="garden-stage ${residents.length > 4 ? 'many-residents' : ''}" aria-label="動物たちの庭">${gardenLandscape()}
      <div class="garden-caption"><p class="eyebrow">LITTLE WILD GARDEN</p><h1>ひとつの庭</h1><p>${residents.length ? `${residents.length}匹が、のんびり暮らしています。` : '学んだぶんだけ、仲間が増えていく。'}</p></div>
      <div class="garden-residents">${residents.map((item, index) => `<button class="garden-animal animal-${item.asset} motion-${item.motion}" style="--x:${item.x}%;--y:${item.y}%;--delay:-${index * .7}s" aria-label="${escape(item.name)}に声をかける"><span class="animal-shadow"></span><span class="animal-roam"><span class="animal-body">${animalImage(item)}</span></span><span class="animal-name">${escape(item.name)}</span></button>`).join('')}</div>
      ${!residents.length ? '<div class="garden-invitation"><span class="invitation-line"></span><p>最初の仲間を、迎えよう。</p><small>右下のガチャで出会えます。</small></div>' : ''}
      <button class="open-garden-shop" aria-haspopup="dialog"><svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="13" r="10"/><path d="M6 13h20M11 23l-2 6h14l-2-6M13 18h6"/><circle cx="16" cy="8" r="1"/></svg><span>ガチャ</span></button>
      <p class="garden-tip">${residents.length ? '動物にタッチしてみよう。' : 'クイズに正解すると、1コイン。'}</p></section>
      <dialog class="garden-shop" aria-labelledby="garden-shop-title"><div class="shop-sheet"><div class="shop-grip" aria-hidden="true"></div>
      <div class="garden-shop-header"><div><p class="eyebrow">MEET A LITTLE FRIEND</p><h2 id="garden-shop-title">どうぶつガチャ</h2></div><button class="close-garden-shop" aria-label="ガチャを閉じる">×</button></div>
      <p class="shop-balance"><span class="coin-dot"></span> ${state.garden.coins} <span>コイン</span><small>${residents.length} / ${boot.shop.length}種類</small></p>
      <div class="gacha-tabs" aria-label="ガチャの表示"><button data-gacha-view="draw" aria-pressed="${gachaView === 'draw'}">ガチャ</button><button data-gacha-view="lineup" aria-pressed="${gachaView === 'lineup'}">ラインナップ</button></div>
      <div class="gacha-scroll">${gachaContents()}</div></div></dialog>`;
  }
  function setupGardenShop() {
    const dialog = content.querySelector('.garden-shop');
    if (!dialog) return;
    const sheet = dialog.querySelector('.shop-sheet');
    const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    content.querySelector('.open-garden-shop').onclick = () => {
      shopOpen = true;
      gachaView = 'draw';
      drawResult = null;
      lineupAnimal = null;
      render();
      const opened = content.querySelector('.shop-sheet');
      if (!reduced()) opened.animate([{ transform: 'translateY(100%)' }, { transform: 'translateY(0)' }], {
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
    function navigate(view, animal = null) {
      gachaView = view;
      lineupAnimal = animal;
      render();
      if (!reduced()) content.querySelector('.gacha-scroll').animate([
        { transform: 'translateY(14px)' }, { transform: 'translateY(0)' }
      ], { duration: 260, easing: 'cubic-bezier(.2,.7,.2,1)' });
    }
    dialog.querySelectorAll('[data-gacha-view]').forEach(button => button.onclick = () => navigate(button.dataset.gachaView));
    dialog.querySelectorAll('[data-lineup]').forEach(button => button.onclick = () => navigate('lineup', button.dataset.lineup));
    const back = dialog.querySelector('.lineup-back');
    if (back) back.onclick = () => navigate('lineup');
    const draw = dialog.querySelector('.draw-gacha');
    if (draw) draw.onclick = () => act('draw', { eventId: `draw-${Date.now()}-${Math.random().toString(36).slice(2)}` });
    content.querySelectorAll('.garden-animal').forEach(animal => animal.onclick = () => {
      animal.classList.remove('says-hello');
      void animal.offsetWidth;
      animal.classList.add('says-hello');
    });
    if (shopOpen) dialog.showModal();
    const resultImage = dialog.querySelector('.draw-animal-image');
    if (resultImage && shownDrawId !== drawResult.id) {
      shownDrawId = drawResult.id;
      if (!reduced()) resultImage.animate([{ transform: 'translateY(22px) scale(.85)' }, { transform: 'translateY(0) scale(1)' }], {
        duration: 450, easing: 'cubic-bezier(.2,.7,.2,1)'
      });
    }
  }
  function renderSettings() {
    content.innerHTML = `<h1 class="page-title">設定</h1><section class="panel"><h2 class="settings-heading">このブラウザの記録</h2><p class="lead">回答 ${state.reviews.length}回 · 動物 ${state.garden.items.length}種類</p><div class="stack"><button class="secondary" data-action="export">学習記録を書き出す</button><button class="secondary" data-action="importState">学習記録を読み込む</button></div><p class="helper">記録はこの端末のブラウザに保存します。端末を替えるときは、書き出したファイルを読み込んでください。</p></section>`;
  }
  function renderCalendar() {
    const stats = RecallCore.statistics(state);
    const year = month.getFullYear(), m = month.getMonth();
    const count = new Date(year, m + 1, 0).getDate();
    let cells = '<span class="calendar-blank" aria-hidden="true"></span>'.repeat(month.getDay());
    for (let date = 1; date <= count; date++) {
      const key = RecallCore.day(new Date(year, m, date));
      const answers = stats.days[key] || 0;
      cells += `<button class="calendar-day ${answers ? 'has-answers' : ''} ${key === RecallCore.day(new Date()) ? 'is-today' : ''}" data-day="${key}" aria-pressed="${key === selectedDay}" aria-label="${year}年${m + 1}月${date}日、${answers}回答"><span>${date}</span><small>${answers ? `${answers}回` : ''}</small></button>`;
    }
    content.innerHTML = `<div class="page-heading calendar-heading"><h1 class="page-title">学習カレンダー</h1><button class="quiet" data-today>今月に戻る</button></div><section class="panel calendar-panel"><div class="month-nav"><button data-month="-1" aria-label="前の月">‹</button><h2>${year}年${m + 1}月</h2><button data-month="1" aria-label="次の月">›</button></div><div class="calendar-grid">${['日', '月', '火', '水', '木', '金', '土'].map(d => `<span class="weekday">${d}</span>`).join('')}${cells}</div></section>`;
  }
  function updateQuizTimer() {
    if (page !== 'quiz' || countdown !== null) return;
    const s = state.session;
    if (!s || s.mode === 'exercise' || s.closed || s.index >= s.queue.length) return;
    const remaining = Math.max(0, Math.min(15000, 15000 - (Date.now() - Date.parse(s.answerShown ? s.revealedAt : s.presentedAt))));
    const track = content.querySelector('.timer-track');
    if (!track) return;
    track.setAttribute('aria-valuenow', String(Math.ceil(remaining / 1000)));
    track.dataset.tone = remaining <= 2000 ? 'red' : remaining <= 5000 ? 'yellow' : 'blue';
    track.querySelector('.timer-fill').style.transform = `scaleX(${remaining / 15000})`;
    content.querySelector('[data-timer-seconds]').textContent = `${Math.ceil(remaining / 1000)}秒`;
    if (remaining === 0 && !busy) act('timeout', { eventId: `${s.id}:${s.index}`, answerShown: s.answerShown });
  }
  function renderHistory() {
    const ordered = [...historyReviews()].reverse().sort((a, b) => Date.parse(b.reviewedAt) - Date.parse(a.reviewedAt));
    const pageCount = Math.max(1, Math.ceil(ordered.length / 10));
    const offset = (historyPage - 1) * 10;
    const reviews = ordered.slice(offset, offset + 10);
    for (const review of reviews) {
      const item = decks.find(item => item.id === review.deckId);
      if (!item || item.questions || catalogRequests.has(item.id) || catalogErrors.has(item.id)) continue;
      catalogRequests.set(item.id, runtime.loadDeck(item.id).then(() => {
        decks = runtime.decks();
      }).catch(error => { catalogErrors.set(item.id, error.message); }).finally(() => {
        catalogRequests.delete(item.id);
        if (page === 'history') render();
      }));
    }
    const rows = reviews.map((review, index) => {
      const item = decks.find(item => item.id === review.deckId);
      const q = [...(item?.questions || []), ...(item?.retiredQuestions || [])].find(q => q.id === review.questionId && q.version === review.questionVersion);
      const result = review.result === 'good' ? ['correct', '○', '思い出せた'] : review.result === 'uncertain' ? ['uncertain', '△', 'あやふや'] : ['mistake', '×', '出なかった'];
      return `<details class="catalog-question history-question"><summary><span class="question-number">${offset + index + 1}</span><span class="catalog-prompt"><small>${escape(item?.title || review.deckId || '以前の教材')} · ${escape(item?.subtitle || '')}<br>${escape(new Date(review.reviewedAt).toLocaleString('ja-JP'))}</small><span class="math-text">${q ? q.promptBlocks ? escape(q.label || '演習問題') : text(q, 'prompt') : escape(review.questionId)}</span></span><span class="result-badge ${result[0]}" aria-label="${result[2]}">${result[1]}</span></summary><div class="catalog-answer">${q ? `${q.promptBlocks ? `<div class="exercise-question">${text(q, 'prompt')}</div>` : ''}<p class="label">解答</p><div class="math-text">${text(q, 'answer')}</div><p class="criterion math-text">${text(q, 'criterion')}</p><div class="source-toggles">${sourceToggles(q, item)}</div>` : `<p>${catalogErrors.has(item?.id) ? '教材を読み込めませんでした。履歴タブを開き直すと再試行します。' : item && !item.questions ? '問題を読み込み中…' : 'この版の問題は現在の教材にありません。'}</p>`}</div></details>`;
    }).join('');
    const pagination = pageCount > 1 ? `<nav class="history-pagination" aria-label="回答履歴のページ"><button data-history-page="${historyPage - 1}" aria-label="前の10問" ${historyPage === 1 ? 'disabled' : ''}>‹</button><span aria-live="polite" aria-label="${historyPage}ページ目、全${pageCount}ページ">${historyPage} / ${pageCount}</span><button data-history-page="${historyPage + 1}" aria-label="次の10問" ${historyPage === pageCount ? 'disabled' : ''}>›</button></nav>` : '';
    content.innerHTML = `<div class="page-heading history-heading"><h1 class="page-title">回答履歴</h1>${pagination}</div>${modeTabs()}<div class="history-list">${rows || '<div class="panel">まだ回答履歴がありません。</div>'}</div>`;
  }
  function resultCounts(n) {
    return `<span class="count-presented" aria-label="出題${n.presented}回">出題 <strong>${n.presented}</strong></span><span class="result-badge correct" aria-label="正解${n.correct}回"><span class="result-symbol" aria-hidden="true">○</span><strong aria-hidden="true">${n.correct}</strong></span><span class="result-badge uncertain" aria-label="あやふや${n.uncertain}回"><span class="result-symbol" aria-hidden="true">△</span><strong aria-hidden="true">${n.uncertain}</strong></span><span class="result-badge mistake" aria-label="ミス${n.mistakes}回"><span class="result-symbol" aria-hidden="true">×</span><strong aria-hidden="true">${n.mistakes}</strong></span>`;
  }
  function catalogNavigate(id = '') {
    catalogLesson = id;
    const url = new URL(location.href);
    url.searchParams.set('screen', 'catalog');
    url.searchParams.set('subject', subject);
    if (id) url.searchParams.set('lesson', id);
    else url.searchParams.delete('lesson');
    history.pushState(null, '', url);
    render();
  }
  function renderCatalog() {
    const stats = RecallCore.statistics(state);
    const subjects = [...new Set(availableDecks().map(item => item.title))];
    const selected = availableDecks().find(item => item.id === catalogLesson);
    if (selected) subject = selected.title;
    else catalogLesson = '';
    if (!subjects.includes(subject)) subject = subjects[0];
    if (!selected) {
      const items = availableDecks().filter(item => item.title === subject);
      content.innerHTML = `<h1 class="page-title">クイズ一覧</h1>${modeTabs()}${subjectPicker('subject', '', subject, '教科')}<div class="lesson-grid">${items.map(item => {
        const label = item.subtitle || item.title;
        const [lesson, ...topic] = label.split(' · ');
        return `<button class="lesson-card" data-open-lesson="${escape(item.id)}"><span class="lesson-card-number">${escape(lesson)}</span><span>${escape(topic.join(' · '))}</span><small>${item.questionCount || item.questions?.length || 0}問<span aria-hidden="true"> →</span></small></button>`;
      }).join('')}</div>`;
      return;
    }
    if (!selected.questions && !catalogRequests.has(selected.id) && !catalogErrors.has(selected.id)) {
      const id = selected.id;
      catalogRequests.set(id, runtime.loadDeck(id).then(() => {
        decks = runtime.decks();
      }).catch(error => { catalogErrors.set(id, error.message); }).finally(() => {
        catalogRequests.delete(id);
        if (page === 'catalog' && catalogLesson === id) render();
      }));
    }
    const heading = `<div class="catalog-toolbar"><button class="catalog-back" data-catalog-back aria-label="授業回の一覧に戻る"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 5-7 7 7 7"/></svg></button><button class="lesson-start" data-deck="${escape(selected.id)}">この回で学習</button></div><p class="eyebrow">${escape(selected.title)}</p><h1 class="page-title">${escape(selected.subtitle || selected.title)}</h1>`;
    if (!selected.questions) {
      const error = catalogErrors.get(selected.id);
      content.innerHTML = `${heading}<div class="panel" role="status" aria-live="polite">${error ? `<p>${escape(error)}</p><button class="secondary" data-retry-lesson="${escape(selected.id)}">もう一度読み込む</button>` : '<p>問題を読み込み中…</p>'}</div>`;
      return;
    }
    const rows = selected.questions.map((q, index) => {
      const n = RecallCore.questionStatistics(stats, selected.id, q.id);
      return `<details class="catalog-question"><summary><span class="question-number">${index + 1}</span><span class="catalog-prompt math-text">${q.promptBlocks ? escape(q.label || '演習問題') : text(q, 'prompt')}</span><span class="question-counts">${resultCounts(n)}</span></summary><div class="catalog-answer">${q.promptBlocks ? `<div class="exercise-question">${text(q, 'prompt')}</div>` : ''}<p class="label">解答</p><div class="math-text">${text(q, 'answer')}</div><p class="criterion math-text">${text(q, 'criterion')}</p><div class="source-toggles">${sourceToggles(q, selected)}</div></div></details>`;
    }).join('');
    const retired = Object.entries(stats.questions).filter(([key]) => {
      const [deckId, questionId] = JSON.parse(key);
      return deckId === selected.id && !selected.questions.some(q => q.id === questionId);
    }).map(([key, n]) => `<div class="retired-question"><p>旧版の問題 <small>${escape(JSON.parse(key)[1])}</small></p><div class="question-counts">${resultCounts(n)}</div></div>`).join('');
    content.innerHTML = `${heading}${modeTabs()}<section class="lesson">${rows}${retired ? `<details><summary>更新で除かれた問題の記録</summary>${retired}</details>` : ''}</section>`;
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
  function saveExerciseDraft() {
    const question = content.querySelector('[data-draft-key]');
    if (!question) return;
    const values = Object.fromEntries([...question.querySelectorAll('[data-field]')].map(input => [input.dataset.field, input.value]));
    try { sessionStorage.setItem(`recall-exercise:${question.dataset.draftKey}`, JSON.stringify(values)); } catch (_) { /* A full storage area does not prevent answering. */ }
  }
  function restoreExerciseDraft() {
    const question = content.querySelector('[data-draft-key]');
    if (!question) return;
    let values = {};
    try { values = JSON.parse(sessionStorage.getItem(`recall-exercise:${question.dataset.draftKey}`) || '{}') || {}; } catch (_) { /* Ignore an unreadable draft. */ }
    for (const input of question.querySelectorAll('[data-field]')) {
      input.value = typeof values[input.dataset.field] === 'string' ? values[input.dataset.field] : '';
      input.oninput = saveExerciseDraft;
    }
  }
  function render() {
    saveExerciseDraft();
    clearInterval(quizTimer);
    historyPage = Math.min(historyPage, Math.max(1, Math.ceil(historyReviews().length / 10)));
    document.body.classList.toggle('garden-mode', page === 'garden');
    const activeQuiz = page === 'quiz' && (countdown !== null || (state.session && !state.session.closed && state.session.index < state.session.queue.length));
    document.body.classList.toggle('quiz-active', Boolean(activeQuiz));
    document.body.classList.toggle('exercise-active', Boolean(activeQuiz && state.session?.mode === 'exercise'));
    document.body.classList.toggle('quiz-answer', Boolean(activeQuiz && countdown === null && state.session?.answerShown));
    quizControls.replaceChildren();
    quizControls.hidden = true;
    if (page !== 'garden') shopOpen = false;
    disclosureCleanups.forEach(dispose => dispose());
    disclosureCleanups = [];
    if (/^https?:$/.test(location.protocol)) {
      const url = new URL(location.href);
      url.searchParams.set('screen', page);
      url.searchParams.set('studyType', studyType);
      if (page === 'history' && historyPage > 1) url.searchParams.set('historyPage', String(historyPage));
      else url.searchParams.delete('historyPage');
      if (page === 'catalog') {
        if (catalogLesson) url.searchParams.set('lesson', catalogLesson);
        else url.searchParams.delete('lesson');
        if (subject) url.searchParams.set('subject', subject);
      } else {
        url.searchParams.delete('lesson');
        url.searchParams.delete('subject');
      }
      history.replaceState(null, '', url);
    }
    document.querySelector('#coins').innerHTML = `<span class="coin-dot" aria-hidden="true"></span>${state.garden.coins}`;
    document.querySelectorAll('header button, .main-nav button').forEach(b => { b.disabled = busy; });
    document.querySelectorAll('[data-screen]').forEach(button => button.setAttribute('aria-current', button.dataset.screen === page ? 'page' : 'false'));
    if (page === 'calendar') renderCalendar();
    else if (page === 'catalog') renderCatalog();
    else if (page === 'history') renderHistory();
    else if (page === 'garden') renderGarden();
    else if (page === 'settings') renderSettings();
    else renderQuiz();
    const ratings = content.querySelector('.ratings, .exercise-actions');
    if (ratings) {
      quizControls.appendChild(ratings);
      quizControls.hidden = false;
    }
    if (page === 'quiz' && state.session && state.session.answerShown) {
      const current = state.session.queue[state.session.index];
      const q = current && deck.questions.find(q => q.id === current.id);
      if (q) {
        const section = content.querySelector('.answer');
        if (section) section.insertAdjacentHTML('beforeend', `<div class="source-toggles">${sourceToggles(q)}</div>`);
      }
    }
    const key = `${page}:${state.session?.id}:${state.session?.index}:${state.session?.answerShown}:${state.session?.closed}:${studyType}:${subject}:${catalogLesson}:${historyPage}`;
    if (key !== renderedKey) {
      const changedPage = page !== renderedPage;
      const historyTurn = page === 'history' && !changedPage && historyPage !== renderedHistoryPage;
      if (content.getAnimations) content.getAnimations().forEach(animation => animation.cancel());
      const answerReveal = page === 'quiz' && !changedPage ? content.querySelector('.answer-reveal') : null;
      if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && content.animate) {
        if (answerReveal) {
          answerReveal.animate([{ height: '0px' }, { height: `${answerReveal.scrollHeight}px` }], {
            duration: 300, easing: 'cubic-bezier(.2,.7,.2,1)'
          });
        } else {
          const order = ['quiz', 'calendar', 'garden', 'catalog', 'history', 'settings'];
          const direction = historyTurn ? Math.sign(historyPage - renderedHistoryPage) :
            order.indexOf(page) >= order.indexOf(renderedPage) ? 1 : -1;
          const animationTarget = page === 'history' ? content.querySelector('.history-list') : content;
          animationTarget.animate([
            { opacity: 0, transform: historyTurn ? `translateX(${direction * 24}px)` :
              changedPage ? `translateX(${direction * 18}px)` : 'translateY(10px)' },
            { opacity: 1, transform: 'translate(0, 0)' }
          ], { duration: historyTurn ? 180 : changedPage ? 320 : 220, easing: 'cubic-bezier(.2,.7,.2,1)' });
        }
      }
      releasePull(false);
      scrollRegion.scrollTop = state.session?.mode === 'exercise' && state.session.answerShown && page === 'quiz' ?
        content.querySelector('.answer-reveal')?.offsetTop || 0 : 0;
      renderedKey = key;
      renderedPage = page;
      renderedHistoryPage = historyPage;
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
        const url = toggle.dataset.sourceUrl;
        if (/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(url || '') || /^\.\/assets\/sources\/[a-f0-9]{64}-\d+\.png$/.test(url || '')) image.src = url;
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
    setupSubjectPickers();
    content.querySelectorAll('[data-study-type]').forEach(button => button.onclick = () => {
      studyType = button.dataset.studyType;
      catalogLesson = '';
      historyPage = 1;
      history.pushState(null, '', `?screen=${page}&studyType=${studyType}`);
      render();
    });
    restoreExerciseDraft();
    content.querySelectorAll('[data-history-page]').forEach(button => button.onclick = () => {
      if (busy) return;
      historyPage = Number(button.dataset.historyPage);
      const url = new URL(location.href);
      url.searchParams.set('historyPage', String(historyPage));
      history.pushState(null, '', url);
      render();
    });
    content.querySelectorAll('[data-open-lesson]').forEach(button => button.onclick = () => catalogNavigate(button.dataset.openLesson));
    const back = content.querySelector('[data-catalog-back]');
    if (back) back.onclick = () => catalogNavigate();
    content.querySelectorAll('[data-retry-lesson]').forEach(button => button.onclick = () => {
      catalogErrors.delete(button.dataset.retryLesson);
      render();
    });
    content.querySelectorAll('[data-deck]').forEach(button => button.onclick = () => act('selectDeck', { id: button.dataset.deck }));
    document.querySelectorAll('#content [data-action], #quiz-controls [data-action]').forEach(b => b.onclick = () => act(b.dataset.action));
    if (page === 'quiz' && countdown === null) {
      quizTimer = setInterval(updateQuizTimer, 100);
      updateQuizTimer();
    }
    updateScrollFade();
    quizControls.querySelectorAll('[data-result]').forEach(b => b.onclick = () => act('rate', {
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
  document.querySelectorAll('[data-screen]').forEach(button => button.onclick = () => {
    if (busy) return;
    renderedKey = '';
    if (button.dataset.screen === 'quiz') { act('home'); return; }
    page = button.dataset.screen;
    if (page === 'catalog') catalogLesson = '';
    if (page === 'history') { historyPage = 1; catalogErrors.clear(); }
    if (page === 'calendar') {
      const today = new Date();
      month = new Date(today.getFullYear(), today.getMonth(), 1);
      selectedDay = RecallCore.day(today);
    }
    if (page === 'garden') {
      shopOpen = false;
      gachaView = 'draw';
      drawResult = null;
      lineupAnimal = null;
      shownDrawId = null;
    }
    status.textContent = '';
    render();
  });
  document.querySelector('#home').onclick = () => act('home');
  window.addEventListener('popstate', () => {
    if (busy) return;
    const params = new URLSearchParams(location.search);
    const requested = params.get('screen');
    page = ['garden', 'settings', 'calendar', 'catalog', 'history'].includes(requested) ? requested : 'quiz';
    catalogLesson = params.get('lesson') || '';
    studyType = params.get('studyType') === 'exercise' || decks.find(item => item.id === catalogLesson)?.studyType === 'exercise' ? 'exercise' : 'knowledge';
    historyPage = Math.max(1, parseInt(params.get('historyPage'), 10) || 1);
    subject = params.get('subject') || '';
    render();
  });
  document.querySelector('#settings-nav').onclick = () => { page = 'settings'; render(); };
  if (boot.notice) {
    const notice = document.querySelector('#notice'); notice.textContent = boot.notice; notice.hidden = false;
  }
  render();
})();
