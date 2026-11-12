const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../src/core');
const Store = require('../src/storage');
function manager() {
  const files = new Map();
  return {
    files, createDirectory() {}, joinPath: (a, b) => a + '/' + b,
    fileExists: p => files.has(p), readString: p => files.get(p),
    writeString: (p, s) => files.set(p, s), remove: p => files.delete(p),
    move(a, b) { files.set(b, files.get(a)); files.delete(a); }
  };
}
test('interrupted replacement recovers the validated pending state', () => {
  const fm = manager(), store = new Store(fm, 'quiz');
  store.save(core.initial());
  const next = core.initial(); next.garden.coins = 2;
  fm.move = () => { throw Error('interruption'); };
  assert.throws(() => store.save(next));
  assert.equal(new Store(fm, 'quiz').load().garden.coins, 2);
});
test('corrupt primary falls back to backup, and total corruption never silently resets', () => {
  const fm = manager(), store = new Store(fm, 'quiz');
  store.save(core.initial()); store.save(core.initial());
  fm.files.set(store.path, 'broken');
  assert.equal(new Store(fm, 'quiz').load().garden.coins, 0);
  fm.files.set(store.backup, 'broken');
  assert.throws(() => new Store(fm, 'quiz').load());
});
test('a stale second view cannot overwrite a newer save', () => {
  const fm = manager(), first = new Store(fm, 'quiz');
  first.save(core.initial());
  const second = new Store(fm, 'quiz');
  const next = core.initial(); next.garden.coins = 3;
  first.save(next);
  assert.throws(() => second.save(core.initial()));
  assert.equal(new Store(fm, 'quiz').load().garden.coins, 3);
});
