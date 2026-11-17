const test = require('node:test');
const assert = require('node:assert/strict');
const { IDBFactory } = require('fake-indexeddb');
const core = require('../src/core');
const Store = require('../src/storage');
function store() { return new Store({ indexedDB: new IDBFactory(), name: 'quiz' }); }
async function put(s, key, value) {
  const db = await s.open();
  await new Promise((resolve, reject) => {
    const tx = db.transaction('records', 'readwrite');
    tx.objectStore('records').put(value, key);
    tx.oncomplete = resolve; tx.onabort = () => reject(tx.error);
  });
}
test('first use and state changes persist with a backup in one transaction', async () => {
  const s = store(), before = await s.read();
  assert.equal(before.state.garden.coins, 0);
  const first = await s.update(r => ({ ...r, selectedDeckId: 'calc2-lesson01' }), before.revision);
  const next = await s.update(r => { r.state.garden.coins = 10; return r; }, first.revision);
  assert.equal((await s.read()).state.garden.coins, 10);
  assert.equal(next.revision, 2);
  await put(s, 'current', { broken: true });
  assert.equal((await s.read()).state.garden.coins, 0);
  assert.match(s.notice, /バックアップ/);
});
test('invalid state changes abort without spending coins or replacing the backup', async () => {
  const s = store();
  const first = await s.update(r => { r.state.garden.coins = 10; return r; }, 0);
  await assert.rejects(s.update(r => { r.state.garden.coins = -1; return r; }, first.revision));
  assert.deepEqual(await s.read(), first);
});
test('a second tab cannot overwrite a newer record', async () => {
  const s = store(), second = new Store({ indexedDB: s.factory, name: s.name });
  const first = await s.update(r => ({ ...r, selectedDeckId: 'calc2-lesson01' }), 0);
  await second.read();
  const updated = await s.update(r => { r.state.garden.coins = 10; return r; }, first.revision);
  await assert.rejects(second.update(r => r, first.revision), { name: 'ConflictError' });
  assert.deepEqual(await second.read(), updated);
});
test('concurrent requests use transactions and only one stale revision can commit', async () => {
  const s = store();
  const first = await s.update(r => { r.state.garden.coins = 10; return r; }, 0);
  const spend = r => { r.state.garden.coins -= 10; return r; };
  const results = await Promise.allSettled([s.update(spend, first.revision), s.update(spend, first.revision)]);
  assert.equal(results.filter(r => r.status === 'fulfilled').length, 1);
  assert.equal((await s.read()).state.garden.coins, 0);
});
test('damaged records never silently reset, and recovery preserves the last intact backup', async () => {
  const s = store();
  await put(s, 'current', 'broken');
  await assert.rejects(s.read());
  const good = { schemaVersion: 1, revision: 3, selectedDeckId: null, state: core.initial() };
  await put(s, 'backup', good);
  assert.deepEqual(await s.read(), good);
  await s.update(r => r, good.revision);
  assert.equal((await s.read()).revision, 4);
});
