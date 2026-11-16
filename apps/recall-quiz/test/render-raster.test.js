const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { addSourceImages } = require('../scripts/source-images');
const crypto = require('node:crypto');
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAAXNSR0IArs4c6QAAAERlWElmTU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAAA6ABAAMAAAABAAEAAKACAAQAAAABAAAACqADAAQAAAABAAAACgAAAAA7eLj1AAAAG0lEQVQYGWP8DwQMRAAmItSAlYwqxBtSRAcPAGmaBBDUFljwAAAAAElFTkSuQmCC', 'base64');

test('PNG and JPEG source photos render and embed without a pre-existing cache', { skip: process.platform !== 'darwin' }, () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'recall-raster-test-'));
  try {
    fs.writeFileSync(path.join(root, 'board.png'), png);
    execFileSync('sips', ['-s', 'format', 'jpeg', path.join(root, 'board.png'), '--out', path.join(root, 'board.jpg')], { stdio: 'pipe' });
    for (const file of ['board.png', 'board.jpg']) {
      const sha256 = crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex');
      const deck = {
        sourceManifest: [{ file, sha256, pageCount: 1, reviewedPages: [1] }],
        questions: [{ sources: [{ file, page: 1 }] }]
      };
      addSourceImages(deck, root, root);
      assert.equal(deck.questions[0].sources[0].imageKey, `${sha256}:1`);
      const rendered = fs.readFileSync(path.join(root, '.source-cache', sha256, '1.png'));
      assert.deepEqual(rendered.subarray(0, 8), png.subarray(0, 8));
      assert.equal(rendered.readUInt32BE(16), 10);
      assert.equal(rendered.readUInt32BE(20), 10);
      assert.equal(deck.sourceImages[`${sha256}:1`], 'data:image/png;base64,' + rendered.toString('base64'));
    }
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
