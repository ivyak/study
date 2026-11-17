const test = require('node:test');
const assert = require('node:assert/strict');
const { IDBFactory } = require('fake-indexeddb');
const core = require('../src/core');
const Store = require('../src/storage');
const { Runtime } = require('../src/web');
const first = require('../decks/calc2-lesson01.json');
const second = { ...first, id: 'second', title: '別の教科' };
function runtime() {
  const store = new Store({ indexedDB: new IDBFactory() });
  const requests = [];
  const app = new Runtime({ store, defaultDeckId: first.id, baseURL: 'https://example.com/study/',
    decks: [first, second].map(d => ({ id: d.id, title: d.title, file: `./decks/${d.id}.json` })),
    fetch: async url => { requests.push(url.href); return { ok: true, json: async () => url.href.includes('/second.') ? second : first }; }
  });
  return { app, store, requests };
}
test('the web app loads only the active deck and keeps deck selection after reopening', async () => {
  const { app, store, requests } = runtime();
  await app.start();
  assert.deepEqual(requests, ['https://example.com/study/decks/calc2-lesson01.json']);
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
  assert.deepEqual((await app.snapshot()).state.settings, { batchSize: 3 });
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
  assert.equal(app.deck.id, second.id);
  assert.equal(app.record.state.garden.coins, 42);
  await assert.rejects(app.restore({ state: { broken: true } }));
  assert.equal((await app.snapshot()).state.garden.coins, 42);
});
