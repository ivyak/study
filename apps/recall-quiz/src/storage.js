const RecallStore = (() => {
  const rules = typeof RecallCore === 'undefined' ? require('./core.js') : RecallCore;
  return class RecallStore {
    constructor(fm, root) {
      this.fm = fm;
      this.root = root;
      fm.createDirectory(root, true);
      this.path = fm.joinPath(root, 'state.json');
      this.backup = fm.joinPath(root, 'state.backup.json');
      this.pending = fm.joinPath(root, 'state.pending.json');
      this.lastText = fm.fileExists(this.path) ? fm.readString(this.path) : null;
      this.notice = '';
    }
    load() {
      const existing = [this.path, this.pending, this.backup].filter(p => this.fm.fileExists(p));
      if (!existing.length) return rules.initial();
      for (const path of existing) {
        try {
          const state = rules.validateState(JSON.parse(this.fm.readString(path)));
          if (path !== this.path) this.notice = '保存途中または前回のバックアップから復元しました。';
          return state;
        } catch (_) { /* Try the next intact copy without deleting the damaged file. */ }
      }
      throw Error('学習記録とバックアップを読み取れません。初期化せず停止しました。');
    }
    save(state) {
      rules.validateState(state);
      const actual = this.fm.fileExists(this.path) ? this.fm.readString(this.path) : null;
      if (actual !== this.lastText) throw Error('別の画面で記録が変わりました。一度閉じて開き直してください。');
      const text = JSON.stringify(state, null, 2);
      this.fm.writeString(this.pending, text);
      rules.validateState(JSON.parse(this.fm.readString(this.pending)));
      if (actual !== null) {
        let intact = false;
        try { rules.validateState(JSON.parse(actual)); intact = true; } catch (_) { /* Preserve for recovery. */ }
        if (intact) this.fm.writeString(this.backup, actual);
        else this.fm.writeString(this.fm.joinPath(this.root, `state.damaged-${Date.now()}.json`), actual);
        this.fm.remove(this.path);
      }
      this.fm.move(this.pending, this.path);
      this.lastText = text;
      return state;
    }
  };
})();
if (typeof module !== 'undefined') module.exports = RecallStore;
