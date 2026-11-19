const test = require('node:test');
const assert = require('node:assert/strict');
const { IDBFactory } = require('fake-indexeddb');
const answers = require('../src/answers');
const core = require('../src/core');
const Store = require('../src/storage');
const { Runtime } = require('../src/web');
const knowledge = require('../decks/bookkeeping-chapter02.json');
const exercises = require('../decks/bookkeeping-chapter02-exercises.json');
const now = new Date('2026-11-19T09:00:00Z');

test('blank worksheets never leak answers, and answers cannot contain blanks', () => {
  for (const q of exercises.questions) {
    core.validateDeck(exercises);
    const prompt = answers.render(q.promptBlocks, undefined, { allowBlanks: true });
    assert.match(prompt, /<input type="text"/);
    assert.doesNotMatch(prompt, /value="/);
    assert.doesNotMatch(answers.render(q.answerBlocks), /<input/);
  }
  assert.throws(() => answers.render([{ type: 'table', headers: ['摘要', '金額'], rows: [['経費', null]] }]));
  assert.throws(() => answers.validate([{ type: 'text', text: '' }]));
});

test('exercise sessions remain ordered and never time out, including after restore', () => {
  const deck = { ...exercises, questions: [...exercises.questions, ...exercises.questions.map(q => ({ ...q, id: `${q.id}-repeat` }))] };
  let state = core.dispatch(core.initial(), deck, 'start', {}, now);
  assert.equal(state.session.mode, 'exercise');
  assert.deepEqual(state.session.queue.map(q => q.id), deck.questions.map(q => q.id));
  assert.doesNotThrow(() => core.validateState(JSON.parse(JSON.stringify(state))));
  const after = new Date(now.getTime() + 1000000);
  assert.deepEqual(core.dispatch(state, deck, 'timeout', {}, after), state);
  state = core.dispatch(state, deck, 'reveal', {}, after);
  assert.equal(state.session.answerShown, true);
  assert.deepEqual(core.dispatch(state, deck, 'timeout', {}, after), state);
  state = core.dispatch(state, deck, 'rate', { eventId: `${state.session.id}:0`, result: 'good' }, after);
  assert.equal(state.reviews[0].studyType, 'exercise');
  assert.equal(state.reviews[0].deckId, exercises.id);
  assert.equal(state.garden.coins, 1);
  assert.equal(state.session.index, 1);
});

test('default and exercise scopes load separate questions and preserve mode after reopening', async () => {
  const source = [knowledge, exercises];
  const store = new Store({ indexedDB: new IDBFactory() });
  const options = { store, baseURL: 'https://example.com/', decks: source.map(d => ({ id: d.id, title: d.title, studyType: d.studyType, file: `${d.id}.json` })),
    fetch: async url => ({ ok: true, json: async () => source.find(d => url.pathname === `/${d.id}.json`) }) };
  const runtime = new Runtime(options);
  await runtime.start();
  for (const scope of [{ type: 'all' }, { type: 'subject', title: knowledge.title }]) {
    const deck = await runtime.studyDeck(scope);
    assert.equal(deck.studyType, 'knowledge');
    assert.equal(deck.questions.length, 22);
    assert.ok(deck.questions.every(q => q.deckId === knowledge.id));
  }
  for (const scope of [{ type: 'all', studyType: 'exercise' }, { type: 'subject', title: knowledge.title, studyType: 'exercise' }, { type: 'lesson', id: exercises.id }]) {
    await runtime.dispatch('startStudy', { scope });
    assert.equal(runtime.record.state.session.mode, 'exercise');
    assert.equal(runtime.deck.questions.length, 4);
    assert.ok(runtime.deck.questions.every(q => q.deckId === exercises.id));
  }
  const reopened = new Runtime(options);
  const boot = await reopened.start();
  assert.equal(boot.state.session.mode, 'exercise');
  assert.equal(boot.deck.studyType, 'exercise');
});

test('retired questions preserve old reviews, balances and exact question versions', () => {
  const old = knowledge.retiredQuestions[0];
  const previousDeck = { ...knowledge, questions: [old], retiredQuestions: [] };
  let state = core.dispatch(core.initial(), previousDeck, 'start', {}, now);
  state = core.dispatch(state, previousDeck, 'reveal', {}, now);
  state = core.dispatch(state, previousDeck, 'rate', { eventId: `${state.session.id}:0`, result: 'good' }, now);
  const before = structuredClone(state);
  const updated = core.reconcile(state, knowledge);
  assert.deepEqual(updated.reviews, before.reviews);
  assert.deepEqual(updated.garden, before.garden);
  assert.equal(updated.session, null);
  assert.ok(knowledge.retiredQuestions.some(q => q.id === updated.reviews[0].questionId && q.version === updated.reviews[0].questionVersion));
});
