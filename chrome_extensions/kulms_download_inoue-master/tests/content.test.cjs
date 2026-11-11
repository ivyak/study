const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');

const source = readFileSync(join(__dirname, '../content.js'), 'utf8');
const sites = [
  { id: 'first', title: '[2026前期月１] 前期の数学' },
  { id: 'second', title: '[2026後期月１] 後期の数学' },
  { id: 'hidden', title: '[2026後期金６] 非表示の科目' },
  { id: 'overlap', title: '[2026後期月１] 同時限の科目' },
  { id: 'annual', title: '[2026通年月１] 通年の科目' },
  { id: 'both', title: '[2026前期・後期火２] 両方の期の科目' },
  { id: '~home', title: '[2026後期月１] マイページ' }
];

async function setup({ term = 'first', failTitles = false, current = '~home', siteList = sites, zipError = false, missingZip = false, clipboardError = false } = {}) {
  const elements = [];
  const requests = [];
  const downloads = [];
  const storage = new Map(term ? [['kulmsSelectedTermV1', term]] : []);
  const timers = new Map();
  let nextTimerId = 0;
  const errors = [];
  const copied = [];
  class Element {
    constructor(tag) {
      this.tag = tag;
      this.style = {};
      this.children = [];
      this.listeners = {};
      this.textContent = '';
      elements.push(this);
    }
    set innerHTML(value) {
      this.html = value;
      this.children = [];
    }
    get innerHTML() { return this.html || ''; }
    appendChild(child) { this.children.push(child); return child; }
    addEventListener(type, fn) { this.listeners[type] = fn; }
    setAttribute(name, value) { this[name] = value; }
    getAttribute(name) { return this[name]; }
    contains(child) { return this === child || this.children.some(el => el.contains(child)); }
    querySelector() { return null; }
    querySelectorAll() { return []; }
    closest() { return null; }
    focus() { this.focused = true; }
    select() { this.selected = true; }
    click() { downloads.push(this.download); }
    fire(type) { return this.listeners[type]?.({ stopPropagation() {} }); }
  }
  const nav = new Element('a');
  nav.href = 'https://lms.gakusei.kyoto-u.ac.jp/portal/site/first';
  nav.title = '[2026前期月１] 省略名…';
  class Zip {
    constructor() { this.files = {}; }
    folder(name) {
      return { file: (path, content) => { this.files[`${name}/${path}`] = { content }; } };
    }
    async generateAsync() {
      if (zipError) throw new Error('ZIP generation failed');
      return {};
    }
  }
  vm.runInNewContext(source, {
    document: {
      getElementById: () => null,
      createElement: tag => new Element(tag),
      addEventListener() {},
      querySelectorAll: () => [nav],
      body: new Element('body')
    },
    window: {
      location: { href: `https://lms.gakusei.kyoto-u.ac.jp/portal/site/${current}` },
      getComputedStyle: () => ({ backgroundColor: 'rgb(255, 255, 255)' })
    },
    localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value)
    },
    JSZip: missingZip ? undefined : Zip,
    navigator: { clipboard: { writeText: async text => {
      if (clipboardError) throw new Error('Clipboard denied');
      copied.push(text);
    } } },
    URL: { createObjectURL: () => 'blob:test', revokeObjectURL() {} },
    setInterval() {},
    setTimeout: fn => { const id = nextTimerId++; timers.set(id, fn); return id; },
    clearTimeout: id => timers.delete(id),
    console: { warn() {}, error: error => errors.push(error) },
    fetch: async url => {
      requests.push(url);
      if (url.includes('/direct/site.json')) {
        return { ok: !failTitles, status: failTitles ? 503 : 200, statusText: failTitles ? 'Service Unavailable' : 'OK', json: async () => ({ site_collection: siteList }) };
      }
      const resource = url.match(/\/direct\/content\/site\/([^/.]+)\.json/);
      if (resource) {
        return { ok: true, json: async () => ({ content_collection: [{
          title: '資料.pdf', type: 'file', createdDate: '2026-11-11',
          url: `https://lms.gakusei.kyoto-u.ac.jp/access/content/group/${resource[1]}/資料.pdf`
        }] }) };
      }
      if (url.includes('/direct/')) return { ok: true, json: async () => ({}) };
      return { ok: true, blob: async () => ({}) };
    }
  });
  await new Promise(resolve => setImmediate(resolve));
  const select = elements.find(el => el.tag === 'select');
  const ttButton = elements.find(el => el.tag === 'button' && el.innerHTML.includes('時間割'));
  const menuItem = text => elements.find(el => el.innerHTML.includes(text));
  const tableNames = () => elements.filter(el => el.tag === 'a' && el.innerText).map(el => el.innerText);
  const processed = () => requests.filter(url => url.includes('/direct/content/site/')).map(url => url.match(/site\/([^/.]+)/)[1]);
  const switchTerm = value => { select.value = value; select.fire('change'); };
  const resetDownload = () => { for (const fn of timers.values()) fn(); timers.clear(); requests.length = 0; };
  return { select, ttButton, menuItem, tableNames, processed, switchTerm, resetDownload, downloads, storage, elements, errors, copied };
}

