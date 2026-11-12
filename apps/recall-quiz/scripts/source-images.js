const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
function addSourceImages(deck, root, repo) {
  if (!Array.isArray(deck.sourceManifest) || !deck.sourceManifest.length) {
    throw Error('原典画像の同梱にはsourceManifestが必要です。');
  }
  const images = {};
  for (const source of deck.sourceManifest) {
    if (!/^[a-f0-9]{64}$/.test(source.sha256 || '')) throw Error('原資料のハッシュを確認してください。');
    const refs = deck.questions.flatMap(q => q.sources).filter(ref => ref.file === path.basename(source.file));
    const pages = [...new Set(refs.map(ref => ref.page))];
    if (!pages.length) continue;
    const pdf = path.resolve(repo, source.file);
    if (!pdf.startsWith(repo + path.sep)) throw Error('リポジトリ外の原資料です。');
    const folder = path.join(root, '.source-cache', source.sha256);
    if (fs.existsSync(pdf)) {
      const hash = crypto.createHash('sha256').update(fs.readFileSync(pdf)).digest('hex');
      if (hash !== source.sha256) throw Error(`原資料が変更されています。画像と問題を再確認してください：${source.file}`);
    }
    const missing = pages.filter(page => !fs.existsSync(path.join(folder, `${page}.png`)));
    if (missing.length) {
      if (!fs.existsSync(pdf)) throw Error(`原PDFか画像キャッシュが必要です：${source.file}`);
      if (process.platform !== 'darwin') throw Error('画像の初回生成はMacで行ってください。画像を省く場合は --without-source-images を指定します。');
      execFileSync('swift', [
        '-module-cache-path', path.join(os.tmpdir(), 'recall-quiz-swift-cache'),
        path.join(__dirname, 'render-sources.swift'), pdf, folder, ...missing.map(String)
      ], { stdio: 'pipe' });
    }
    for (const page of pages) {
      const key = `${source.sha256}:${page}`;
      const data = fs.readFileSync(path.join(folder, `${page}.png`));
      if (!data.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) throw Error('原典画像のキャッシュが壊れています。');
      images[key] = 'data:image/png;base64,' + data.toString('base64');
    }
    for (const ref of refs) ref.imageKey = `${source.sha256}:${ref.page}`;
  }
  deck.sourceImages = images;
  return deck;
}
module.exports = { addSourceImages };
