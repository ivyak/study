const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../src/core');
const deck = require('../decks/calc2-lesson01.json');
const date = value => new Date(value || '2026-11-12T12:00:00+09:00');
function rate(state, result, now = date()) {
  const shown = core.dispatch(state, deck, 'reveal', {}, now);
  return core.dispatch(shown, deck, 'rate', { eventId: `${shown.session.id}:${shown.session.index}`, result }, now);
}
test('bounded recall, immediate feedback and exactly-once rewards survive reload', () => {
  let state = core.ensureSession(core.initial(), deck, date());
  assert.equal(state.session.queue.length, 5);
  assert.throws(() => core.dispatch(state, deck, 'rate', { result: 'good' }, date()));
  const id = `${state.session.id}:0`;
  state = rate(state, 'again');
  const loaded = core.validateState(JSON.parse(JSON.stringify(state)));
  assert.equal(loaded.session.index, 1);
  assert.equal(loaded.garden.coins, 0);
  assert.equal(core.dispatch(loaded, deck, 'rate', { eventId: id, result: 'again' }).garden.coins, 0);
  assert.equal(state.reviews[0].questionId, deck.questions[0].id);
});
test('a failed card returns after intervening recalls, at most once again that day', () => {
  const small = { ...deck, questions: deck.questions.slice(0, 3) };
  let s = core.start(core.initial(), small, date());
  for (const r of ['again', 'good', 'good']) s = rate(s, r);
  s = core.start(s, small, date());
  assert.equal(s.session.queue.length, 1);
  assert.equal(s.session.queue[0].id, small.questions[0].id);
  s = rate(s, 'again');
  assert.equal(core.select(s, small, date()).length, 0);
  assert.ok(core.select(s, small, date('2026-11-13T00:01:00+09:00')).length > 0);
});
test('same-day retries do not turn into a long interval; success on another day does', () => {
  let s = core.start(core.initial(), deck, date());
  s = rate(s, 'good');
  const firstDue = s.cards[deck.questions[0].id].dueAt;
  s = core.start(s, deck, date('2026-11-13T12:00:00+09:00'));
  s = rate(s, 'good', date('2026-11-13T12:00:00+09:00'));
  assert.equal(s.cards[deck.questions[0].id].level, 2);
  assert.notEqual(s.cards[deck.questions[0].id].dueAt, firstDue);
});
test('updated question versions preserve the ledger and garden but re-enter learning', () => {
  let s = rate(core.start(core.initial(), deck, date()), 'good');
  const updated = structuredClone(deck);
  updated.questions[0].version++;
  s = core.reconcile(s, updated);
  assert.equal(s.session, null);
  assert.equal(s.reviews.length, 1);
  assert.equal(s.garden.coins, 1);
  assert.equal(core.select(s, updated, date())[0].id, deck.questions[0].id);
});
test('legacy animal ownership and coin balances survive updates, while malformed backups are rejected', () => {
  const legacy = core.initial();
  legacy.garden = { coins: 42, items: ['sprout', 'flower', 'tree'] };
  const s = core.reconcile(legacy, deck);
  assert.deepEqual(s.garden, legacy.garden);
  assert.throws(() => core.dispatch(s, deck, 'buy', { id: 'sprout' }));
  const broken = structuredClone(s); broken.garden.coins = -1;
  assert.throws(() => core.validateState(broken));
  const answered = rate(core.start(s, deck, date()), 'good');
  answered.reviews.push(answered.reviews[0]);
  assert.throws(() => core.validateState(answered));
});
test('stopping after one question saves the reward and never forces the remaining batch', () => {
  const s = core.dispatch(rate(core.start(core.initial(), deck, date()), 'good'), deck, 'finish');
  assert.equal(s.session.closed, true);
  assert.equal(s.session.index, 1);
  assert.equal(s.garden.coins, 1);
});
test('a completed batch opens the first due question directly on the following day', () => {
  let s = core.start(core.initial(), deck, date());
  for (let i = 0; i < 5; i++) s = rate(s, 'good');
  assert.equal(s.session.index, 5);
  const resumed = core.ensureSession(s, deck, date('2026-11-13T12:00:00+09:00'));
  assert.equal(resumed.session.index, 0);
  assert.equal(resumed.session.queue[0].id, deck.questions[0].id);
  assert.equal(resumed.reviews.length, 5);
});
test('calendar and question counts preserve legacy answers, versions, unfinished presentations and duplicate protection', () => {
  let state = core.start(core.initial(), deck, date());
  const first = deck.questions[0];
  let stats = core.statistics(state);
  assert.deepEqual(core.questionStatistics(stats, deck.id, first.id), { presented: 1, correct: 0, uncertain: 0, mistakes: 0 });
  state = core.ensureSession(state, deck, date());
  assert.equal(state.presentations.length, 1);
  state = rate(state, 'again');
  const event = state.reviews[0];
  state = core.dispatch(state, deck, 'rate', { eventId: event.id, result: 'again' });
  const legacy = structuredClone(state);
  delete legacy.presentations;
  delete legacy.reviews[0].reviewedDay;
  core.validateState(legacy);
  assert.equal(core.questionStatistics(core.statistics(legacy), deck.id, first.id).presented, 1);
  const updated = structuredClone(deck);
  updated.questions[0].version++;
  state = core.start(state, updated, date('2026-11-13T12:00:00+09:00'));
  state = core.dispatch(state, updated, 'reveal', {}, date('2026-11-13T12:00:00+09:00'));
  state = core.dispatch(state, updated, 'rate', { eventId: `${state.session.id}:0`, result: 'good' }, date('2026-11-13T12:00:00+09:00'));
  stats = core.statistics(state);
  assert.deepEqual(core.questionStatistics(stats, deck.id, first.id), { presented: 2, correct: 1, uncertain: 0, mistakes: 1 });
  assert.equal(stats.days[event.reviewedDay], 1);
  assert.equal(Object.values(stats.days).reduce((a, b) => a + b, 0), 2);
  assert.equal(state.garden.coins, 1);
});
test('calendar uses the recorded answer day even after the device timezone changes', () => {
  const state = core.initial();
  state.reviews.push({ id: 'old', deckId: deck.id, questionId: deck.questions[0].id, questionVersion: 1,
    reviewedAt: '2026-12-31T15:10:00Z', reviewedDay: '2027-1-1', result: 'good' });
  assert.deepEqual(core.statistics(state).days, { '2027-1-1': 1 });
  assert.deepEqual(core.questionStatistics(core.statistics(state), 'other', deck.questions[0].id), { presented: 0, correct: 0, uncertain: 0, mistakes: 0 });
});

