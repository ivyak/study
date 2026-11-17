const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../src/core.js');
const deck = require('../decks/calc2-lesson01.json');
const now = new Date('2026-11-17T12:00:00+09:00');
function draw(state, id, random = () => 0) {
  return core.dispatch(state, deck, 'draw', { eventId: id }, now, random);
}
test('a draw spends exactly ten coins, persists the result and is idempotent', () => {
  const before = core.initial();
  before.garden.coins = 20;
  const after = draw(before, 'once');
  assert.equal(before.garden.coins, 20);
  assert.equal(after.garden.coins, 10);
  assert.deepEqual(after.garden.items, ['sprout']);
  const loaded = core.validateState(JSON.parse(JSON.stringify(after)));
  assert.deepEqual(draw(loaded, 'once', () => { throw Error('must not draw again'); }), loaded);
  const second = draw(loaded, 'twice');
  assert.equal(second.garden.coins, 0);
  assert.deepEqual(second.garden.items, ['sprout', 'flower']);
});
test('the equal-width draw slots cover all thirteen animals and skip owned animals', () => {
  assert.equal(core.shop.length, 13);
  const before = core.initial();
  before.garden.coins = 10;
  for (let i = 0; i < 13; i++) {
    assert.equal(draw(before, `slot-${i}`, () => (i + .5) / 13).garden.items[0], core.shop[i].id);
  }
  before.garden.items = ['sprout', 'flower', 'tree'];
  assert.equal(draw(before, 'skip-owned').garden.items.at(-1), 'squirrel');
});
test('insufficient coins, missing request IDs and invalid randomness never change the balance', () => {
  const before = core.initial();
  before.garden.coins = 9;
  assert.throws(() => draw(before, 'short'));
  assert.equal(before.garden.coins, 9);
  before.garden.coins = 10;
  for (const value of [-1, 1, NaN, Infinity]) assert.throws(() => draw(before, 'invalid', () => value));
  assert.throws(() => draw(before, ''));
  assert.equal(before.garden.coins, 10);
  assert.equal(before.garden.items.length, 0);
});
test('collection completion stops further draws without charging, including old ownership', () => {
  let state = core.initial();
  state.garden.coins = 150;
  for (let i = 0; i < 13; i++) state = draw(state, `collect-${i}`, () => .99999);
  assert.equal(new Set(state.garden.items).size, 13);
  assert.equal(state.garden.coins, 20);
  assert.throws(() => draw(state, 'complete'));
  assert.equal(state.garden.coins, 20);
  const duplicate = structuredClone(state);
  duplicate.garden.draws.push(duplicate.garden.draws[0]);
  assert.throws(() => core.validateState(duplicate));
});
test('only correct self-assessments earn coins, and repeated events cannot pay twice', () => {
  let state = core.start(core.initial(), deck, now);
  for (const result of ['again', 'good']) {
    state = core.dispatch(state, deck, 'reveal', {}, now);
    const eventId = `${state.session.id}:${state.session.index}`;
    state = core.dispatch(state, deck, 'rate', { eventId, result }, now);
    state = core.dispatch(state, deck, 'rate', { eventId, result }, now);
  }
  assert.equal(state.garden.coins, 1);
  assert.equal(state.reviews.length, 2);
  assert.equal(state.cards[deck.questions[0].id].lapses, 1);
});
