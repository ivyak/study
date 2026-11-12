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
  assert.equal(state.session.queue.length, 3);
  assert.throws(() => core.dispatch(state, deck, 'rate', { result: 'good' }, date()));
  const id = `${state.session.id}:0`;
  state = rate(state, 'again');
  const loaded = core.validateState(JSON.parse(JSON.stringify(state)));
  assert.equal(loaded.session.index, 1);
  assert.equal(loaded.garden.coins, 1);
  assert.equal(core.dispatch(loaded, deck, 'rate', { eventId: id, result: 'again' }).garden.coins, 1);
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
test('coins cannot be spent twice, and malformed backups are rejected', () => {
  let s = core.start(core.initial(), deck, date());
  for (let i = 0; i < 3; i++) s = rate(s, 'good');
  s = core.dispatch(s, deck, 'buy', { id: 'sprout' });
  assert.equal(s.garden.coins, 0);
  assert.deepEqual(s.garden.items, ['sprout']);
  assert.throws(() => core.dispatch(s, deck, 'buy', { id: 'sprout' }));
  const broken = structuredClone(s); broken.garden.coins = -1;
  assert.throws(() => core.validateState(broken));
  const duplicate = structuredClone(s); duplicate.reviews.push(duplicate.reviews[0]);
  assert.throws(() => core.validateState(duplicate));
});
test('stopping after one question saves the reward and never forces the remaining batch', () => {
  const s = core.dispatch(rate(core.start(core.initial(), deck, date()), 'good'), deck, 'finish');
  assert.equal(s.session.closed, true);
  assert.equal(s.session.index, 1);
  assert.equal(s.garden.coins, 1);
});
test('a completed batch opens the first due question directly on the following day', () => {
  let s = core.start(core.initial(), deck, date());
  for (let i = 0; i < 3; i++) s = rate(s, 'good');
  assert.equal(s.session.index, 3);
  const resumed = core.ensureSession(s, deck, date('2026-11-13T12:00:00+09:00'));
  assert.equal(resumed.session.index, 0);
  assert.equal(resumed.session.queue[0].id, deck.questions[0].id);
  assert.equal(resumed.reviews.length, 3);
});