test('一括DLは選択した期だけを処理し、履歴とフルDLを維持する', async () => {
  const app = await setup();
  await app.menuItem('選択した期の全教科を一括DL').fire('click');
  assert.deepEqual(app.processed(), ['first']);
  assert.deepEqual(app.downloads, ['前期_全教科一括DL.zip']);
  app.resetDownload();
  app.switchTerm('second');
  await app.menuItem('選択した期の全教科を一括DL').fire('click');
  assert.deepEqual(app.processed(), ['second', 'hidden', 'overlap']);
  assert.equal(app.downloads.at(-1), '後期_全教科一括DL.zip');
  app.resetDownload();
  await app.menuItem('選択した期の全教科を一括DL').fire('click');
  assert.equal(app.downloads.length, 2);
  app.resetDownload();
  await app.menuItem('選択した期の全教科を再度フルDL').fire('click');
  assert.equal(app.downloads.length, 3);
  app.resetDownload();
  app.switchTerm('unspecified');
  await app.menuItem('選択した期の全教科を一括DL').fire('click');
  assert.deepEqual(app.processed(), ['annual', 'both']);
  assert.equal(app.downloads.at(-1), '期指定なし_全教科一括DL.zip');
  assert.equal(app.errors.length, 0);
});

test('時間割は前後期を分離し、非表示科目・全角時限・同時限の別科目も表示する', async () => {
  const app = await setup({ term: 'second' });
  app.ttButton.fire('click');
  assert.deepEqual(app.tableNames(), ['後期の数学', '同時限の科目', '非表示の科目']);
  // 過去のDOMを除き、切り替え後に作成されたリンクを確認する。
  const count = app.tableNames().length;
  app.switchTerm('first');
  assert.deepEqual(app.tableNames().slice(count), ['前期の数学']);
  assert.equal(app.storage.get('kulmsSelectedTermV1'), 'first');
  const nextCount = app.tableNames().length;
  app.switchTerm('unspecified');
  assert.deepEqual(app.tableNames().slice(nextCount), ['通年の科目', '両方の期の科目']);
});

test('個別DLは選択期に関係なく、開いている科目を対象にする', async () => {
  const app = await setup({ term: 'second', current: 'first' });
  await app.menuItem('選択中の教科のみDL').fire('click');
  assert.deepEqual(app.processed(), ['first']);
  assert.equal(app.downloads[0], '[2026前期月１] 前期の数学.zip');
});

test('DL中に期を変えても、開始時の対象期とZIP名を維持する', async () => {
  const app = await setup();
  const pending = app.menuItem('選択した期の全教科を一括DL').fire('click');
  app.switchTerm('second');
  await pending;
  assert.deepEqual(app.processed(), ['first']);
  assert.equal(app.downloads[0], '前期_全教科一括DL.zip');
});

test('API取得失敗時も画面上の名前で時間割を分類し、失敗を表示する', async () => {
  const app = await setup({ failTitles: true });
  app.ttButton.fire('click');
  assert.deepEqual(app.tableNames(), ['省略名']);
  assert.ok(app.elements.some(el => el.innerText?.includes('画面上の科目のみ表示')));
  assert.equal(app.errors.length, 1);
});


test('教科一覧のHTTPエラーを握りつぶさず表示し、時間が経っても詳細を確認・コピーできる', async () => {
  const app = await setup({ failTitles: true });
  await app.menuItem('選択した期の全教科を再度フルDL').fire('click');
  const panel = app.elements.find(el => el.id === 'kulms-download-error');
  const details = app.elements.find(el => el.tag === 'textarea');
  assert.equal(panel.style.display, 'block');
  assert.match(details.value, /HTTP 503 Service Unavailable/);
  assert.match(details.value, /処理：教科一覧の取得/);
  assert.match(details.value, /方法：再度フルDL/);
  assert.doesNotMatch(details.value, /教科が見つかりません/);
  app.resetDownload();
  assert.equal(panel.style.display, 'block');
  await app.elements.find(el => el.textContent === 'エラーをコピー').fire('click');
  assert.equal(app.copied[0], details.value);
  app.elements.find(el => el.textContent === '閉じる').fire('click');
  assert.equal(panel.style.display, 'none');
  app.menuItem('前回のエラーを表示').fire('click');
  assert.equal(panel.style.display, 'block');
  assert.equal(app.downloads.length, 0);
  assert.equal(app.storage.has('kulmsDownloadedSourcesV1'), false);
});

test('対象科目なしとZIPライブラリの未読込も、詳細を残して再試行できる', async () => {
  for (const options of [{ siteList: [] }, { missingZip: true }]) {
    const app = await setup(options);
    await app.menuItem('選択した期の全教科を再度フルDL').fire('click');
    const details = app.elements.find(el => el.tag === 'textarea');
    assert.match(details.value, options.missingZip ? /ZIPライブラリ/ : /前期の教科が見つかりません/);
    const main = app.elements.find(el => el.tag === 'button' && el.innerHTML.includes('DL失敗'));
    assert.equal(main.style.pointerEvents, 'auto');
    await app.menuItem('選択した期の全教科を再度フルDL').fire('click');
    assert.equal(app.errors.length, 2);
  }
});

test('ZIP作成に失敗した場合は取得済み履歴を更新しない', async () => {
  const app = await setup({ zipError: true });
  await app.menuItem('選択した期の全教科を再度フルDL').fire('click');
  const details = app.elements.find(el => el.tag === 'textarea');
  assert.match(details.value, /処理：ZIPの作成/);
  assert.match(details.value, /ZIP generation failed/);
  assert.equal(app.downloads.length, 0);
  assert.equal(app.storage.has('kulmsDownloadedSourcesV1'), false);
});

test('コピーが拒否された場合もエラー詳細を選択して手動コピーできる', async () => {
  const app = await setup({ siteList: [], clipboardError: true });
  await app.menuItem('選択した期の全教科を再度フルDL').fire('click');
  await app.elements.find(el => el.textContent === 'エラーをコピー').fire('click');
  const details = app.elements.find(el => el.tag === 'textarea');
  assert.equal(details.focused, true);
  assert.equal(details.selected, true);
});
