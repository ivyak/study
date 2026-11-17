const test = require('node:test');
const assert = require('node:assert/strict');
const { IDBFactory } = require('fake-indexeddb');
const core = require('../src/core');
const Store = require('../src/storage');
const { Runtime } = require('../src/web');
const first = require('../decks/calc2-lesson01.json');
const second = { ...first, id: 'second', title: '別の教科', questions: first.questions.map(q => ({ ...q, id: `second-${q.id}` })) };
function runtime() {
  const store = new Store({ indexedDB: new IDBFactory() });
  const requests = [];
  const app = new Runtime({ store, defaultDeckId: first.id, baseURL: 'https://example.com/study/',
    decks: [first, second].map(d => ({ id: d.id, title: d.title, file: `./decks/${d.id}.json` })),
    fetch: async url => { requests.push(url.href); return { ok: true, json: async () => url.href.includes('/second.') ? second : first }; }
  });
  return { app, store, requests };
}
test('the home screen loads no questions and an explicit lesson selection survives reopening', async () => {
  const { app, store, requests } = runtime();
  await app.start();
  assert.deepEqual(requests, []);
  assert.equal(app.record.state.session, null);
  await app.dispatch('selectDeck', { id: second.id });
  assert.equal((await app.snapshot()).selectedDeckId, second.id);
  assert.equal((await app.export()).selectedDeckId, second.id);
  const reopened = new Runtime({ store, decks: app.catalog, baseURL: app.baseURL, fetch: app.fetch, defaultDeckId: first.id });
  assert.equal((await reopened.start()).deck.id, second.id);
});
test('Scriptable and browser JSON backups import without losing answers, coins or animals', async () => {
  const { app } = runtime(); await app.start();
  const legacy = core.initial();
  legacy.garden = { coins: 20, items: ['sprout'] };
  legacy.settings = { batchSize: 3, notificationEnabled: true, notificationTime: '12:30', iCloudBackup: true };
  await app.restore(legacy);
  assert.deepEqual((await app.snapshot()).state.garden, legacy.garden);
  assert.deepEqual((await app.snapshot()).state.settings, { batchSize: 5 });
  const backup = await app.export();
  await app.dispatch('draw', { eventId: 'once' });
  assert.equal((await app.snapshot()).state.garden.coins, 10);
  await app.restore(backup);
  assert.equal((await app.snapshot()).state.garden.coins, 20);
});
test('old browser-preview records migrate once, while malformed imports never erase state', async () => {
  const { app } = runtime();
  const old = core.initial(); old.garden.coins = 42;
  const legacyStorage = { getItem: key => key === 'recall-quiz-preview-v1' ? JSON.stringify(old) : second.id };
  await app.start(legacyStorage);
  assert.equal(app.record.selectedDeckId, second.id);
  assert.equal(app.record.state.session, null);
  assert.equal(app.record.state.garden.coins, 42);
  await assert.rejects(app.restore({ state: { broken: true } }));
  assert.equal((await app.snapshot()).state.garden.coins, 42);
});

test('mixed and subject sessions preserve their scope and original deck IDs across reload and export', async () => {
  const { app, store } = runtime();
  await app.start();
  await app.dispatch('startStudy', { scope: { type: 'subject', title: second.title } });
  assert.ok(app.record.state.session.queue.every(q => q.deckId === second.id));
  await app.dispatch('reveal');
  await app.dispatch('rate', { eventId: `${app.record.state.session.id}:0`, result: 'good' });
  assert.equal(app.record.state.reviews[0].deckId, second.id);
  await app.dispatch('finish');
  const reopened = new Runtime({ store, decks: app.catalog, baseURL: app.baseURL, fetch: app.fetch });
  await reopened.start();
  assert.equal(reopened.record.state.session.closed, true);
  assert.deepEqual(reopened.record.state.session.scope, { type: 'subject', title: second.title });
  const exported = await reopened.export();
  await reopened.dispatch('home');
  assert.equal(reopened.record.state.session, null);
  await reopened.restore(exported);
  assert.deepEqual(reopened.record.state.session, exported.state.session);
  await reopened.dispatch('startStudy', { scope: { type: 'all' } });
  assert.deepEqual(reopened.record.state.session.scope, { type: 'all' });
  assert.equal(reopened.deck.questions.length, first.questions.length + second.questions.length);
  assert.equal(reopened.record.state.reviews.length, 1);
  assert.equal(reopened.record.state.garden.coins, 1);
});
test('reading a lesson is lazy and does not start a session or record a presentation', async () => {
  const { app, requests } = runtime();
  await app.start();
  await app.loadDeck(second.id);
  assert.deepEqual(requests, ['https://example.com/study/decks/second.json']);
  assert.equal(app.record.state.session, null);
  assert.deepEqual(app.record.state.presentations, []);
  await app.dispatch('selectDeck', { id: second.id });
  await app.dispatch('finish');
  await app.dispatch('selectDeck', { id: second.id });
  assert.equal(app.record.state.session.closed, false);
  assert.equal(app.record.state.session.index, 0);
});
