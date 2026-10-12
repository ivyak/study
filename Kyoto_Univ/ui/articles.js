/* Article explanations are created in Codex chat and read here as illustrated articles. */
window.LifeArticles = (() => {
  let records = JSON.parse(document.getElementById('article-data').textContent);
  const labels = {unread: '未読', reading: '勉強中', read: '完了'};
  const storageKey = 'life.article.read-status';
  const bookmarkKey = 'life.article.bookmarks';
  let bookmarks = {};
  try { bookmarks = JSON.parse(localStorage.getItem(bookmarkKey) || '{}') || {}; } catch {}
  let local = {};
  try { local = JSON.parse(localStorage.getItem(storageKey) || '{}') || {}; } catch {}
  let currentId = null, slideIndex = 0, base = null, connecting = null;
  const element = (tag, value, className) => {
    const node = document.createElement(tag); node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  function slideArrow(direction, label) {
    const button = element('button', '', `article-slide-arrow article-slide-${direction}`);
    button.type = 'button'; button.setAttribute('aria-label', label); button.title = label;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', direction === 'prev' ? 'm14 6-6 6 6 6' : 'm10 6 6 6-6 6');
    svg.append(path); button.append(svg); return button;
  }
  function markAppearance(button, selected, title) {
    button.setAttribute('aria-pressed', String(selected));
    const label = `${title}：${selected ? 'しおりを外す' : 'しおりを付ける'}`;
    button.setAttribute('aria-label', label); button.title = label;
  }
  const date = value => new Date(value).toLocaleString('ja-JP', {timeZone: 'Asia/Tokyo', hour12: false});
  async function connect() {
    if (base) return;
    if (!connecting) connecting = (async () => {
      for (const candidate of [...new Set([...(['http:', 'https:'].includes(location.protocol) ? [location.origin] : []), 'http://127.0.0.1:8765'])]) {
        try {
          const response = await fetch(candidate + '/api/runtime', {signal: AbortSignal.timeout(3000)});
          const data = await response.json();
          if (data.token) { base = candidate; return; }
        } catch {}
      }
      throw new Error('ローカルサーバーに接続できません');
    })();
    try { await connecting; } finally { connecting = null; }
  }
  async function request(path, options = {}) {
    await connect();
    const response = await fetch(base + path, {...options, signal: AbortSignal.timeout(10000)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '接続を確認してください');
    return data;
  }
  function completionStatus(report) {
    const cached = local[report.id];
    return cached && (cached.pending || Date.parse(cached.updatedAt) > (Date.parse(report.readStatusUpdatedAt) || 0)) ? cached.status : report.readStatus || 'unread';
  }
  function readingStatus(report) { return Number.isInteger(bookmarkIndex(report)) ? 'reading' : completionStatus(report) === 'read' ? 'read' : 'unread'; }
  function store() { try { localStorage.setItem(storageKey, JSON.stringify(local)); return true; } catch { return false; } }
  function bookmarkIndex(report) {
    const cached = bookmarks[report.id];
    if (typeof cached === 'number') return cached;
    if (cached && (cached.pending || Date.parse(cached.updatedAt) > (Date.parse(report.bookmarkUpdatedAt) || 0))) return cached.index;
    return report.bookmarkIndex;
  }
  async function persistBookmark(id) {
    const cached = bookmarks[id];
    const runtime = await request('/api/runtime');
    const result = await request(`/api/articles/${id}/bookmark`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-LIFE-Token': runtime.token}, body: JSON.stringify({slideIndex: cached.index})});
    if (bookmarks[id] !== cached) return;
    bookmarks[id] = {index: result.bookmarkIndex, updatedAt: result.bookmarkUpdatedAt, pending: false};
    try { localStorage.setItem(bookmarkKey, JSON.stringify(bookmarks)); } catch {}
    const report = records.find(item => item.id === id);
    if (report) { report.bookmarkIndex = result.bookmarkIndex; report.bookmarkUpdatedAt = result.bookmarkUpdatedAt; }
  }

  async function persist(id) {
    const cached = local[id];
    const runtime = await request('/api/runtime');
    const result = await request(`/api/articles/${id}/read-status`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-LIFE-Token': runtime.token}, body: JSON.stringify({readStatus: cached.status})});
    if (local[id] !== cached) return;
    local[id] = {status: result.readStatus, updatedAt: result.readStatusUpdatedAt, pending: false}; store();
    const report = records.find(item => item.id === id);
    if (report) { report.readStatus = result.readStatus; report.readStatusUpdatedAt = result.readStatusUpdatedAt; report.bookmarkIndex = result.bookmarkIndex; report.bookmarkUpdatedAt = result.bookmarkUpdatedAt; }
  }
  function controls(report) {
    const wrapper = element('div', '', 'article-reading-controls');
    const label = element('span', '', 'article-reading-label'); wrapper.append(label);
    report.updateReadingStatus = () => { label.textContent = `読書ステータス：${labels[readingStatus(report)]}`; };
    report.updateReadingStatus();
    return wrapper;
  }
  function completeButton(report, content) {
    const wrapper = element('div', '', 'article-complete-controls');
    const button = element('button', '確認完了', 'reading-complete-button'); button.type = 'button';
    button.addEventListener('click', async () => {
      const now = new Date().toISOString();
      local[report.id] = {status: 'read', updatedAt: now, pending: true};
      bookmarks[report.id] = {index: null, updatedAt: now, pending: false};
      const stored = store();
      try { localStorage.setItem(bookmarkKey, JSON.stringify(bookmarks)); } catch {}
      report.updateBookmarks?.();
      report.updateReadingStatus();
      try { await persist(report.id); document.getElementById('article-detail-reading-status').textContent = '完了を保存しました。'; }
      catch { document.getElementById('article-detail-reading-status').textContent = stored ? 'このブラウザーに保存しました。サーバー接続時に同期します。' : '保存できませんでした。'; }
    });
    wrapper.append(button); content.append(wrapper);
  }
  function list() {
    const target = document.getElementById('article-list'); target.replaceChildren();
    for (const report of records) {
      const row = element('div', '', 'lesson article-row');
      const title = element('a', report.title, 'lesson-overview');
      title.href = '#' + new URLSearchParams({section: '記事解説', article: report.id});
      const heading = element('div', '', 'article-row-heading');
      const badge = element('span', labels[readingStatus(report)], `article-status-badge article-status-${readingStatus(report)}`);
      heading.append(title, badge);
      row.append(heading, element('span', report.publishedAt, 'article-date'), element('span', date(report.generatedAt), 'article-date'));
      target.append(row);
    }
    if (!records.length) target.append(element('p', '解説はまだありません。Codexのチャットで $article-explainer に記事を渡すと、ここに表示されます。'));
  }
  function legacySlides(html) {
    const template = document.createElement('template'); template.innerHTML = html;
    let section = '要点'; const slides = [];
    for (const node of [...template.content.children]) {
      if (node.tagName === 'H2' || node.tagName === 'H3') { section = node.textContent; continue; }
      if (!node.textContent.trim()) continue;
      slides.push({title: section, html: node.outerHTML});
    }
    return slides;
  }
  function sourceDetails(report) {
    const details = document.createElement('details'); details.className = 'article-source';
    details.append(element('summary', '入力した記事・参照元を見る'));
    const body = element('div', '', 'article-source-body');
    if (report.url) {
      body.append(element('p', '入力したURL'));
      if (/^https?:\/\//i.test(report.url)) {
        const link = element('a', report.url); link.href = report.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; body.append(link);
      } else body.append(element('p', report.url));
    }
    if (report.inputText) { body.append(element('p', '入力した文章'), element('pre', report.inputText)); }
    if (report.appendix) { const appendix = element('div', '', 'article-appendix'); appendix.innerHTML = report.appendix; body.append(appendix); }
    if (!body.childNodes.length) body.append(element('p', '入力元の本文は保存されていません。'));
    details.append(body); return details;
  }
  function prose(report, content, keepPosition) {
    content.append(controls(report));
    if (report.error) content.append(element('p', report.error, 'article-coverage'));
    const sections = [{title: 'この記事が言いたいこと', html: report.summary, slides: []}, ...report.sections];
    const nodes = [], marks = [];
    sections.forEach((section, index) => {
      if (index === 1) content.append(element('h2', '解説'));
      const wrapper = element('section', '', 'article-prose-section');
      const heading = element(index === 0 ? 'h2' : 'h3', section.title);
      const mark = element('button', '', 'article-section-bookmark'); mark.type = 'button';
      function update() {
        const selected = bookmarkIndex(report) === index;
        markAppearance(mark, selected, section.title);
      }
      marks.push(update); update();
      mark.addEventListener('click', async () => {
        const previous = bookmarks[report.id];
        bookmarks[report.id] = {index: bookmarkIndex(report) === index ? null : index, updatedAt: new Date().toISOString(), pending: true};
        try { localStorage.setItem(bookmarkKey, JSON.stringify(bookmarks)); }
        catch { bookmarks[report.id] = previous; document.getElementById('article-detail-reading-status').textContent = 'しおりを保存できませんでした。'; return; }
        marks.forEach(fn => fn()); report.updateReadingStatus();
        try { await persistBookmark(report.id); }
        catch { document.getElementById('article-detail-reading-status').textContent = 'しおりはこのブラウザーに保存しました。サーバー接続時に同期します。'; }
      });
      const headingRow = element('div', '', 'article-heading-row');
      headingRow.append(mark, heading); wrapper.append(headingRow);
      const body = element('div', '', 'article-prose-body'); body.innerHTML = section.html; wrapper.append(body);
      if (section.slides?.length) {
        const deck = element('aside', '', 'article-inline-deck');
        deck.setAttribute('aria-label', `${section.title}の補助スライド`);
        const title = element('h4', ''); const slide = element('div', '', 'article-inline-slide');
        const nav = element('nav', '', 'article-slide-nav');
        const prev = slideArrow('prev', '前の補助スライド');
        const next = slideArrow('next', '次の補助スライド');
        const count = element('span', ''); let position = 0;
        function show(value) {
          position = Math.max(0, Math.min(value, section.slides.length - 1));
          title.textContent = section.slides[position].title;
          slide.innerHTML = section.slides[position].html;
          count.textContent = `${position + 1} / ${section.slides.length}`;
          prev.disabled = position === 0; next.disabled = position === section.slides.length - 1;
        }
        prev.addEventListener('click', () => show(position - 1)); next.addEventListener('click', () => show(position + 1));
        nav.append(prev, count, next); deck.append(title, slide, nav); wrapper.append(deck); show(0);
      }
      nodes.push(wrapper); content.append(wrapper);
    });
    report.updateBookmarks = () => marks.forEach(update => update());
    content.append(sourceDetails(report)); completeButton(report, content);
    const saved = bookmarkIndex(report);
    if (!keepPosition && Number.isInteger(saved)) requestAnimationFrame(() => {
      if (currentId === report.id) nodes[Math.max(0, Math.min(saved, nodes.length - 1))]?.scrollIntoView({block: 'start'});
    });
  }
  function detail(id, keepPosition = false) {
    const report = records.find(item => item.id === id);
    document.getElementById('article-title').textContent = report?.title || '記事解説が見つかりません';
    document.getElementById('article-dates').textContent = report ? `記事執筆時：${report.publishedAt} ／ 生成日時：${date(report.generatedAt)}（日本時間）` : '';
    document.getElementById('article-detail-view').classList.toggle('article-prose', Boolean(report?.sections));
    const content = document.getElementById('article-content'); content.replaceChildren();
    if (!report) return;
    if (report.sections) { prose(report, content, keepPosition); return; }
    content.append(controls(report));
    const slides = report.slides || legacySlides(report.html || '');
    const savedIndex = bookmarkIndex(report);
    const initialIndex = keepPosition ? slideIndex : Number.isInteger(savedIndex) ? savedIndex : 0;
    const stage = element('section', '', 'article-slide'); stage.setAttribute('aria-live', 'polite');
    const heading = element('h2', ''); const body = element('div', '', 'article-slide-body');
    const headingRow = element('div', '', 'article-heading-row');
    stage.append(headingRow, body);
    const nav = element('nav', '', 'article-slide-nav'); nav.setAttribute('aria-label', 'スライド操作');
    const prev = slideArrow('prev', '前のスライド');
    const count = element('span', '');
    const next = slideArrow('next', '次のスライド');
    const bookmark = element('button', '', 'article-section-bookmark'); bookmark.type = 'button';
    headingRow.append(bookmark, heading);
    function show(index) {
      slideIndex = Math.max(0, Math.min(index, slides.length - 1));
      const slide = slides[slideIndex];
      heading.textContent = slide?.title || '解説'; body.innerHTML = slide?.html || '';
      count.textContent = `${slideIndex + 1} / ${slides.length}`;
      prev.disabled = slideIndex === 0; next.disabled = slideIndex === slides.length - 1;
      const marked = bookmarkIndex(report) === slideIndex;
      markAppearance(bookmark, marked, slide?.title || '解説');
    }
    report.updateBookmarks = () => show(slideIndex);
    prev.addEventListener('click', () => show(slideIndex - 1)); next.addEventListener('click', () => show(slideIndex + 1));
    bookmark.addEventListener('click', async () => {
      const previous = bookmarks[id];
      bookmarks[id] = {index: bookmarkIndex(report) === slideIndex ? null : slideIndex, updatedAt: new Date().toISOString(), pending: true};
      try { localStorage.setItem(bookmarkKey, JSON.stringify(bookmarks)); }
      catch { bookmarks[id] = previous; document.getElementById('article-detail-reading-status').textContent = 'しおりを保存できませんでした。'; return; }
      show(slideIndex); report.updateReadingStatus();
      try { await persistBookmark(id); }
      catch { document.getElementById('article-detail-reading-status').textContent = 'しおりはこのブラウザーに保存しました。サーバー接続時に同期します。'; }
    });
    nav.append(prev, count, next); content.append(stage, nav, sourceDetails(report)); completeButton(report, content); show(initialIndex);
  }
  async function refresh(id) {
    try {
      const data = await request('/api/articles');
      if (currentId !== id) return;
      records = data.articles;
      for (const report of records) {
        if (local[report.id]?.pending) { try { await persist(report.id); } catch {} }
        if (bookmarks[report.id]?.pending) { try { await persistBookmark(report.id); } catch {} }
      }
      if (currentId !== id) return;
      if (id) {
        if (!document.getElementById('article-detail-view').classList.contains('article-prose')) detail(id, true);
      } else list();
    } catch { /* Embedded data remains available without a server. */ }
  }
  function render(id) { currentId = id; if (id) detail(id); else list(); refresh(id); }
  function stop() { currentId = null; }
  document.addEventListener('keydown', event => {
    if (document.getElementById('article-detail-view').classList.contains('article-prose')) return;
    if (!currentId || event.altKey || event.ctrlKey || event.metaKey || event.target.closest('input,textarea,pre,details')) return;
    if (event.key === 'ArrowRight') document.querySelector('.article-slide-next')?.click();
    if (event.key === 'ArrowLeft') document.querySelector('.article-slide-prev')?.click();
  });
  return {stop, render};
})();
