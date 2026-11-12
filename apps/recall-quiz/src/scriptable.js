// The build adds RecallCore, RecallStore, QUIZ_DECK and QUIZ_HTML above this file.
async function runRecallQuiz() {
  const fm = FileManager.local();
  const root = fm.joinPath(fm.documentsDirectory(), 'RecallQuiz');
  const store = new RecallStore(fm, root);
  const deckPath = fm.joinPath(root, 'deck.json');
  let deck = RecallCore.validateDeck(QUIZ_DECK);
  if (fm.fileExists(deckPath)) {
    const imported = RecallCore.validateDeck(JSON.parse(fm.readString(deckPath)));
    if (imported.id !== deck.id || imported.version >= deck.version) deck = imported;
  }
  let state = store.load();
  const notice = store.notice;
  state = store.save(RecallCore.ensureSession(state, deck, new Date()));
  const notificationId = 'study-recall-quiz-daily';
  async function notifications(settings, test = false) {
    const id = test ? `${notificationId}-test` : notificationId;
    await Notification.removePending(!test && !settings.notificationEnabled ? [id, `${notificationId}-test`] : [id]);
    if (!test && !settings.notificationEnabled) return;
    const n = new Notification();
    n.identifier = id;
    n.title = test ? '通知テスト · ひとつ想起' : '3問だけ、思い出そう';
    n.body = '1問で終わってもOK。今日の分をひとつ思い出そう。';
    n.openURL = URLScheme.forRunningScript();
    if (test) n.setTriggerDate(new Date(Date.now() + 60000));
    else {
      const [hour, minute] = settings.notificationTime.split(':').map(Number);
      n.setDailyTrigger(hour, minute, true);
    }
    await n.schedule();
  }
  async function backup() {
    if (!state.settings.iCloudBackup) return '';
    try {
      const cloud = FileManager.iCloud();
      const folder = cloud.joinPath(cloud.documentsDirectory(), 'RecallQuizBackup');
      cloud.createDirectory(folder, true);
      cloud.writeString(cloud.joinPath(folder, 'state.json'), JSON.stringify(state, null, 2));
      return '';
    } catch (_) {
      return '本体への保存は完了しました。iCloudバックアップはできませんでした。';
    }
  }
  async function readPicked() {
    const paths = await DocumentPicker.open(['public.json']);
    if (!paths.length) throw Error('ファイル選択を取り消しました。');
    const path = paths[0];
    const cloud = FileManager.iCloud();
    if (cloud.isFileStoredIniCloud(path)) await cloud.downloadFileFromiCloud(path);
    return JSON.parse(fm.readString(path));
  }
  async function confirm(title, message) {
    const alert = new Alert();
    alert.title = title;
    alert.message = message;
    alert.addAction('取り込む');
    alert.addCancelAction('キャンセル');
    return (await alert.presentAlert()) === 0;
  }
  async function handle(action, payload) {
    let message = '';
    if (action === 'testNotification') {
      await notifications(state.settings, true);
      message = '1分後にテスト通知を予約しました。一度アプリを閉じて確認できます。';
    } else if (action === 'export') {
      await DocumentPicker.exportString(JSON.stringify(state, null, 2), 'recall-quiz-state.json');
      message = '学習記録を書き出しました。';
    } else if (action === 'importState') {
      const imported = RecallCore.reconcile(RecallCore.validateState(await readPicked()), deck);
      if (!await confirm('学習記録を復元', `今の記録を、選んだ${imported.reviews.length}件の履歴に置き換えます。今の記録は前回バックアップに残ります。`)) return '';
      // Notification settings belong to this device; restoring history does not enable notifications.
      imported.settings = { ...state.settings };
      state = store.save(RecallCore.ensureSession(imported, deck, new Date()));
      message = await backup() || '学習記録を復元しました。';
    } else if (action === 'importDeck') {
      const imported = RecallCore.validateDeck(await readPicked());
      if (imported.renderVersion !== 1 || imported.questions.some(q => !q.promptHtml || !q.answerHtml)) {
        throw Error('ビルドで作った compiled.json の教材を選んでください。');
      }
      if (imported.id === deck.id) {
        if (imported.version < deck.version) throw Error('古い版の教材です。');
        for (const q of imported.questions) {
          const old = deck.questions.find(x => x.id === q.id);
          if (old && (q.version < old.version || (q.version === old.version &&
            ['prompt', 'answer', 'criterion', 'explanation'].some(k => q[k] !== old[k])))) {
            throw Error('内容を変更した問題の版を上げてください。');
          }
        }
      }
      if (!await confirm('教材を読み込む', `${imported.title}、${imported.questions.length}問。これまでの回答履歴と庭は残ります。`)) return '';
      fm.writeString(deckPath, JSON.stringify(imported));
      deck = imported;
      state = store.save(RecallCore.start(state, deck, new Date()));
      message = '教材を読み込みました。';
    } else {
      const next = RecallCore.dispatch(state, deck, action, payload);
      if (action === 'settings') {
        await notifications(next.settings);
        try { state = store.save(next); }
        catch (error) { await notifications(state.settings); throw error; }
        message = await backup() || '設定を保存しました。';
      } else {
        state = store.save(next);
        message = await backup();
      }
    }
    return message;
  }
  const view = new WebView();
  const encode = value => JSON.stringify(value).replace(/</g, '\\u003c');
  const boot = { native: true, deck, state, shop: RecallCore.shop, notice };
  await view.loadHTML(QUIZ_HTML.replace('__BOOTSTRAP__', encode(boot)));
  let closed = false;
  const dismissed = view.present(true).then(() => { closed = true; return { closed: true }; });
  while (!closed) {
    const waiting = view.evaluateJavaScript('window.takeNativeCommand(completion)', true)
      .then(command => ({ command }), error => ({ error }));
    const event = await Promise.race([waiting, dismissed]);
    if (event.closed || closed) break;
    if (event.error) throw event.error;
    const command = event.command;
    let response;
    try {
      if (!command || typeof command.id !== 'string' || typeof command.action !== 'string') throw Error('操作を読み取れません。');
      const message = await handle(command.action, command.payload || {});
      response = { ok: true, state, message };
      if (command.action === 'importDeck') response.deck = deck;
    } catch (error) {
      response = { ok: false, error: String(error.message || error) };
    }
    if (closed) break;
    await view.evaluateJavaScript(`window.resolveNativeCommand(${encode(command.id)}, ${encode(response)})`);
  }
}
try { await runRecallQuiz(); }
catch (error) {
  const alert = new Alert();
  alert.title = 'クイズを開けませんでした';
  alert.message = `${String(error.message || error)}\n記録を消す操作は行っていません。`;
  alert.addAction('閉じる');
  await alert.presentAlert();
}
Script.complete();
