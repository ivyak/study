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
    async studyDeck(scope) {
      if (!scope || !['all', 'subject', 'lesson'].includes(scope.type)) throw Error('出題範囲を選んでください。');
      const entries = this.catalog.filter(item => scope.type === 'all' ||
        (scope.type === 'subject' ? item.title === scope.title : item.id === scope.id));
      if (!entries.length) throw Error('この範囲の教材が見つかりません。');
      const decks = await Promise.all(entries.map(item => this.loadDeck(item.id)));
      return {
        id: scope.type === 'lesson' ? scope.id : `study-${scope.type}`,
        title: scope.type === 'all' ? '全教科' : decks[0].title,
        studyScope: scope,
        questions: decks.flatMap(deck => deck.questions.map(q => ({ ...q, deckId: deck.id }))),
        sourceImages: Object.assign({}, ...decks.map(deck => deck.sourceImages || {}))
      };
    }
    async sessionDeck(state, selectedDeckId) {
      const session = state.session;
      if (session?.scope) return this.studyDeck(session.scope);
      if (session) {
        const id = this.catalog.some(item => item.id === session.deckId) ? session.deckId : selectedDeckId;
        if (this.catalog.some(item => item.id === id)) return this.loadDeck(id);
      }
      return { id: 'study-all', title: '全教科', questions: [], sourceImages: {}, studyScope: { type: 'all' } };
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
      this.deck = await this.sessionDeck(record.state, record.selectedDeckId);
      this.record = await this.store.update(previous => ({ selectedDeckId: previous.selectedDeckId,
        state: rules.reconcile(previous.state, this.deck)
      }), record.revision);
      return this.boot();
    }
    boot() {
      return { state: this.record.state, deck: this.deck, decks: this.decks(), shop: rules.shop, notice: this.store.notice };
    }
    async refresh() {
      this.record = await this.store.read();
      this.deck = await this.sessionDeck(this.record.state, this.record.selectedDeckId);
      return this.boot();
    }
    async dispatch(action, payload = {}) {
      const scope = action === 'selectDeck' ? { type: 'lesson', id: payload.id } : action === 'start' ?
        this.record.state.session?.scope || this.deck.studyScope || { type: 'lesson', id: this.deck.id } : payload.scope;
      const starting = ['selectDeck', 'startStudy', 'start'].includes(action);
      const selected = starting ? await this.studyDeck(scope) : this.deck;
      this.record = await this.store.update(previous => ({
        selectedDeckId: starting && scope.type === 'lesson' ? scope.id : previous.selectedDeckId,
        state: rules.dispatch(previous.state, selected, starting ? 'start' : action, payload)
      }), this.record.revision);
      this.deck = selected;
      return this.boot();
    }
    async restore(data) {
      const state = rules.validateState(data.state || data);
      const selectedDeckId = this.catalog.some(item => item.id === data.selectedDeckId) ? data.selectedDeckId : this.record.selectedDeckId;
      const selected = await this.sessionDeck(state, selectedDeckId);
      // Scriptable-only notification and cloud settings have no browser-side effect.
      state.settings = { batchSize: 3 };
      this.record = await this.store.update(() => ({ selectedDeckId,
        state: rules.reconcile(state, selected)
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
