/* Shared domain logic. No Scriptable or browser APIs. */
const RecallCore = (() => {
  const intervals = [1, 3, 7, 14, 30];
  // Original item IDs preserve the animals already obtained in earlier versions.
  const gachaCost = 10;
  const shop = [
    { id: 'sprout', name: '白いうさぎ', asset: 'rabbit', description: '草むらが好きな、気ままな子。', x: 24, y: 67, motion: 'hop' },
    { id: 'flower', name: '夕焼けのきつね', asset: 'fox', description: 'ふさふさのしっぽで、庭をおさんぽ。', x: 75, y: 58, motion: 'stroll' },
    { id: 'tree', name: '森のこじか', asset: 'deer', description: '静かな木かげで、のんびりひと休み。', x: 35, y: 40, motion: 'rest' },
    { id: 'squirrel', name: 'どんぐりりす', asset: 'squirrel', description: 'お気に入りのどんぐりは、いつも一緒。', x: 60, y: 47, motion: 'hop' },
    { id: 'raccoon', name: 'しましまアライグマ', asset: 'raccoon', description: 'しましまのしっぽで、あたりを探検。', x: 45, y: 60, motion: 'stroll' },
    { id: 'hedgehog', name: 'まんまるハリネズミ', asset: 'hedgehog', description: 'ちいさな足で、ゆっくり進みます。', x: 15, y: 55, motion: 'stroll' },
    { id: 'owl', name: '木かげのふくろう', asset: 'owl', description: '庭のみんなを、そっと見守っています。', x: 82, y: 38, motion: 'float' },
    { id: 'redpanda', name: 'もみじレッサーパンダ', asset: 'redpanda', description: '夕日の色をまとった、のんびり屋。', x: 59, y: 73, motion: 'rest' },
    { id: 'capybara', name: 'ひなたのカピバラ', asset: 'capybara', description: 'あたたかな水辺で、ひとやすみ。', x: 18, y: 77, motion: 'rest' },
    { id: 'cat', name: 'おひるねねこ', asset: 'cat', description: '日だまりを見つけるのが得意です。', x: 39, y: 77, motion: 'rest' },
    { id: 'shiba', name: 'おさんぽしばいぬ', asset: 'shiba', description: '庭の小道を、てくてく歩きます。', x: 82, y: 70, motion: 'stroll' },
    { id: 'bear', name: 'こもれびこぐま', asset: 'bear', description: '大きく伸びをして、今日もゆったり。', x: 15, y: 43, motion: 'rest' },
    { id: 'otter', name: '水辺のかわうそ', asset: 'otter', description: '小さな池のそばが、いつもの場所。', x: 10, y: 68, motion: 'rest' }
  ];
  const copy = value => JSON.parse(JSON.stringify(value));
  const day = date => [date.getFullYear(), date.getMonth() + 1, date.getDate()].join('-');
  function later(now, days) {
    const date = new Date(now);
    date.setHours(0, 0, 0, 0);
    date.setDate(date.getDate() + days);
    return date.toISOString();
  }
  function validateDeck(deck) {
    if (!deck || deck.schemaVersion !== 1 || !/^[a-z0-9-]+$/.test(deck.id || '') ||
      !Number.isInteger(deck.version) || deck.version < 1 || typeof deck.title !== 'string' ||
      !Array.isArray(deck.questions) || !deck.questions.length) throw Error('教材の形式が違います。');
    const ids = new Set();
    for (const q of deck.questions) {
      if (!q || !/^[a-z0-9-]+$/.test(q.id || '') || ids.has(q.id) ||
        !Number.isInteger(q.version) || q.version < 1 ||
        !['prompt', 'answer', 'criterion', 'explanation'].every(k => typeof q[k] === 'string') ||
        !q.prompt.trim() || !q.answer.trim() || !q.criterion.trim() ||
        !Array.isArray(q.sources) || !q.sources.length ||
        q.sources.some(s => typeof s.file !== 'string' || !s.file || !Number.isInteger(s.page) || s.page < 1)) {
        throw Error('問題ID・版・問い・答え・判定基準・出典を確認してください。');
      }
      ids.add(q.id);
    }
    return deck;
  }
  function initial() {
    return {
      schemaVersion: 1, reviews: [], presentations: [], cards: {}, garden: { coins: 0, items: [], draws: [] },
      settings: { batchSize: 3 },
      session: null
    };
  }
  function validateState(state) {
    if (!state || state.schemaVersion !== 1 || !Array.isArray(state.reviews) ||
      !state.cards || Array.isArray(state.cards) || typeof state.cards !== 'object' ||
      !state.garden || !Number.isSafeInteger(state.garden.coins) || state.garden.coins < 0 ||
      !Array.isArray(state.garden.items) || state.garden.items.some(id => !shop.some(i => i.id === id)) ||
      new Set(state.garden.items).size !== state.garden.items.length || !state.settings ||
      (state.settings.notificationEnabled !== undefined && typeof state.settings.notificationEnabled !== 'boolean') ||
      (state.settings.iCloudBackup !== undefined && typeof state.settings.iCloudBackup !== 'boolean') ||
      (state.settings.notificationTime !== undefined && !/^([01]\d|2[0-3]):[0-5]\d$/.test(state.settings.notificationTime)) || state.settings.batchSize !== 3) {
      throw Error('学習記録の形式が違います。元のファイルは消していません。');
    }
    if (state.garden.draws !== undefined) {
      if (!Array.isArray(state.garden.draws)) throw Error('ガチャの記録を読み取れません。');
      const draws = new Set(), animals = new Set();
      for (const draw of state.garden.draws) {
        if (!draw || typeof draw.id !== 'string' || !draw.id || draws.has(draw.id) ||
          !state.garden.items.includes(draw.animalId) || animals.has(draw.animalId) ||
          !Number.isFinite(Date.parse(draw.drawnAt))) throw Error('ガチャの記録を読み取れません。');
        draws.add(draw.id);
        animals.add(draw.animalId);
      }
    }
    const ids = new Set();
    for (const r of state.reviews) {
      if (!r || typeof r.id !== 'string' || !r.id || ids.has(r.id) || typeof r.questionId !== 'string' ||
        !Number.isInteger(r.questionVersion) || r.questionVersion < 1 ||
        !['good', 'again'].includes(r.result) || !Number.isFinite(Date.parse(r.reviewedAt))) {
        throw Error('回答履歴を読み取れません。');
      }
      ids.add(r.id);
    }
    if (state.presentations !== undefined) {
      if (!Array.isArray(state.presentations)) throw Error('出題履歴を読み取れません。');
      const shown = new Set();
      for (const event of state.presentations) {
        if (!event || typeof event.id !== 'string' || !event.id || shown.has(event.id) ||
          typeof event.deckId !== 'string' || typeof event.questionId !== 'string' ||
          !Number.isInteger(event.questionVersion) || event.questionVersion < 1 ||
          !Number.isFinite(Date.parse(event.presentedAt))) throw Error('出題履歴を読み取れません。');
        shown.add(event.id);
      }
    }
    for (const c of Object.values(state.cards)) {
      if (!c || !Number.isInteger(c.version) || c.version < 1 || !Number.isInteger(c.level) ||
        c.level < 0 || c.level > 5 || !Number.isFinite(Date.parse(c.dueAt)) ||
        !Number.isInteger(c.seen) || c.seen < 1 || !Number.isInteger(c.lapses) || c.lapses < 0 ||
        typeof c.lastSuccessDay !== 'string' || typeof c.retryDay !== 'string' ||
        (c.retryAfter !== null && (!Number.isInteger(c.retryAfter) || c.retryAfter < 0))) {
        throw Error('復習状態を読み取れません。');
      }
    }
    if (state.session !== null) {
      const s = state.session;
      if (!s || typeof s.id !== 'string' || typeof s.deckId !== 'string' ||
        !Array.isArray(s.queue) || s.queue.length > 3 || !Number.isInteger(s.index) ||
        s.index < 0 || s.index > s.queue.length || !Number.isInteger(s.correct) ||
        s.correct < 0 || s.correct > s.index || typeof s.closed !== 'boolean' ||
        typeof s.answerShown !== 'boolean' || !Number.isFinite(Date.parse(s.presentedAt)) ||
        (s.revealedAt !== null && !Number.isFinite(Date.parse(s.revealedAt))) ||
        (s.answerShown && (s.revealedAt === null || s.index >= s.queue.length)) ||
        s.queue.some(q => typeof q.id !== 'string' || !Number.isInteger(q.version) || q.version < 1)) {
        throw Error('途中の学習記録を読み取れません。');
      }
    }
    return state;
  }
  function reconcile(state, deck) {
    const next = copy(validateState(state));
    const s = next.session;
    if (s && (s.deckId !== deck.id || s.queue.some(ref =>
      !deck.questions.some(q => q.id === ref.id && q.version === ref.version)))) next.session = null;
    return next;
  }
  function select(state, deck, now) {
    const due = [], fresh = [], retry = [];
    for (const q of deck.questions) {
      const c = state.cards[q.id];
      if (!c || c.version !== q.version) fresh.push(q);
      else if (Date.parse(c.dueAt) <= now.getTime()) due.push(q);
      else if (c.retryAfter !== null && state.reviews.length >= c.retryAfter && c.retryDay !== day(now)) retry.push(q);
    }
    due.sort((a, b) => Date.parse(state.cards[a.id].dueAt) - Date.parse(state.cards[b.id].dueAt));
    // A bounded batch, never an obligation to clear the entire queue.
    return [...due, ...fresh, ...retry].slice(0, 3).map(q => ({ id: q.id, version: q.version }));
  }
  function recordPresentation(state, now) {
    const s = state.session;
    if (!s || s.closed || s.index >= s.queue.length) return state;
    const id = `${s.id}:${s.index}`;
    state.presentations = state.presentations || [];
    if (!state.presentations.some(event => event.id === id)) {
      const q = s.queue[s.index];
      state.presentations.push({ id, deckId: s.deckId, questionId: q.id, questionVersion: q.version,
        presentedAt: now.toISOString() });
    }
    return state;
  }
  function statistics(state) {
    const days = {}, questions = {};
    const key = (deckId, questionId) => JSON.stringify([deckId || '', questionId]);
    const counts = event => {
      const id = key(event.deckId, event.questionId);
      return questions[id] || (questions[id] = { presented: 0, correct: 0, mistakes: 0 });
    };
    const shown = new Set();
    for (const event of state.presentations || []) {
      counts(event).presented++;
      shown.add(event.id);
    }
    for (const review of state.reviews) {
      const date = review.reviewedDay || day(new Date(review.reviewedAt));
      days[date] = (days[date] || 0) + 1;
      const item = counts(review);
      // Older versions recorded only completed answers. Count each of those as one presentation.
      if (!shown.has(review.id)) item.presented++;
      item[review.result === 'good' ? 'correct' : 'mistakes']++;
    }
    return { days, questions };
  }
  function questionStatistics(stats, deckId, questionId) {
    return stats.questions[JSON.stringify([deckId, questionId])] || { presented: 0, correct: 0, mistakes: 0 };
  }
  function start(state, deck, now) {
    const next = reconcile(state, deck);
    const queue = select(next, deck, now);
    next.session = {
      id: `${now.getTime()}-${Math.random().toString(36).slice(2)}`,
      deckId: deck.id, queue, index: 0, correct: 0, closed: false,
      answerShown: false, presentedAt: now.toISOString(), revealedAt: null
    };
    return recordPresentation(next, now);
  }
  function ensureSession(state, deck, now) {
    const next = reconcile(state, deck);
    if (!next.session || ((next.session.closed || next.session.index >= next.session.queue.length) &&
      day(new Date(next.session.presentedAt)) !== day(now))) {
      return start(next, deck, now);
    }
    return recordPresentation(next, now);
  }
  function dispatch(state, deck, action, payload = {}, now = new Date(), random = Math.random) {
    let next = reconcile(state, deck);
    const s = next.session;
    if (action === 'start') return start(next, deck, now);
    if (action === 'finish') {
      if (s) s.closed = true;
    } else if (action === 'reveal') {
      if (!s || s.closed || s.index >= s.queue.length) throw Error('問題を開き直してください。');
      s.answerShown = true;
      s.revealedAt = s.revealedAt || now.toISOString();
    } else if (action === 'rate') {
      if (next.reviews.some(r => r.id === payload.eventId)) return next;
      if (!s || s.closed || !s.answerShown || s.index >= s.queue.length ||
        payload.eventId !== `${s.id}:${s.index}` || !['good', 'again'].includes(payload.result)) {
        throw Error('先に答え合わせをしてください。');
      }
      const q = s.queue[s.index];
      const old = next.cards[q.id];
      const c = old && old.version === q.version ? old : {
        version: q.version, level: 0, seen: 0, lapses: 0,
        lastSuccessDay: '', retryAfter: null, retryDay: ''
      };
      const today = day(now);
      const isRetry = c.retryAfter !== null && Date.parse(c.dueAt || '') > now.getTime();
      c.seen += 1;
      if (payload.result === 'again') {
        c.level = 0;
        c.lapses += 1;
        c.dueAt = later(now, 1);
        c.retryAfter = next.reviews.length + 3;
      } else {
        if (c.lastSuccessDay !== today) {
          c.level = Math.min(c.level + 1, intervals.length);
          c.lastSuccessDay = today;
          c.dueAt = later(now, intervals[c.level - 1]);
        }
        c.retryAfter = null;
        s.correct += 1;
      }
      if (isRetry) c.retryDay = today;
      next.cards[q.id] = c;
      next.reviews.push({
        id: payload.eventId, questionId: q.id, questionVersion: q.version, deckId: deck.id,
        reviewedAt: now.toISOString(), reviewedDay: today, result: payload.result,
        recallMs: Math.max(0, Date.parse(s.revealedAt) - Date.parse(s.presentedAt))
      });
      if (payload.result === 'good') next.garden.coins += 1;
      s.index += 1;
      s.answerShown = false;
      s.presentedAt = now.toISOString();
      s.revealedAt = null;
      recordPresentation(next, now);
    } else if (action === 'draw') {
      if (typeof payload.eventId !== 'string' || !payload.eventId) throw Error('ガチャの操作を読み取れません。');
      const draws = next.garden.draws || [];
      if (draws.some(draw => draw.id === payload.eventId)) return next;
      const available = shop.filter(item => !next.garden.items.includes(item.id));
      if (!available.length) throw Error('すべての動物がそろっています。');
      if (next.garden.coins < gachaCost) throw Error('ガチャには10コイン必要です。');
      const value = random();
      if (!Number.isFinite(value) || value < 0 || value >= 1) throw Error('抽選できませんでした。コインは使っていません。');
      const animal = available[Math.floor(value * available.length)];
      next.garden.coins -= gachaCost;
      next.garden.items.push(animal.id);
      next.garden.draws = [...draws, { id: payload.eventId, animalId: animal.id, drawnAt: now.toISOString() }];
    } else if (action === 'settings') {
      next.settings = { ...next.settings, ...payload, batchSize: 3 };
    } else throw Error('この操作は使えません。');
    return validateState(next);
  }
  return { initial, validateDeck, validateState, reconcile, start, ensureSession, dispatch, select, shop, gachaCost, day, statistics, questionStatistics };
})();
if (typeof module !== 'undefined') module.exports = RecallCore;
