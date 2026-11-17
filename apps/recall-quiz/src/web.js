/* Static-host runtime. Only public teaching material is fetched; records stay in IndexedDB. */
const RecallWeb = (() => {
  const rules = typeof RecallCore === 'undefined' ? require('./core.js') : RecallCore;
  const Store = typeof RecallStore === 'undefined' ? require('./storage.js') : RecallStore;
  class Runtime {
    constructor({ decks, defaultDeckId, baseURL, store, fetch: fetcher = globalThis.fetch }) {
      if (!Array.isArray(decks) || !decks.length) throw Error('教材一覧がありません。');
      this.catalog = decks;
      this.defaultDeckId = defaultDeckId || decks[0].id;
      this.baseURL = baseURL;
      this.store = store;
      this.fetch = fetcher;
      this.loaded = new Map();
      this.requests = new Map();
      this.record = null;
      this.deck = null;
    }
    async loadDeck(id) {
      if (this.loaded.has(id)) return this.loaded.get(id);
      const entry = this.catalog.find(item => item.id === id);
      if (!entry) throw Error('教材が見つかりません。');
      if (!this.requests.has(id)) this.requests.set(id, (async () => {
        const response = await this.fetch(new URL(entry.file, this.baseURL), { cache: 'no-cache' });
        if (!response.ok) throw Error('教材を読み込めませんでした。接続を確認して、もう一度開いてください。');
        const deck = rules.validateDeck(await response.json());
        if (deck.id !== id) throw Error('教材のIDが一致しません。');
        this.loaded.set(id, deck);
        return deck;
      })().catch(error => { this.requests.delete(id); throw error; }));
      return this.requests.get(id);
    }
    decks() { return this.catalog.map(item => this.loaded.get(item.id) || item); }
    async subject(title) {
      await Promise.all(this.catalog.filter(item => item.title === title).map(item => this.loadDeck(item.id)));
      return this.decks();
    }
    async start(legacyStorage) {
      let record = await this.store.read();
      if (record.revision === 0 && legacyStorage) {
        const old = legacyStorage.getItem('recall-quiz-preview-v1');
        if (old) {
          const state = rules.validateState(JSON.parse(old));
          const selected = legacyStorage.getItem('recall-quiz-preview-deck');
          record = await this.store.update(() => ({ state,
            selectedDeckId: this.catalog.some(item => item.id === selected) ? selected : this.defaultDeckId
          }), record.revision);
        }
      }
      this.deck = await this.loadDeck(this.catalog.some(item => item.id === record.selectedDeckId) ? record.selectedDeckId : this.defaultDeckId);
      this.record = await this.store.update(previous => ({ selectedDeckId: this.deck.id,
        state: rules.ensureSession(previous.state, this.deck, new Date())
      }), record.revision);
      return this.boot();
    }
    boot() {
      return { state: this.record.state, deck: this.deck, decks: this.decks(), shop: rules.shop, notice: this.store.notice };
    }
    async refresh() {
      this.record = await this.store.read();
      this.deck = await this.loadDeck(this.catalog.some(item => item.id === this.record.selectedDeckId) ? this.record.selectedDeckId : this.defaultDeckId);
      return this.boot();
    }
    async dispatch(action, payload = {}) {
      const selected = action === 'selectDeck' ? await this.loadDeck(payload.id) : this.deck;
      this.record = await this.store.update(previous => ({ selectedDeckId: selected.id,
        state: action === 'selectDeck' ? (selected.id === previous.selectedDeckId ? previous.state : rules.start(previous.state, selected, new Date())) :
          rules.dispatch(previous.state, selected, action, payload)
      }), this.record.revision);
      this.deck = selected;
      return this.boot();
    }
    async restore(data) {
      const state = rules.validateState(data.state || data);
      const selected = this.catalog.some(item => item.id === data.selectedDeckId) ? await this.loadDeck(data.selectedDeckId) : this.deck;
      // Scriptable-only notification and cloud settings have no browser-side effect.
      state.settings = { batchSize: 3 };
      this.record = await this.store.update(() => ({ selectedDeckId: selected.id,
        state: rules.ensureSession(state, selected, new Date())
      }), this.record.revision);
      this.deck = selected;
      return this.boot();
    }
    async snapshot() { return this.store.read(); }
    async export() {
      const record = await this.snapshot();
      return { format: 'recall-quiz-browser', version: 1, exportedAt: new Date().toISOString(),
        selectedDeckId: record.selectedDeckId, state: record.state };
    }
  }
  async function start(manifest) {
    const baseURL = new URL('./', document.baseURI).href;
    const store = new Store({ name: `recall-quiz:${new URL(baseURL).pathname}` });
    const runtime = new Runtime({ ...manifest, baseURL, store, fetch: (...args) => fetch(...args) });
    window.RecallRuntime = runtime;
    return runtime.start(window.localStorage);
  }
  function failure(error) {
    const content = document.querySelector('#content');
    content.replaceChildren();
    const heading = document.createElement('h1');
    heading.className = 'page-title';
    heading.textContent = 'クイズを開けませんでした';
    const message = document.createElement('p');
    message.textContent = error.message || String(error);
    const retry = document.createElement('button');
    retry.className = 'primary'; retry.textContent = '読み込み直す';
    retry.onclick = () => location.reload();
    content.append(heading, message, retry);
  }
  return { Runtime, start, failure };
})();
if (typeof module !== 'undefined') module.exports = RecallWeb;
