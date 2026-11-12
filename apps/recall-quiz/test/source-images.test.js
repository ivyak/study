const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { addSourceImages } = require('../scripts/source-images');
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=', 'base64');
function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'recall-source-test-'));
  const hash = '0'.repeat(64);
  const folder = path.join(root, '.source-cache', hash);
  fs.mkdirSync(folder, { recursive: true });
  fs.writeFileSync(path.join(folder, '1.png'), png);
  return { root, hash, deck: {
    sourceManifest: [{ file: 'lecture.pdf', sha256: hash }],
    questions: [{ sources: [{ file: 'lecture.pdf', page: 1 }] }, { sources: [{ file: 'lecture.pdf', page: 1 }] }]
  } };
}
test('one cached page is embedded once and shared by all matching references', () => {
  const { root, hash, deck } = fixture();
  try {
    addSourceImages(deck, root, root);
    assert.equal(Object.keys(deck.sourceImages).length, 1);
    assert.equal(deck.questions[0].sources[0].imageKey, `${hash}:1`);
    assert.equal(deck.questions[1].sources[0].imageKey, `${hash}:1`);
    assert.equal(deck.sourceImages[`${hash}:1`], 'data:image/png;base64,' + png.toString('base64'));
  } finally { fs.rmSync(root, { recursive: true }); }
});
test('a changed PDF cannot silently reuse screenshots from the old hash', () => {
  const { root, deck } = fixture();
  try {
    fs.writeFileSync(path.join(root, 'lecture.pdf'), 'changed document');
    assert.throws(() => addSourceImages(deck, root, root), /原資料が変更/);
  } finally { fs.rmSync(root, { recursive: true }); }
});