test('study selection prioritizes fewer successful recalls and randomizes ties across lessons', () => {
  const pool = { id: 'study-all', studyScope: { type: 'all' }, questions: deck.questions.slice(0, 4).map((q, i) => ({ ...q, deckId: i < 2 ? 'one' : 'two' })) };
  const state = core.initial();
  const add = (i, version, result) => state.reviews.push({ id: `review-${state.reviews.length}`, deckId: pool.questions[i].deckId,
    questionId: pool.questions[i].id, questionVersion: version, result, reviewedAt: date().toISOString() });
  add(0, pool.questions[0].version, 'good'); add(0, pool.questions[0].version, 'good'); add(1, 1, 'good'); add(2, 1, 'again');
  add(3, 2, 'good');
  const a = core.selectStudy(state, pool, () => 0);
  const b = core.selectStudy(state, pool, () => .5);
  assert.deepEqual(new Set(a.slice(0, 2).map(q => q.id)), new Set(pool.questions.slice(2).map(q => q.id)));
  assert.equal(a[2].id, pool.questions[1].id);
  assert.notDeepEqual(a, b);
  assert.equal(new Set(a.map(q => q.id)).size, 4);
});
test('mixed sessions keep the source lesson for both presentation and answer records', () => {
  const pool = { ...deck, id: 'study-all', studyScope: { type: 'all' }, questions: deck.questions.map(q => ({ ...q, deckId: deck.id })) };
  let state = core.start(core.initial(), pool, date(), () => .999);
  assert.equal(state.presentations[0].deckId, deck.id);
  state = core.dispatch(state, pool, 'reveal', {}, date());
  state = core.dispatch(state, pool, 'rate', { eventId: `${state.session.id}:0`, result: 'good' }, date());
  assert.equal(state.reviews[0].deckId, deck.id);
  state = core.dispatch(state, pool, 'finish');
  const saved = core.validateState(JSON.parse(JSON.stringify(state)));
  assert.deepEqual(saved.session.scope, { type: 'all' });
  const home = core.dispatch(saved, pool, 'home');
  assert.equal(home.session, null);
  assert.equal(home.reviews.length, 1);
  assert.equal(home.garden.coins, 1);
});

test('legacy three-question sessions migrate without losing answers', () => {
  const legacy = core.start(core.initial(), deck, date());
  legacy.settings.batchSize = 3;
  legacy.session.queue = legacy.session.queue.slice(0, 3);
  const restored = core.reconcile(legacy, deck);
  assert.equal(restored.settings.batchSize, 5);
  assert.equal(restored.session.queue.length, 3);
  assert.equal(core.start(restored, deck, date()).session.queue.length, 5);
});
test('uncertain answers remain separate from successes and mistakes after reload', () => {
  let state = core.start(core.initial(), deck, date());
  const id = state.session.queue[0].id;
  state = rate(state, 'uncertain');
  state = core.validateState(JSON.parse(JSON.stringify(state)));
  assert.equal(state.reviews[0].result, 'uncertain');
  assert.equal(state.session.correct, 0);
  assert.equal(state.garden.coins, 0);
  assert.equal(state.cards[id].level, 0);
  assert.deepEqual(core.questionStatistics(core.statistics(state), deck.id, id),
    { presented: 1, correct: 0, uncertain: 1, mistakes: 0 });
});
test('timeouts reveal at fifteen seconds, then record one failure after fifteen more seconds', () => {
  let state = core.start(core.initial(), deck, date());
  const payload = { eventId: `${state.session.id}:0`, answerShown: false };
  const at = ms => new Date(date().getTime() + ms);
  state = core.dispatch(state, deck, 'timeout', payload, at(14999));
  assert.equal(state.session.answerShown, false);
  state = core.dispatch(state, deck, 'timeout', payload, at(15000));
  assert.equal(state.session.answerShown, true);
  assert.equal(state.reviews.length, 0);
  const answer = { ...payload, answerShown: true };
  state = core.dispatch(state, deck, 'timeout', answer, at(29999));
  assert.equal(state.session.index, 0);
  state = core.dispatch(state, deck, 'timeout', answer, at(30000));
  assert.equal(state.session.index, 1);
  assert.equal(state.reviews[0].result, 'again');
  assert.equal(state.reviews[0].recallMs, 15000);
  assert.equal(state.garden.coins, 0);
  state = core.dispatch(state, deck, 'timeout', answer, at(31000));
  assert.equal(state.reviews.length, 1);
  assert.equal(state.session.answerShown, false);
});
