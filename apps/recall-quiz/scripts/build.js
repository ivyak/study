const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');
const katex = require('katex');
const core = require('../src/core.js');
const answers = require('../src/answers.js');
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
  for (const q of [...deck.questions, ...(deck.retiredQuestions || [])]) {
    for (const key of ['prompt', 'answer', 'criterion', 'explanation']) q[`${key}Html`] = render(q[key]);
    if (q.promptBlocks) q.promptHtml = answers.render(q.promptBlocks, render, { allowBlanks: true });
    if (q.answerBlocks) q.answerHtml = answers.render(q.answerBlocks, render);
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
const decks = input ? [deck] : [deck, ...fs.readdirSync(path.join(root, 'decks'))
  .filter(file => file.endsWith('.json') && file !== path.basename(deckPath))
  .sort().map(file => compile(path.join(root, 'decks', file)))];
if (new Set(decks.map(item => item.id)).size !== decks.length) throw Error('教材IDが重複しています。');
const read = name => fs.readFileSync(path.join(root, 'src', name), 'utf8');
const json = value => JSON.stringify(value).replace(/</g, '\\u003c');
const output = path.join(root, 'output/site');
fs.rmSync(output, { recursive: true, force: true });
for (const folder of ['decks', 'assets/garden', 'assets/sources']) fs.mkdirSync(path.join(output, folder), { recursive: true });
for (const item of decks) {
  for (const [key, data] of Object.entries(item.sourceImages || {})) {
    if (!/^[a-f0-9]{64}:\d+$/.test(key) || !data.startsWith('data:image/png;base64,')) throw Error('原典画像の形式が違います。');
    const file = `assets/sources/${key.replace(':', '-')}.png`;
    fs.writeFileSync(path.join(output, file), Buffer.from(data.slice('data:image/png;base64,'.length), 'base64'));
    item.sourceImages[key] = `./${file}`;
  }
  fs.writeFileSync(path.join(output, 'decks', `${item.id}.json`), JSON.stringify(item));
}
const gardenAssets = Object.fromEntries(core.shop.map(item => {
  const file = `assets/garden/${item.asset}.png`;
  fs.copyFileSync(path.join(root, file), path.join(output, file));
  return [item.asset, `./${file}`];
}));
const manifest = { defaultDeckId: deck.id, decks: decks.map(item => ({ id: item.id, version: item.version,
  title: item.title, subtitle: item.subtitle, scope: item.scope, studyType: item.studyType || 'knowledge', questionCount: item.questions.length,
  file: `./decks/${item.id}.json` })) };
fs.writeFileSync(path.join(output, 'decks/manifest.json'), JSON.stringify(manifest, null, 2));
const runtime = read('storage.js') + '\n' + read('web.js') + '\n' +
  'RecallWeb.start(window.BOOT).then(boot => { window.BOOT = boot;\n' + read('app.js') + '\n}).catch(RecallWeb.failure);';
new vm.Script(read('answers.js') + '\n' + read('core.js') + '\n' + runtime);
let html = read('index.html').replace('/*__STYLE__*/', read('style.css'))
  .replace('/*__GARDEN_ASSETS__*/', json(gardenAssets)).replace('__BOOTSTRAP__', json(manifest))
  .replace('/*__ANSWERS__*/', read('answers.js')).replace('/*__CORE__*/', read('core.js')).replace('/*__APP__*/', runtime)
  .replace('img-src data:', "img-src 'self' data:").replace("connect-src 'none'", "connect-src 'self'");
// Keep the editable template independent of the hosting root and preserve existing favicon edits.
html = html.replace(/<link[^>]+rel=["']icon["'][^>]*>\s*/g, '');
const favicon = path.join(repo, 'Kyoto_Univ/ui/favicon.svg');
if (fs.existsSync(favicon)) {
  fs.copyFileSync(favicon, path.join(output, 'assets/favicon.svg'));
  html = html.replace('</head>', '  <link rel="icon" type="image/svg+xml" href="./assets/favicon.svg">\n</head>');
}
fs.writeFileSync(path.join(output, 'index.html'), html);
fs.writeFileSync(path.join(output, '.nojekyll'), '');
console.log(`${decks.length}教材を output/site/ に出力しました。クイズの公開にはこのフォルダを使います。`);
