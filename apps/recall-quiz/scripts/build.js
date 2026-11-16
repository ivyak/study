const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');
const katex = require('katex');
const core = require('../src/core.js');
const { addSourceImages } = require('./source-images.js');
const root = path.resolve(__dirname, '..');
const repo = path.resolve(root, '../..');
const input = process.argv.find(a => a.endsWith('.json'));
const deckPath = input ? path.resolve(repo, input) : path.join(root, 'decks/calc2-lesson01.json');
const htmlEscape = text => text.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function render(text) {
  let result = '', cursor = 0;
  for (const match of text.matchAll(/\\\(([\s\S]*?)\\\)/g)) {
    result += htmlEscape(text.slice(cursor, match.index));
    result += katex.renderToString(match[1], { output: 'mathml', throwOnError: true, trust: false });
    cursor = match.index + match[0].length;
  }
  const remainder = text.slice(cursor);
  if (/\\[()]/.test(remainder)) throw Error('閉じていない数式があります。');
  return (result + htmlEscape(remainder)).replace(/\n/g, '<br>');
}
function compile(file) {
  const deck = core.validateDeck(JSON.parse(fs.readFileSync(file, 'utf8')));
  if (process.argv.includes('--verify-sources')) {
    if (!Array.isArray(deck.sourceManifest) || !deck.sourceManifest.length) throw Error('原資料のハッシュがありません。');
    for (const source of deck.sourceManifest) {
      const sourcePath = path.resolve(repo, source.file);
      if (!sourcePath.startsWith(repo + path.sep)) throw Error('リポジトリ外の原資料です。');
      const hash = crypto.createHash('sha256').update(fs.readFileSync(sourcePath)).digest('hex');
      if (hash !== source.sha256) throw Error(`原資料が変更されています。再確認してください：${source.file}`);
    }
  }
  for (const q of deck.questions) {
    for (const key of ['prompt', 'answer', 'criterion', 'explanation']) q[`${key}Html`] = render(q[key]);
    if (deck.sourceManifest) for (const ref of q.sources) {
      const source = deck.sourceManifest.find(s => path.basename(s.file) === ref.file);
      if (!source || ref.page > source.pageCount || !source.reviewedPages.includes(ref.page)) {
        throw Error(`原資料で照合されていないページです：${q.id}`);
      }
    }
  }
  if (!process.argv.includes('--without-source-images')) addSourceImages(deck, root, repo);
  deck.renderVersion = 1;
  return deck;
}
const deck = compile(deckPath);
// The PC catalog includes every local deck when no single deck was requested.
const decks = input ? [deck] : [deck, ...fs.readdirSync(path.join(root, 'decks'))
  .filter(file => file.endsWith('.json') && file !== path.basename(deckPath))
  .sort()
  .map(file => compile(path.join(root, 'decks', file)))];
const read = name => fs.readFileSync(path.join(root, 'src', name), 'utf8');
const json = value => JSON.stringify(value).replace(/</g, '\\u003c');
const html = read('index.html').replace('/*__STYLE__*/', read('style.css'))
  .replace('/*__CORE__*/', read('core.js')).replace('/*__APP__*/', read('app.js'));
const bundle = '// Variables used by Scriptable.\n// icon-color: green; icon-glyph: seedling;\n' +
  read('core.js') + '\n' + read('storage.js') + '\n' +
  `const QUIZ_DECK = ${json(deck)};\nconst QUIZ_HTML = ${json(html)};\n` + read('scriptable.js');
// Parse top-level await with an async wrapper, without running Scriptable APIs.
new vm.Script(`(async () => { ${bundle}\n})()`);
const output = path.join(root, 'output');
fs.mkdirSync(output, { recursive: true });
fs.writeFileSync(path.join(output, 'Quiz.js'), bundle);
for (const item of decks) {
  fs.writeFileSync(path.join(output, `${item.id}.compiled.json`), JSON.stringify(item, null, 2));
}
const state = core.ensureSession(core.initial(), deck, new Date());
fs.writeFileSync(path.join(output, 'preview.html'), html.replace('__BOOTSTRAP__', json({
  native: false, deck, decks, state, shop: core.shop, notice: ''
})));
console.log(`${deck.questions.length}問をビルドしました。output/Quiz.js をScriptableへ取り込めます。`);
