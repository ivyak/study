/* Shared local-file navigation. Lesson HTML remains the source of its content. */
(() => {
  const isPortal = document.body.dataset.lifePage === 'portal';
  const portal = document.body.dataset.portal || 'index.html';
  const progressKey = 'life.lesson.progress';
  let progress = {};
  try { progress = JSON.parse(localStorage.getItem(progressKey) || '{}') || {}; } catch {}
  const saveProgress = () => { try { localStorage.setItem(progressKey, JSON.stringify(progress)); return true; } catch { return false; } };
  const documentKey = () => decodeURIComponent(location.pathname).split('/Kyoto_Univ/').at(-1).replace(/^\//, '');
  const progressStatus = key => Number.isInteger(progress[key]?.bookmark) ? 'reading' : progress[key]?.status === 'read' ? 'read' : 'unread';
  async function progressRequest(path, options = {}) {
    const origin = location.protocol === 'file:' ? 'http://127.0.0.1:8765' : location.origin;
    const response = await fetch(origin + path, {...options, signal: AbortSignal.timeout(2500)});
    if (!response.ok) throw new Error('接続できません');
    return response.json();
  }
  async function syncProgress() {
    try {
      const remote = (await progressRequest('/api/lesson-progress')).progress;
      for (const [key, value] of Object.entries(remote)) {
        if (!progress[key] || !progress[key].pending && Date.parse(value.updatedAt) > Date.parse(progress[key].updatedAt || 0)) progress[key] = value;
      }
      saveProgress();
      for (const [key, value] of Object.entries(progress)) {
        if (!value.pending) continue;
        try {
          const token = (await progressRequest('/api/runtime')).token;
          const saved = await progressRequest('/api/lesson-progress', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-LIFE-Token': token}, body: JSON.stringify({path: key, ...value})});
          if (progress[key] === value) { progress[key] = saved.progress; saveProgress(); }
        } catch {}
      }
      if (isPortal) { renderTimetable(); updateLessonStatuses(); }
      else { updateDocumentControls?.(); updateDocumentBookmarks?.(); }
    } catch {}
  }
  let updateDocumentControls = null;
  let updateDocumentBookmarks = null;
  if (!isPortal) {
    const article = document.querySelector('article.lesson-document');
    if (article) {
      const key = documentKey();
      const controls = document.createElement('div'); controls.className = 'lesson-progress-controls';
      controls.setAttribute('aria-label', 'この資料の学習ステータス');
      const label = document.createElement('span'); controls.append(label);
      updateDocumentControls = () => { label.textContent = `学習ステータス：${{unread: '未読', reading: '勉強中', read: '完了'}[progressStatus(key)]}`; };
      const header = article.querySelector('header');
      if (header) header.insertAdjacentElement('afterend', controls); else article.prepend(controls);
      updateDocumentControls();
      const headings = [...article.querySelectorAll('h2,h3,h4')].filter(heading => !heading.closest('header, .toc'));
      const marks = [];
      let bookmarkRestored = Boolean(location.hash);
      headings.forEach((heading, index) => {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'lesson-section-bookmark';
        const title = heading.textContent.trim();
        heading.classList.add('lesson-bookmarked-heading'); heading.prepend(button);
        const update = () => {
          const selected = progress[key]?.bookmark === index;
          button.setAttribute('aria-pressed', String(selected));
          button.setAttribute('aria-label', `${title}：しおりを${selected ? '外す' : '付ける'}`);
          button.title = button.getAttribute('aria-label');
        };
        marks.push(update); update();
        button.addEventListener('click', async () => {
          bookmarkRestored = true;
          const previous = progress[key];
          progress[key] = {...previous, bookmark: previous?.bookmark === index ? null : index, updatedAt: new Date().toISOString(), pending: true};
          if (!saveProgress()) { progress[key] = previous; return; }
          marks.forEach(mark => mark()); updateDocumentControls(); await syncProgress();
        });
      });
      updateDocumentBookmarks = () => {
        marks.forEach(mark => mark());
        const saved = progress[key]?.bookmark;
        if (!bookmarkRestored && Number.isInteger(saved) && headings[saved]) {
          bookmarkRestored = true;
          requestAnimationFrame(() => headings[saved].scrollIntoView({block: 'start'}));
        }
      };
      updateDocumentBookmarks();
      const footer = document.createElement('div'); footer.className = 'lesson-complete-controls';
      const complete = document.createElement('button'); complete.type = 'button'; complete.className = 'reading-complete-button'; complete.textContent = '確認完了';
      const note = document.createElement('span'); note.className = 'lesson-progress-note'; note.setAttribute('role', 'status');
      complete.addEventListener('click', async () => {
        progress[key] = {...progress[key], status: 'read', bookmark: null, updatedAt: new Date().toISOString(), pending: true};
        const stored = saveProgress(); marks.forEach(mark => mark()); updateDocumentControls();
        note.textContent = stored ? 'このブラウザーに保存しました。' : '保存できませんでした。';
        await syncProgress();
        if (!progress[key]?.pending) note.textContent = '完了を保存しました。';
      });
      footer.append(complete, note); article.append(footer);
    }
    syncProgress();
  }
  const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const icon = name => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.classList.add('ui-icon');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS(svg.namespaceURI, 'use');
    use.setAttribute('href', `#${name}`);
    svg.append(use);
    return svg;
  };

  // The TOC overlays the article and supports hover, keyboard and touch.
  const toc = document.querySelector('.toc .toc-toggle')?.closest('.toc');
  let closeToc = () => {};
  if (toc) {
    const toggle = toc.querySelector('.toc-toggle');
    const panel = toc.querySelector('.toc-panel');
    let pinned = false, hovered = false;
    const open = value => {
      panel.hidden = !value;
      toggle.setAttribute('aria-expanded', String(value));
    };
    closeToc = () => { pinned = false; hovered = false; open(false); };
    toc.addEventListener('pointerenter', event => {
      if (event.pointerType !== 'touch') { hovered = true; open(true); }
    });
    toc.addEventListener('pointerleave', () => { hovered = false; if (!pinned) open(false); });
    toc.addEventListener('focusin', () => open(true));
    toc.addEventListener('focusout', event => {
      if (!toc.contains(event.relatedTarget) && !pinned && !hovered) open(false);
    });
    toggle.addEventListener('click', () => { pinned = !pinned; open(pinned || hovered); });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !panel.hidden) {
        event.preventDefault(); toggle.focus({ preventScroll: true }); closeToc();
      }
    });
    document.addEventListener('pointerdown', event => { if (!toc.contains(event.target)) closeToc(); });
    panel.querySelectorAll('a[href^="#"]').forEach(link => link.addEventListener('click', () => {
      const target = document.getElementById(link.hash.slice(1));
      closeToc();
      if (target) { target.tabIndex = -1; target.focus({ preventScroll: true }); }
    }));
  }

  if (!isPortal) {
    document.querySelectorAll('[data-home]').forEach(button => button.addEventListener('click', () => location.href = portal));
    document.querySelectorAll('[data-section]').forEach(button => button.addEventListener('click', () => {
      location.href = button.dataset.section === '授業資料' ? portal : `${portal}#section=${encodeURIComponent(button.dataset.section)}`;
    }));
    return;
  }

  const goals = JSON.parse(document.getElementById('goal-data').textContent);
  const courses = JSON.parse(document.getElementById('course-data').textContent);
  const terms = [...new Set(courses.map(course => course.term))].filter(Boolean);
  const latestTerm = terms.at(-1) || '';
  let term = latestTerm, currentCourse = null, view = 'timetable';
  const menu = document.getElementById('lesson-actions');
  let trigger = null;
  const kinds = [['解説', 'slide-icon'], ['要約', 'scroll'], ['理解度クイズ', 'book'], ['対応問題', 'pen']];
  const closeMenu = (restoreFocus = false) => {
    menu.hidden = true;
    if (trigger) {
      trigger.classList.remove('selected'); trigger.setAttribute('aria-expanded', 'false');
      if (restoreFocus) trigger.focus({ preventScroll: true });
    }
    trigger = null;
  };
  const show = (name, direction = 1) => {
    closeMenu(); closeToc();
    window.LifeResources.stop();
    window.LifeArticles.stop();
    for (const id of ['timetable', 'lessons', 'resource', 'skills', 'goals', 'goal-detail', 'articles', 'article-detail', 'empty']) document.getElementById(`${id}-view`).hidden = id !== name;
    const target = document.getElementById(`${name}-view`);
    if (view !== name && !reducedMotion()) {
      target.getAnimations().forEach(animation => animation.cancel());
      target.animate([{ opacity: 0, transform: `translateX(${direction * 20}px)` }, { opacity: 1, transform: 'translateX(0)' }], { duration: 260, easing: 'cubic-bezier(.22,1,.36,1)' });
    }
    view = name; window.scrollTo(0, 0);
    const heading = target.querySelector('h1');
    heading.tabIndex = -1; heading.focus({ preventScroll: true });
  };
  const selectSection = name => document.querySelectorAll('[data-section]').forEach(button => {
    const active = button.dataset.section === name;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  const lessonState = docs => {
    const explanations = docs.filter(doc => doc.kind === '解説');
    if (!explanations.length) return null;
    const states = explanations.map(doc => progressStatus(decodeURIComponent(doc.url)));
    return states.every(value => value === 'read') ? 'read' : states.includes('reading') || states.includes('read') ? 'reading' : 'unread';
  };
  const stateLabels = {unread: '未読', reading: '勉強中', read: '完了'};
  const status = course => {
    const container = document.createElement('span'); container.className = 'course-status';
    const dots = document.createElement('span'); dots.className = 'dots';
    for (let number = 1; number <= 14; number++) {
      const docs = course.documents.filter(doc => doc.lesson === number);
      const exists = docs.length > 0;
      const state = lessonState(docs);
      const dot = document.createElement('i'); dot.className = `dot${exists ? ' done' : ''}${state ? ` lesson-${state}` : ''}`;
      dot.title = `第${number}回：${state ? stateLabels[state] : `解説${exists ? 'なし' : '未作成'}`}`;
      dots.append(dot);
    }
    const resources = document.createElement('span'); resources.className = 'resource-dots';
    [
      ['weapons', '武器一覧', !!course.resources?.weapons?.length],
      ['practice', '演習問題', !!course.resources?.practice?.length],
      ['exams', '過去問', !!course.hasPastPaper]
    ].forEach(([kind, name, exists]) => {
      const dot = document.createElement('i');
      dot.className = `dot resource-flag ${kind}${exists ? ' available' : ''}`;
      dot.dataset.resourceStatus = kind;
      dot.title = `${name}：${exists ? 'あり' : kind === 'exams' ? '未発見・未確認（詳細は過去問ページ）' : '資料なし'}`;
      dot.setAttribute('role', 'img'); dot.setAttribute('aria-label', dot.title);
      resources.append(dot);
    });
    container.append(dots, resources); return container;
  };
  const renderTimetable = () => {
    const body = document.getElementById('schedule-body'); body.replaceChildren();
    document.querySelector('.schedule').setAttribute('aria-label', `${term}の時間割`);
    for (let period = 1; period <= 5; period++) {
      const row = document.createElement('tr');
      const heading = document.createElement('th'); heading.scope = 'row'; heading.textContent = period; row.append(heading);
      for (const day of ['月', '火', '水', '木', '金']) {
        const cell = document.createElement('td');
        courses.filter(course => course.term === term && course.day === day && course.period === period).forEach(course => {
          const button = document.createElement('button'); button.className = 'course'; button.dataset.course = course.id;
          button.setAttribute('aria-label', `${day}曜${period}限 ${course.name}の授業一覧を開く`);
          const title = document.createElement('span'); title.className = 'course-title'; title.textContent = course.name;
          button.append(title, status(course)); button.addEventListener('click', () => navigate({ course: course.id, term })); cell.append(button);
        });
        row.append(cell);
      }
      body.append(row);
    }
    const tabs = [...document.querySelectorAll('[data-term]')];
    tabs.forEach(button => { const active = button.dataset.term === term; button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1; });
  };
  const updateLessonStatuses = () => {
    if (!currentCourse) return;
    document.querySelectorAll('#lesson-list .lesson').forEach(button => {
      const number = Number(button.dataset.lesson);
      const state = lessonState(currentCourse.documents.filter(doc => doc.lesson === number));
      const badge = button.querySelector('.lesson-progress-badge');
      badge.hidden = !state;
      badge.className = `lesson-progress-badge${state ? ` lesson-progress-${state}` : ''}`;
      badge.textContent = state ? stateLabels[state] : '';
      button.setAttribute('aria-label', `第${number}回${state ? `：${stateLabels[state]}` : ''}の資料を選ぶ`);
    });
  };
  syncProgress();
  const menuItems = () => [...menu.querySelectorAll('a,button:not(:disabled)')];
  const openMenu = (number, event) => {
    if (!menu.hidden && trigger === event.currentTarget) { closeMenu(true); return; }
    closeMenu(); trigger = event.currentTarget;
    trigger.classList.add('selected'); trigger.setAttribute('aria-expanded', 'true');
    menu.replaceChildren(); menu.setAttribute('aria-label', `第${number}回の資料`);
    for (const [kind, symbol] of kinds) {
      const docs = currentCourse.documents.filter(doc => doc.lesson === number && doc.kind === kind);
      if (docs.length <= 1) {
        const item = document.createElement(docs.length ? 'a' : 'button');
        item.setAttribute('role', 'menuitem'); item.dataset.kind = kind;
        item.append(icon(symbol), document.createTextNode(kind));
        if (docs.length) item.href = docs[0].url;
        else { item.disabled = true; const label = document.createElement('span'); label.className = 'unavailable'; label.textContent = '未作成'; item.append(label); }
        menu.append(item);
      } else {
        const group = document.createElement('div'); group.className = 'material-group';
        const label = document.createElement('p'); label.textContent = kind; group.append(label);
        docs.forEach(doc => { const link = document.createElement('a'); link.href = doc.url; link.textContent = doc.title; link.setAttribute('role', 'menuitem'); group.append(link); });
        menu.append(group);
      }
    }
    menu.hidden = false;
    const rect = trigger.getBoundingClientRect(), keyboard = event.detail === 0;
    const x = keyboard ? rect.left + Math.min(rect.width / 2, 180) : event.clientX;
    const y = keyboard ? rect.bottom : event.clientY;
    const { width, height } = menu.getBoundingClientRect(), margin = 12;
    let left = x + margin, top = y + margin;
    if (left + width > innerWidth - margin) left = x - width - margin;
    if (top + height > innerHeight - margin) top = y - height - margin;
    menu.style.left = `${Math.max(margin, Math.min(left, innerWidth - width - margin))}px`;
    menu.style.top = `${Math.max(margin, Math.min(top, innerHeight - height - margin))}px`;
    menu.getAnimations().forEach(animation => animation.cancel());
    if (!reducedMotion()) menu.animate([{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 160, easing: 'ease-out' });
    if (keyboard) (menuItems()[0] || trigger).focus({ preventScroll: true });
  };
  const renderLessons = course => {
    currentCourse = course;
    document.querySelector('.term-label').textContent = course.term;
    const heading = document.getElementById('course-title'); heading.replaceChildren(document.createTextNode(`${course.day}曜${course.period}限 `));
    const name = document.createElement('span'); name.style.color = 'var(--gold)'; name.style.marginLeft = '16px'; name.textContent = course.name; heading.append(name);
    document.querySelectorAll('[data-resource]').forEach(link => {
      const kind = link.dataset.resource;
      const available = kind === 'exams' || !!course.resources?.[kind]?.length;
      if (available) {
        link.href = '#' + new URLSearchParams({ course: course.id, resource: kind });
        link.removeAttribute('aria-disabled');
        link.removeAttribute('tabindex');
      } else {
        link.removeAttribute('href');
        link.setAttribute('aria-disabled', 'true');
        link.setAttribute('tabindex', '-1');
      }
    });
    updateSearchBadge(course);
    const list = document.getElementById('lesson-list'); list.replaceChildren();
    for (let number = 1; number <= 14; number++) {
      const docs = course.documents.filter(doc => doc.lesson === number);
      const button = document.createElement('button'); button.className = 'lesson'; button.dataset.lesson = number;
      button.disabled = docs.length === 0;
      button.setAttribute('aria-label', `第${number}回の資料を選ぶ`); button.setAttribute('aria-haspopup', 'menu'); button.setAttribute('aria-expanded', 'false'); button.setAttribute('aria-controls', 'lesson-actions');
      const round = document.createElement('span'); round.className = 'lesson-number'; round.textContent = `第${number}回`;
      const title = document.createElement('span'); title.className = 'lesson-overview'; title.textContent = docs.map(doc => doc.title).join(' / ') || '未作成';
      const meta = document.createElement('span'); meta.className = 'lesson-meta';
      const date = document.createElement('span'); date.className = 'lesson-date'; date.textContent = docs.find(doc => doc.created)?.created || '—';
      const badge = document.createElement('span'); badge.className = 'lesson-progress-badge';
      meta.append(date, badge);
      button.append(round, title, meta); button.addEventListener('click', event => openMenu(number, event)); list.append(button);
    }
    updateLessonStatuses();
    const extra = document.getElementById('extra-materials'); extra.replaceChildren();
    const otherDocs = course.documents.filter(doc => !doc.lesson || doc.lesson > 14);
    extra.hidden = !otherDocs.length;
    if (otherDocs.length) {
      const heading = document.createElement('h2'); heading.textContent = '関連資料'; extra.append(heading);
      otherDocs.forEach(doc => { const link = document.createElement('a'); link.href = doc.url; link.textContent = doc.title; extra.append(link); });
    }
  };
  function updateSearchBadge(course) {
    const button = document.querySelector('[data-resource="exams"]');
    const badge = window.LifeResources.badge(course.pastExams);
    button.dataset.searchState = badge.state;
    button.querySelector('.search-badge').textContent = badge.label;
  }
  const route = () => {
    const params = new URLSearchParams(location.hash.slice(1));
    term = terms.includes(params.get('term')) ? params.get('term') : latestTerm;
    const section = params.get('section') || '授業資料'; selectSection(section);
    document.title = `LIFE｜${section}`;
    if (section === '目標') {
      const goal = goals.find(item => item.date === params.get('date'));
      if (goal) {
        document.getElementById('goal-title').textContent = goal.date;
        document.getElementById('goal-content').innerHTML = goal.html;
        show('goal-detail');
      } else {
        const list = document.getElementById('goal-list'); list.replaceChildren();
        goals.forEach(item => {
          const button = document.createElement('button'); button.className = 'lesson goal-row';
          const date = document.createElement('span'); date.className = 'lesson-number'; date.textContent = item.date;
          const description = document.createElement('span'); description.className = 'lesson-overview'; description.textContent = '目標達成状況サマリ';
          button.append(date, description);
          button.addEventListener('click', () => navigate({ section: '目標', date: item.date })); list.append(button);
        });
        if (!goals.length) { const message = document.createElement('p'); message.textContent = 'サマリはまだありません'; list.append(message); }
        show('goals');
      }
      return;
    }
    if (section === '記事解説') {
      show(params.has('article') ? 'article-detail' : 'articles');
      window.LifeArticles.render(params.get('article'), navigate); return;
    }
    if (section === 'スキル') { show('skills'); return; }
    if (section !== '授業資料') { document.getElementById('empty-title').textContent = section; show('empty'); return; }
    const course = courses.find(course => course.id === params.get('course'));
    if (course) {
      term = course.term;
      const resource = params.get('resource');
      if (Object.hasOwn(window.LifeResources.names, resource)) {
        currentCourse = course;
        document.getElementById('resource-course-link').textContent = course.name;
        show('resource');
        window.LifeResources.render(course, resource, updateSearchBadge);
      } else { renderLessons(course); show('lessons'); }
    }
    else { renderTimetable(); show('timetable', -1); }
  };
  function navigate(params) {
    const hash = new URLSearchParams(params).toString();
    if (location.hash.slice(1) === hash) route(); else location.hash = hash;
  }
  const tabList = document.getElementById('term-tabs');
  terms.forEach((value, index) => {
    const button = document.createElement('button'); button.dataset.term = value; button.setAttribute('role', 'tab'); button.textContent = value;
    button.addEventListener('click', () => navigate({ term: value }));
    button.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % terms.length;
      else if (event.key === 'ArrowLeft') next = (index + terms.length - 1) % terms.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = terms.length - 1;
      else return;
      event.preventDefault(); navigate({ term: terms[next] }); tabList.children[next].focus();
    });
    tabList.append(button);
  });
  document.querySelectorAll('[data-home],[data-back="timetable"]').forEach(button => button.addEventListener('click', () => navigate({ term })));
  document.querySelectorAll('#resource-back,#resource-course-link').forEach(button => button.addEventListener('click', () => navigate({ course: currentCourse.id, term })));
  document.querySelectorAll('[data-section]').forEach(button => button.addEventListener('click', () => navigate(button.dataset.section === '授業資料' ? { term } : { section: button.dataset.section })));
  document.addEventListener('pointerdown', event => { if (!menu.hidden && !menu.contains(event.target) && !trigger?.contains(event.target)) closeMenu(); });
  document.addEventListener('keydown', event => { if (!menu.hidden && event.key === 'Escape') { event.preventDefault(); closeMenu(true); } });
  menu.addEventListener('keydown', event => {
    const items = menuItems(); if (!items.length) return;
    let index = items.indexOf(document.activeElement);
    if (event.key === 'ArrowDown') index = (index + 1) % items.length;
    else if (event.key === 'ArrowUp') index = (index + items.length - 1) % items.length;
    else if (event.key === 'Home') index = 0;
    else if (event.key === 'End') index = items.length - 1;
    else if (event.key === 'Tab') { closeMenu(true); return; }
    else return;
    event.preventDefault(); items[index].focus();
  });
  window.addEventListener('resize', () => closeMenu());
  document.addEventListener('scroll', event => { if (!menu.contains(event.target)) closeMenu(); }, true);
  document.getElementById('article-back').addEventListener('click', () => navigate({ section: '記事解説' }));
  document.getElementById('goal-back').addEventListener('click', () => navigate({ section: '目標' }));
  window.addEventListener('hashchange', route);
  route();
})();
