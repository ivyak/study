(() => {
  const boot = window.BOOT;
  let state = boot.state, deck = boot.deck, page = 'quiz', busy = false, serial = 0;
  const content = document.querySelector('#content');
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
    document.querySelectorAll('button').forEach(b => { b.disabled = true; });
    const slow = setTimeout(() => {
      status.textContent = '処理を待っています。反応が戻らない場合は、一度閉じて開き直してください。';
    }, 15000);
    try {
      const result = await call(action, payload);
      if (!result.ok) throw Error(result.error);
      state = result.state;
      deck = result.deck;
      if (['start', 'importDeck', 'importState'].includes(action)) page = 'quiz';
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
  function renderQuiz() {
    const s = state.session;
    if (!s || s.closed || s.index >= s.queue.length) {
      const count = s ? s.index : 0;
      content.innerHTML = `<p class="eyebrow">A LITTLE RECALL, EVERY DAY</p><h1 class="page-title">${count ? '今日は、ここまででも。' : 'いまは、ひと休み。'}</h1><p class="lead">${count ? `${count}回の想起を記録しました。<br>また少し時間を空けて、思い出そう。` : 'いま出す問題はありません。<br>新しい教材や、別の日の復習でまた会おう。'}</p>${scene()}<div class="stack"><button class="primary" data-action="start">あと3問</button><button class="secondary" data-page="garden">庭をのぞく</button><button class="quiet" data-page="settings">通知・教材・記録の設定</button></div><p class="helper center">休んでも、コインや植物はなくなりません。</p>`;
      content.querySelector('[data-action="start"]').disabled = RecallCore.select(state, deck, new Date()).length === 0;
      return;
    }
    const q = deck.questions.find(q => q.id === s.queue[s.index].id);
    content.innerHTML = `<p class="eyebrow">${escape(deck.title)}</p><p class="course">${escape(deck.subtitle || '')}</p><div class="question-head"><span class="step">${s.index + 1} / ${s.queue.length} 問</span><span class="dots" aria-hidden="true">${s.queue.map((_, i) => `<i class="${i < s.index ? 'done' : i === s.index ? 'current' : ''}"></i>`).join('')}</span></div><h1 class="question math-text">${text(q, 'prompt')}</h1>${s.answerShown ? `<section class="answer"><p class="label">ANSWER</p><div class="answer-main math-text">${text(q, 'answer')}</div><div class="criterion math-text">${text(q, 'criterion')}</div><details><summary>補足と出典</summary><div class="math-text">${text(q, 'explanation')}</div><div class="sources">${q.sources.map(s => `${escape(s.file)} · p.${s.page}`).join('<br>')}</div></details></section><p class="reward-hint">どちらを押しても ＋1コイン</p><div class="ratings"><button class="secondary" data-result="again">出なかった</button><button class="primary" data-result="good">思い出せた</button></div><p class="helper center">読んで納得しただけなら「出なかった」でOK。</p>` : '<p class="helper">頭の中で答えるだけ。わからなければ、すぐ見よう。</p><button class="primary" data-action="reveal">答えを見る</button>'}<div class="center"><button class="quiet" data-action="finish">今日はここまで</button></div>`;
  }
  function renderGarden() {
    content.innerHTML = `<p class="eyebrow">YOUR LITTLE GARDEN</p><h1 class="page-title">想起のあとに、小さな庭。</h1><p class="lead">正解でも、出なかった日でも。<br>ひとつ取り組むたびに、1コイン。</p>${scene()}<div class="shop">${boot.shop.map(item => `<div class="shop-item"><div><span class="plant">${item.icon}</span>${item.name}</div><button data-buy="${item.id}" ${state.garden.items.includes(item.id) || state.garden.coins < item.cost ? 'disabled' : ''}>${state.garden.items.includes(item.id) ? '庭にいます' : `${item.cost} コイン`}</button></div>`).join('')}</div><div class="center"><button class="quiet" data-page="quiz">クイズに戻る</button></div>`;
  }
  function renderSettings() {
    const settings = state.settings;
    content.innerHTML = `<p class="eyebrow">MAKE IT EASY TO RETURN</p><h1 class="page-title">自分のペースで。</h1>${!boot.native ? '<p class="badge">PCプレビュー · iPhoneの記録とは別です</p>' : ''}<form id="settings-form" class="panel"><label class="field">昼の通知<input id="notify" type="checkbox" ${settings.notificationEnabled ? 'checked' : ''}></label><label class="field">通知する時刻<input id="notify-time" type="time" value="${settings.notificationTime}" required></label><p class="helper">1日1回、追撃なし。夜のバイト中を避けた時刻に。</p><label class="field">iCloudへ記録をバックアップ<input id="cloud" type="checkbox" ${settings.iCloudBackup ? 'checked' : ''}></label><p class="helper">本体保存の後にコピーします。初期値はOFF。端末間の即時同期ではありません。</p><button class="primary" type="submit" ${boot.native ? '' : 'disabled'}>設定を保存</button></form><div class="stack"><button class="secondary" data-action="testNotification" ${boot.native ? '' : 'disabled'}>1分後の通知をテスト</button><button class="secondary" data-action="importDeck" ${boot.native ? '' : 'disabled'}>教材を読み込む</button><button class="secondary" data-action="export">学習記録を書き出す</button><button class="secondary" data-action="importState" ${boot.native ? '' : 'disabled'}>学習記録を復元する</button></div><p class="helper">教材：${escape(deck.subtitle || deck.title)}、${deck.questions.length}問。復習の間隔は初版では1・3・7・14・30日。誤答は翌日と、他の問題を挟んだ当日の再確認候補になります。同日だけの成功で間隔は延びません。</p><p class="helper">出題は短い区切りです。試験の計算演習も別に確認してください。</p><div class="center"><button class="quiet" data-page="quiz">クイズに戻る</button></div>`;
    document.querySelector('#settings-form').onsubmit = event => {
      event.preventDefault();
      act('settings', {
        notificationEnabled: document.querySelector('#notify').checked,
        notificationTime: document.querySelector('#notify-time').value,
        iCloudBackup: document.querySelector('#cloud').checked
      });
    };
  }
  function render() {
    document.querySelector('#coins').innerHTML = `<span class="coin-dot" aria-hidden="true"></span>${state.garden.coins}`;
    document.querySelectorAll('header button').forEach(b => { b.disabled = busy; });
    if (page === 'garden') renderGarden();
    else if (page === 'settings') renderSettings();
    else renderQuiz();
    content.querySelectorAll('[data-action]').forEach(b => b.onclick = () => act(b.dataset.action));
    content.querySelectorAll('[data-page]').forEach(b => b.onclick = () => { page = b.dataset.page; status.textContent = ''; render(); });
    content.querySelectorAll('[data-buy]').forEach(b => b.onclick = () => act('buy', { id: b.dataset.buy }));
    content.querySelectorAll('[data-result]').forEach(b => b.onclick = () => act('rate', {
      eventId: `${state.session.id}:${state.session.index}`, result: b.dataset.result
    }));
  }
  document.querySelector('#home').onclick = () => { page = 'quiz'; render(); };
  document.querySelector('#garden-nav').onclick = () => { page = 'garden'; render(); };
  document.querySelector('#settings-nav').onclick = () => { page = 'settings'; render(); };
  if (!boot.native) {
    try {
      const saved = localStorage.getItem('recall-quiz-preview-v1');
      state = RecallCore.ensureSession(saved ? RecallCore.validateState(JSON.parse(saved)) : state, deck, new Date());
    } catch (error) { status.textContent = 'PCプレビューの保存を利用できません。iPhone版は別のファイル保存です。'; }
  }
  if (boot.notice) {
    const notice = document.querySelector('#notice'); notice.textContent = boot.notice; notice.hidden = false;
  }
  render();
})();
