/* Browser-only persistence. All changes to a record share one IndexedDB transaction. */
const RecallStore = (() => {
  const rules = typeof RecallCore === 'undefined' ? require('./core.js') : RecallCore;
  const copy = value => JSON.parse(JSON.stringify(value));
  function empty() {
    return { schemaVersion: 1, revision: 0, selectedDeckId: null, state: rules.initial() };
  }
  function validate(record) {
    if (!record || record.schemaVersion !== 1 || !Number.isSafeInteger(record.revision) || record.revision < 0 ||
      (record.selectedDeckId !== null && typeof record.selectedDeckId !== 'string')) throw Error('保存した記録を読み取れません。');
    rules.validateState(record.state);
    return record;
  }
  function recover(current, backup) {
    if (current === undefined && backup === undefined) return { record: empty(), intact: true };
    try { return { record: validate(current), intact: true }; }
    catch (_) {
      try { return { record: validate(backup), intact: false }; }
      catch (_) { throw Error('学習記録とバックアップを読み取れません。初期化せず停止しました。'); }
    }
  }
  return class RecallStore {
    constructor({ indexedDB: database = globalThis.indexedDB, name = 'recall-quiz' } = {}) {
      this.factory = database;
      this.name = name;
      this.notice = '';
      this.connection = null;
    }
    async open() {
      if (!this.factory) throw Error('このブラウザでは記録を保存できません。');
      if (!this.connection) this.connection = new Promise((resolve, reject) => {
        const request = this.factory.open(this.name, 1);
        request.onupgradeneeded = () => request.result.createObjectStore('records');
        request.onsuccess = () => {
          const db = request.result;
          db.onversionchange = () => { db.close(); this.connection = null; };
          resolve(db);
        };
        request.onerror = () => { this.connection = null; reject(request.error); };
        request.onblocked = () => reject(Error('別のタブを閉じてから開き直してください。'));
      });
      return this.connection;
    }
    async read() {
      const db = await this.open();
      return new Promise((resolve, reject) => {
        const tx = db.transaction('records', 'readonly'), records = tx.objectStore('records');
        const current = records.get('current'), backup = records.get('backup');
        tx.oncomplete = () => {
          try {
            const restored = recover(current.result, backup.result);
            this.notice = restored.intact ? '' : '前回のバックアップから記録を復元しました。';
            resolve(copy(restored.record));
          } catch (error) { reject(error); }
        };
        tx.onabort = () => reject(tx.error || Error('学習記録を読み取れません。'));
      });
    }
    async update(mutator, expectedRevision) {
      const db = await this.open();
      return new Promise((resolve, reject) => {
        const tx = db.transaction('records', 'readwrite'), records = tx.objectStore('records');
        const current = records.get('current'), backup = records.get('backup');
        let ready = 0, result, failure;
        function apply() {
          if (++ready !== 2) return;
          try {
            const restored = recover(current.result, backup.result), previous = restored.record;
            if (expectedRevision !== undefined && previous.revision !== expectedRevision) {
              const error = Error('別のタブで記録が変わりました。内容を更新したので、もう一度操作してください。');
              error.name = 'ConflictError';
              throw error;
            }
            const next = mutator(copy(previous));
            result = validate({ schemaVersion: 1, revision: previous.revision + 1,
              selectedDeckId: next.selectedDeckId, state: next.state });
            if (restored.intact && previous.revision > 0 && JSON.stringify(next.state) === JSON.stringify(previous.state) && next.selectedDeckId === previous.selectedDeckId) {
              result = previous;
              return;
            }
            if (current.result !== undefined && restored.intact) records.put(previous, 'backup');
            else if (current.result !== undefined) records.put(current.result, `damaged-${Date.now()}`);
            records.put(result, 'current');
          } catch (error) { failure = error; tx.abort(); }
        }
        current.onsuccess = apply;
        backup.onsuccess = apply;
        tx.oncomplete = () => resolve(copy(result));
        tx.onabort = () => reject(failure || tx.error || Error('記録を保存できませんでした。'));
      });
    }
  };
})();
if (typeof module !== 'undefined') module.exports = RecallStore;
