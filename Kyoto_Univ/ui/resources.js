/* Course resources; past-exam results are preview links, never local downloads. */
window.LifeResources = (() => {
  const names = { weapons: '武器一覧', practice: '演習問題', exams: '過去問' };
  const groups = [['sameTeacherPreviousYear', '同名教科・同名教員・前年度'], ['sameTeacherEarlier', '同名教科・同名教員・前年度よりも前'], ['differentTeacher', '同名教科・違う名前の教員']];
  const statuses = { unsearched: '未検索', running: '検索中', partial: '未確認あり', complete: '検索済み', failed: '検索未完了' };
  let generation = 0, timer = null, runtime = null;
  const base = location.protocol === 'file:' ? 'http://127.0.0.1:8765' : location.origin;
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function link(text, href, external = false) {
    const node = element('a', text);
    if (external) {
      try { if (!['http:', 'https:'].includes(new URL(href).protocol)) return element('span', text); }
      catch { return element('span', text); }
      node.target = '_blank'; node.rel = 'noopener noreferrer';
    }
    node.href = href; return node;
  }
  function stop() { generation++; clearTimeout(timer); timer = null; }
  async function request(path, options = {}) {
    const response = await fetch(base + path, { ...options, signal: AbortSignal.timeout(10000) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '接続を確認してください');
    return data;
  }
  async function connect() { runtime = await request('/api/runtime'); return runtime; }
  function badge(report) {
    const status = report?.execution?.status || 'unsearched';
    return { state: status === 'unsearched' ? 'unsearched' : 'searched', label: statuses[status] || '未確認' };
  }
  function files(content, items) {
    if (!items.length) { content.append(element('p', '資料はまだありません。', 'resource-empty')); return; }
    const list = element('div', null, 'resource-files');
    items.forEach(item => list.append(link(item.name, item.url)));
    content.append(list);
  }
  function table(headers, rows) {
    const wrap = element('div', null, 'table-wrap'), table = element('table', null, 'exam-table exam-links');
    const head = element('thead'), header = element('tr');
    headers.forEach(text => { const cell = element('th', text); cell.scope = 'col'; header.append(cell); });
    head.append(header); table.append(head);
    const body = element('tbody');
    rows.forEach(row => { const tr = element('tr'); row.forEach(value => { const td = element('td'); td.append(value instanceof Node ? value : document.createTextNode(String(value))); tr.append(td); }); body.append(tr); });
    table.append(body); wrap.append(table); return wrap;
  }
  function displayReport(container, course, report, token, onUpdate) {
    const previous = container.querySelector('.search-controls');
    const edited = previous?.dataset.edited === 'true' ? { teacher: previous.elements.teacher.value, year: previous.elements.academicYear.value } : null;
    const open = container.querySelector('.exam-settings')?.open;
    container.replaceChildren();
    const execution = report.execution || { status: 'unsearched' };
    const header = element('div', null, 'exam-search-header');
    header.append(element('span', badge(report).label, 'status-muted'));
    const settings = element('details', null, 'exam-settings');
    settings.open = open ?? execution.status === 'unsearched';
    settings.append(element('summary', '検索条件'));
    const controls = element('form', null, 'search-controls');
    const teacherLabel = element('label', '教員名（ファイル名の表記・必須）'), teacher = element('input');
    teacher.name = 'teacher'; teacher.value = edited?.teacher ?? report.teacher ?? ''; teacher.maxLength = 100; teacher.required = true;
    teacher.placeholder = '例：柴山';
    teacherLabel.append(teacher);
    teacherLabel.append(element('span', '教員名を入力するまで検索できません。', 'field-note'));
    const yearLabel = element('label', '履修年度'), year = element('input');
    year.name = 'academicYear'; year.type = 'number'; year.min = '1900'; year.max = '2100'; year.required = true;
    year.value = edited?.year ?? report.academicYear ?? course.term.slice(0, 4); yearLabel.append(year);
    const run = element('button', execution.status === 'unsearched' ? '検索スキルを実行' : '検索スキルを再実行', 'action-button');
    run.type = 'submit';
    const updateRunState = () => {
      const missing = !teacher.value.trim();
      run.disabled = execution.status === 'running' || missing;
      teacher.setCustomValidity(missing && teacher.value ? '教員名を入力してください。' : '');
    };
    updateRunState();
    controls.append(teacherLabel, yearLabel, run); controls.dataset.edited = String(!!edited);
    controls.addEventListener('input', () => { controls.dataset.edited = 'true'; updateRunState(); });
    settings.append(controls); header.append(settings); container.append(header);
    const message = element('p', execution.error || '', 'status-red'); message.setAttribute('role', 'status'); container.append(message);
    const setup = element('div', null, 'setup-note'); setup.hidden = true;
    setup.append(element('p', '検索にはローカルサーバーを起動してください。'), element('code', 'python3 Kyoto_Univ/serve_portal.py'));
    container.append(setup);
    const refresh = async () => {
      const result = await request(`/api/exams/${encodeURIComponent(course.id)}`);
      if (token !== generation) return;
      course.pastExams = result; course.hasPastPaper = result.hasPastPaper; onUpdate(course);
      displayReport(container, course, result, token, onUpdate);
      if (result.execution?.status === 'running') timer = setTimeout(() => refresh().catch(() => {}), 2000);
    };
    controls.addEventListener('submit', async event => {
      event.preventDefault();
      const teacherName = teacher.value.trim();
      if (!teacherName) { teacher.setCustomValidity('教員名を入力してください。'); teacher.reportValidity(); teacher.focus(); return; }
      teacher.setCustomValidity(''); run.disabled = true; message.textContent = '検索を開始しています…';
      let connected = false;
      try {
        await connect(); connected = true;
        if (!runtime.skillAvailable) throw new Error('過去問検索スキルが見つかりません。');
        await request(`/api/exams/${encodeURIComponent(course.id)}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-LIFE-Token': runtime.token }, body: JSON.stringify({ teacher: teacherName, academicYear: Number(year.value) }) });
        await refresh();
      } catch (error) { message.textContent = connected ? error.message : 'ローカルサーバーを起動してください。'; setup.hidden = connected; updateRunState(); }
    });
    const results = element('div', null, 'filename-results');
    groups.forEach(([key, label]) => {
      const value = report.filenameResults?.[key] || '未確認';
      const row = element('div', null, 'filename-result'); row.append(element('span', label));
      const result = element('span', value === '確認範囲では未発見' ? '見つからず（確認範囲）' : value, 'material-badge');
      result.dataset.kind = value === '未確認' ? '未確認' : '判定';
      if (value === '未確認') result.title = !report.teacher ? '教員名が未入力のため、条件判定をしていません。教員名を入力して検索してください。' : 'ファイル名の情報不足、未走査または一覧の全件取得が未確認です。';
      row.append(result); results.append(row);
    });
    container.append(results);
    if (!report.teacher) container.append(element('p', '教員名が未入力のため、3条件の判定は未実行です。検索条件に教員名を入力してください。', 'status-muted'));
    const candidates = (report.candidates || []).filter(candidate => {
      try { return new URL(candidate.url).hostname === 'drive.google.com'; } catch { return false; }
    });
    if (candidates.length) {
      container.append(table(['タイトル名', '資料の種類', 'URL'], candidates.map(candidate => {
        const badges = element('div', null, 'material-badges');
        (candidate.materialTypes?.length ? candidate.materialTypes : ['未確認']).forEach(kind => {
          const badge = element('span', kind, 'material-badge'); badge.dataset.kind = kind; badges.append(badge);
        });
        const url = link(candidate.url, candidate.url, true); url.title = candidate.name || '';
        return [candidate.name || candidate.title || candidate.subjectName || course.name, badges, url];
      })));
    } else container.append(element('p', execution.status === 'unsearched' ? 'まだ検索していません。' : '資料リンクはまだありません。判定は上の3条件を確認してください。', 'resource-empty'));
    // Unvisited/failed scopes are always the last section.
    if (report.unscanned?.length) {
      const bottom = element('section', null, 'unscanned-areas'); bottom.append(element('h2', '走査できなかった領域'));
      const list = element('ul');
      report.unscanned.forEach(item => {
        const row = element('li'), parts = (item.path || item.url).split('/').filter(Boolean);
        const isDrive = item.source === 'kuinfo2020' || item.source === 'past-exam-drive';
        if (isDrive && parts[0] === item.source) parts.shift();
        const location = isDrive
          ? `Google Drive（検索元: ${item.source}）${parts.length ? ` / ${parts.join(' / ')}` : ' / 検索元フォルダ'}`
          : parts.join(' / ');
        const path = element('strong', location);
        row.append(path, element('span', item.reason, 'status-muted'), link('Driveで開く', item.url, true), element('span', item.url, 'unscanned-url'));
        list.append(row);
      });
      bottom.append(list); container.append(bottom);
    }
  }
  async function render(course, kind, onUpdate) {
    stop(); const token = generation;
    const content = document.getElementById('resource-content'); content.replaceChildren();
    document.getElementById('resource-title').textContent = names[kind];
    document.getElementById('resource-crumb').textContent = names[kind];
    if (kind !== 'exams') { files(content, course.resources?.[kind] || []); return; }
    displayReport(content, course, course.pastExams || {}, token, onUpdate);
    try {
      await connect(); const report = await request(`/api/exams/${encodeURIComponent(course.id)}`);
      if (token !== generation) return;
      course.pastExams = report; course.hasPastPaper = report.hasPastPaper; onUpdate(course);
      displayReport(content, course, report, token, onUpdate);
      if (report.execution?.status === 'running') timer = setTimeout(() => render(course, kind, onUpdate), 2000);
    } catch { /* Saved links remain available when index.html is opened directly. */ }
  }
  return { render, stop, badge, names };
})();
