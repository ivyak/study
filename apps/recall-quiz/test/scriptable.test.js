const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
test('Scriptable host bridges commands, persists, exports and configures only its own notifications', async () => {
  const root = path.resolve(__dirname, '..');
  const files = new Map(), scheduled = new Map([['other-app', {}]]), responses = [];
  let boot, close, exported, complete = false, index = 0, firstEvent;
  const fm = {
    createDirectory() {}, documentsDirectory: () => 'documents',
    joinPath: (a, b) => a + '/' + b, fileExists: p => files.has(p),
    readString: p => files.get(p), writeString: (p, s) => files.set(p, s), remove: p => files.delete(p),
    move(a, b) { files.set(b, files.get(a)); files.delete(a); }, isFileStoredIniCloud: () => false
  };
  const seed = require('../src/core.js').initial();
  seed.garden.coins = 10;
  files.set('documents/RecallQuiz/state.json', JSON.stringify(seed));
  const commands = [
    () => ({ action: 'reveal' }),
    () => {
      firstEvent = `${boot.state.session.id}:${boot.state.session.index}`;
      return { action: 'rate', payload: { eventId: firstEvent, result: 'again' } };
    },
    () => ({ action: 'rate', payload: { eventId: firstEvent, result: 'again' } }),
    () => ({ action: 'settings', payload: { notificationEnabled: true, notificationTime: '12:15' } }),
    () => ({ action: 'testNotification' }),
    () => ({ action: 'export' }),
    () => {
      files.set('picked.json', exported);
      return { action: 'importState' };
    },
    () => ({ action: 'settings', payload: { notificationEnabled: false, notificationTime: '12:15' } }),
    () => {
      const imported = JSON.parse(fs.readFileSync(path.join(root, 'decks/calc2-lesson01.json'), 'utf8'));
      imported.id = 'physics-lesson01';
      imported.title = '物理学';
      imported.renderVersion = 1;
      imported.questions = imported.questions.map(q => ({ ...q, id: 'physics-' + q.id, promptHtml: q.prompt, answerHtml: q.answer }));
      files.set('picked.json', JSON.stringify(imported));
      return { action: 'importDeck' };
    },
    () => ({ action: 'selectDeck', payload: { id: 'calc2-lesson01' } }),
    () => ({ action: 'draw', payload: { eventId: 'native-draw' } }),
    () => ({ action: 'draw', payload: { eventId: 'native-draw' } })
  ];
  class MockNotification {
    static async removePending(ids) { ids.forEach(id => scheduled.delete(id)); }
    setDailyTrigger(hour, minute, repeats) { this.daily = [hour, minute, repeats]; }
    setTriggerDate(date) { this.date = date; }
    async schedule() { scheduled.set(this.identifier, this); }
  }
  class MockView {
    async loadHTML(html) { boot = JSON.parse(html.split('window.BOOT = ')[1].split(';</script>')[0]); }
    present() { return new Promise(resolve => { close = resolve; }); }
    async evaluateJavaScript(code, callback) {
      if (callback) {
        if (index === commands.length) { close(); return new Promise(() => {}); }
        return { id: String(index), ...commands[index++]() };
      }
      vm.runInNewContext(code, { window: { resolveNativeCommand(id, result) {
        responses.push(result);
        if (result.ok) boot = { ...boot, state: result.state, deck: result.deck };
      } } });
    }
  }
  class MockAlert {
    addAction() {} addCancelAction() {}
    async presentAlert() { return 0; }
  }
  const sandbox = {
    FileManager: { local: () => fm, iCloud: () => fm }, Notification: MockNotification,
    WebView: MockView, URLScheme: { forRunningScript: () => 'scriptable:///run/Quiz' },
    DocumentPicker: {
      async exportString(text) { exported = text; return ['exported.json']; },
      async open() { return ['picked.json']; }
    },
    Alert: MockAlert, Script: { complete() { complete = true; } }
  };
  const code = ['core.js', 'storage.js'].map(f => fs.readFileSync(path.join(root, 'src', f), 'utf8')).join('\n') +
    '\nconst QUIZ_DECK = ' + fs.readFileSync(path.join(root, 'decks/calc2-lesson01.json'), 'utf8') +
    ';\nconst QUIZ_HTML = "<script>window.BOOT = __BOOTSTRAP__;</script>";\n' +
    fs.readFileSync(path.join(root, 'src/scriptable.js'), 'utf8');
  await vm.runInNewContext(`(async () => { ${code} })()`, sandbox);
  assert.equal(complete, true);
  assert.equal(responses.length, commands.length);
  assert.ok(responses.every(r => r.ok), responses.map(r => r.error).join(','));
  const saved = JSON.parse(files.get('documents/RecallQuiz/state.json'));
  assert.equal(saved.reviews.length, 1);
  assert.equal(saved.garden.coins, 0);
  assert.equal(saved.garden.draws.length, 1);
  assert.equal(saved.garden.items.length, 1);
  assert.equal(saved.settings.notificationEnabled, false);
  assert.equal(scheduled.has('other-app'), true);
  assert.equal(scheduled.has('study-recall-quiz-daily'), false);
  assert.equal(scheduled.has('study-recall-quiz-daily-test'), false);
  assert.equal(JSON.parse(exported).reviews.length, 1);
  assert.equal(JSON.parse(files.get('documents/RecallQuiz/decks.json')).length, 2);
  assert.equal(JSON.parse(files.get('documents/RecallQuiz/deck.json')).id, 'calc2-lesson01');
  assert.equal(saved.session.deckId, 'calc2-lesson01');
  assert.equal(responses.find(r => r.decks)?.decks.length, 2);
  const presentationCount = saved.presentations.length;
  commands.length = 0;
  index = 0;
  await vm.runInNewContext(`(async () => { ${code} })()`, sandbox);
  assert.equal(boot.decks.length, 2);
  assert.equal(boot.deck.id, 'calc2-lesson01');
  assert.equal(boot.state.presentations.length, presentationCount);
});
