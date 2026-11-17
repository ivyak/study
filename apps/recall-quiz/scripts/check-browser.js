const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const { createStaticServer } = require('./serve.js');
const { chromium } = require('playwright');
(async () => {
  const server = createStaticServer({ directory: path.resolve(__dirname, '../output/site'), prefix: '/study/' });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const siteURL = `http://127.0.0.1:${server.address().port}/study/`;
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 402, height: 874 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
    const network = [], errors = [];
    await context.route(/^https?:\/\//, route => {
      if (route.request().url().startsWith(siteURL)) {
        assert.equal(route.request().method(), 'GET');
        return route.continue();
      }
      network.push(route.request().url()); return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(siteURL);
    await page.getByRole('button', { name: '答えを見る', exact: true }).waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight));
    assert.ok(await page.locator('.scroll-region').evaluate(el => el.scrollHeight <= el.clientHeight), 'initial quiz should fit without scrolling');
    assert.equal(await page.locator('.has-more-above, .has-more-below').count(), 0);
    const touchSession = await context.newCDPSession(page);
    async function pullFrom(y, direction = 1) {
      await touchSession.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 200, y }] });
      for (const distance of [15, 45, 90, 130]) {
        await touchSession.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: 200, y: y + distance * direction }] });
      }
    }
    async function releaseTouch() {
      await touchSession.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
      await page.waitForFunction(() => document.querySelector('.stretch-content').getAnimations().length === 0);
    }
    await pullFrom(230);
    assert.equal(await page.locator('.stretch-content').evaluate(el => el.style.transform), '');
    await releaseTouch();
    const nav = page.getByRole('navigation', { name: '画面の切り替え' });
    assert.deepEqual(await nav.locator('button').allTextContents(), ['クイズ', 'カレンダー', '庭', '一覧']);
    assert.equal(await nav.locator('svg').count(), 4);
    for (const button of await nav.locator('button').all()) {
      const icon = await button.locator('svg').boundingBox();
      const label = await button.locator('span').boundingBox();
      assert.ok(icon.width >= 28 && icon.y + icon.height <= label.y);
    }
    assert.equal(await nav.evaluate(el => getComputedStyle(el).position), 'fixed');
    assert.ok((await nav.boundingBox()).height <= 68);
    assert.equal(await page.locator('footer').count(), 0);
    assert.equal(await page.locator('#notice').isVisible(), false);
    const safeArea = await page.addStyleTag({ content: '.shell { padding-top: 62px; padding-bottom: 120px; } .main-nav { bottom: 34px; }' });
    assert.ok(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight));
    assert.ok(await page.locator('.scroll-region').evaluate(el => el.scrollHeight <= el.clientHeight));
    await safeArea.evaluate(el => el.remove());
    await page.getByRole('button', { name: '答えを見る', exact: true }).evaluate(el => el.click());
    await page.locator('.answer-reveal').waitFor();
    assert.ok(await page.locator('.answer-reveal').evaluate(el => el.getAnimations().length > 0));
    const source = page.locator('.source-toggle').first();
    const summary = source.locator('summary');
    async function waitForSource() {
      await page.waitForFunction(() => {
        const image = document.querySelector('.source-toggle[open] img');
        return image && image.complete && image.naturalWidth > 0;
      });
    }
    await summary.click();
    await waitForSource();
    assert.ok(await source.locator('img').evaluate(image => image.naturalWidth >= 1000));
    assert.equal(await page.locator('dialog').count(), 0);
    await source.locator('[data-zoom="25"]').click();
    assert.equal(await source.locator('output').innerText(), '125%');
    assert.ok(await source.locator('.source-viewport').evaluate(box => box.scrollWidth > box.clientWidth));
    for (let i = 0; i < 2; i++) await source.locator('[data-zoom="-25"]').click();
    assert.equal(await source.locator('output').innerText(), '75%');
    await source.getByRole('button', { name: '全体', exact: true }).click();
    assert.equal(await source.locator('output').innerText(), '100%');
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 844 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `source overflow at ${width}px`);
    }
    await page.screenshot({ path: path.resolve(__dirname, '../output/source-toggle.png'), fullPage: true, animations: 'disabled' });
    await summary.click();
    await page.waitForFunction(() => !document.querySelector('.source-toggle').open);
    assert.equal(await source.evaluate(view => view.open), false);
    await summary.click();
    await waitForSource();
    assert.equal(await source.locator('output').innerText(), '100%');
    await summary.click();
    await page.getByRole('button', { name: '出なかった', exact: true }).click();
    assert.equal(await page.locator('#coins').innerText(), '0');
    await page.getByRole('button', { name: '答えを見る', exact: true }).waitFor();
    await page.reload();
    assert.match(await page.locator('.step').innerText(), /2 \/ 3/);
    for (let i = 0; i < 2; i++) {
      await page.getByRole('button', { name: '答えを見る', exact: true }).click();
      if (i === 1) {
        assert.ok(await page.locator('.question').innerText());
        await page.screenshot({ path: path.resolve(__dirname, '../output/question.png'), fullPage: true, animations: 'disabled' });
      }
      await page.getByRole('button', { name: '思い出せた', exact: true }).click();
    }
    await page.getByRole('heading', { name: '今日は、ここまででも。' }).waitFor();
    assert.equal(await page.locator('#content [data-page]').count(), 0);
    await page.setViewportSize({ width: 402, height: 874 });
    await page.getByRole('button', { name: '庭', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('#content').getAnimations().length === 0);
    const garden = await page.locator('.garden-stage').boundingBox();
    assert.equal(garden.x, 0);
    assert.equal(garden.y, 0);
    assert.equal(garden.width, page.viewportSize().width);
    assert.equal(garden.height, page.viewportSize().height);
    assert.equal(await page.locator('#coins').innerText(), '2');
    const gachaButton = await page.locator('.open-garden-shop').boundingBox();
    assert.ok(gachaButton.x > garden.width / 2 && gachaButton.y > garden.height / 2);
    await page.locator('.open-garden-shop').click();
    const gacha = page.getByRole('dialog', { name: 'どうぶつガチャ' });
    await gacha.waitFor();
    const gachaSheet = await gacha.locator('.shop-sheet').boundingBox();
    const drawButton = await gacha.locator('.draw-gacha').boundingBox();
    assert.ok(gachaSheet.height < 550, 'gacha sheet has excessive empty space');
    assert.ok(gachaSheet.y + gachaSheet.height - drawButton.y - drawButton.height < 45, 'excessive padding below the draw button');
    assert.equal(await gacha.locator('.gacha-short, .gacha-rule, .shop-footnote').count(), 0);
    assert.equal(await gacha.getByText('次は、どの子に会えるかな。', { exact: true }).count(), 0);
    assert.equal(await gacha.getByRole('button', { name: '10コインで1回まわす', exact: true }).isDisabled(), true);
    assert.equal(await gacha.locator('img').count(), 0);
    await gacha.getByRole('button', { name: 'ラインナップ', exact: true }).click();
    assert.equal(await gacha.locator('.lineup-card.locked').count(), 13);
    assert.ok(await gacha.locator('.gacha-scroll').evaluate(el => el.scrollHeight > el.clientHeight), 'lineup must remain scrollable');
    assert.equal(await gacha.locator('.lineup-card img').count(), 0);
    assert.equal(await gacha.locator('[data-lineup]').count(), 0);
    assert.ok(!(await gacha.innerText()).includes('白いうさぎ'));
    await page.screenshot({ path: path.resolve(__dirname, '../output/garden-lineup-locked.png'), animations: 'disabled' });
    await page.getByRole('button', { name: 'ガチャを閉じる', exact: true }).click();
    await page.waitForFunction(() => !document.querySelector('.garden-shop').open);
    assert.equal(await page.locator('.garden-animal').count(), 0);
    await page.screenshot({ path: path.resolve(__dirname, '../output/garden.png'), animations: 'disabled' });
    await nav.getByRole('button', { name: 'クイズ', exact: true }).click();
    await page.getByRole('button', { name: 'あと3問', exact: true }).click();
    await page.getByRole('button', { name: '答えを見る', exact: true }).waitFor();
    await page.getByRole('button', { name: '今日はここまで', exact: true }).click();
    await page.getByRole('heading', { name: 'いまは、ひと休み。' }).waitFor();
    for (const width of [320, 390, 840]) {
      await page.setViewportSize({ width, height: 844 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `overflow at ${width}px`);
    }
    const saved = await page.evaluate(async () => (await window.RecallRuntime.snapshot()).state);
    assert.equal(saved.reviews.length, 3);
    assert.deepEqual(saved.garden.items, []);
    assert.equal(saved.garden.coins, 2);
    assert.equal(network.length, 0);
    assert.deepEqual(errors, []);
    await page.getByRole('button', { name: 'カレンダー', exact: true }).click();
    await page.getByRole('heading', { name: '学習カレンダー' }).waitFor();
    const today = new Date();
    await page.getByRole('button', { name: `${today.getFullYear()}年${today.getMonth()+1}月${today.getDate()}日、3回答`, exact: true }).click();
    assert.equal(await page.locator('.day-count').innerText(), '3回回答');
    await page.getByRole('button', { name: '前の月', exact: true }).click();
    assert.equal(await page.locator('.calendar-day.has-answers').count(), 0);
    assert.ok(await page.locator('.calendar-day small').evaluateAll(nodes => nodes.every(node => node.textContent === '')));
    await page.getByRole('button', { name: '今月に戻る', exact: true }).click();
    await page.screenshot({ path: path.resolve(__dirname, '../output/calendar.png'), fullPage: true, animations: 'disabled' });
    await page.getByRole('button', { name: '一覧', exact: true }).click();
    assert.equal(await page.locator('.catalog-question').count(), 8);
    assert.equal(await page.locator('#content').getByRole('button', { name: 'クイズに戻る', exact: true }).count(), 0);
    assert.equal(await page.locator('#content [data-deck]').count(), 0);
    await page.getByRole('button', { name: '設定', exact: true }).click();
    assert.equal(await page.locator('#content [data-page]').count(), 0);
    await nav.getByRole('button', { name: '一覧', exact: true }).click();
    const scrollFade = () => page.locator('.scroll-region').evaluate(el => ({ above: el.classList.contains('has-more-above'), below: el.classList.contains('has-more-below') }));
    assert.deepEqual(await scrollFade(), { above: false, below: true });
    await page.locator('.scroll-region').evaluate(el => { el.scrollTop = 150; });
    await page.waitForFunction(() => document.querySelector('.scroll-region').classList.contains('has-more-above'));
    assert.deepEqual(await scrollFade(), { above: true, below: true });
    await page.locator('.scroll-region').evaluate(el => { el.scrollTop = el.scrollHeight; });
    await page.waitForFunction(() => !document.querySelector('.scroll-region').classList.contains('has-more-below'));
    assert.deepEqual(await scrollFade(), { above: true, below: false });
    await page.screenshot({ path: path.resolve(__dirname, '../output/catalog-bottom.png'), animations: 'disabled' });
    await page.locator('.scroll-region').evaluate(el => { el.scrollTop = 0; });
    await page.waitForFunction(() => !document.querySelector('.scroll-region').classList.contains('has-more-above'));
    const firstCounts = await page.locator('.catalog-question').first().locator('.question-counts').innerText();
    assert.match(firstCounts, /出題\s+1/);
    await page.locator('.catalog-question').first().getByLabel('正解0回', { exact: true }).waitFor();
    await page.locator('.catalog-question').first().getByLabel('ミス1回', { exact: true }).waitFor();
    assert.notEqual(await page.locator('.correct').first().evaluate(el => getComputedStyle(el).color), await page.locator('.mistake').first().evaluate(el => getComputedStyle(el).color));
    const disclosure = page.locator('.catalog-question').first();
    await disclosure.locator('summary').evaluate(el => el.click());
    assert.ok(await disclosure.locator('.disclosure-body').evaluate(el => el.getAnimations().length > 0));
    await page.waitForFunction(() => document.querySelector('.catalog-question .disclosure-body').getAnimations().length === 0);
    assert.ok(await page.locator('.catalog-question[open] math').count() > 0);
    const expandedHeight = (await disclosure.boundingBox()).height;
    await disclosure.locator('summary').evaluate(el => el.click());
    assert.ok(await disclosure.locator('.disclosure-body').evaluate(el => el.getAnimations().length > 0));
    await page.waitForFunction(() => !document.querySelector('.catalog-question').open);
    assert.ok((await disclosure.boundingBox()).height < expandedHeight);
    // Reversing direction before a slide ends must leave the requested state intact.
    await disclosure.locator('summary').evaluate(el => { el.click(); el.click(); el.click(); });
    await page.waitForFunction(() => document.querySelector('.catalog-question').open && document.querySelector('.catalog-question .disclosure-body').getAnimations().length === 0);
    const note = page.locator('.count-note');
    await note.locator('summary').evaluate(el => el.click());
    assert.ok(await note.locator('.disclosure-body').evaluate(el => el.getAnimations().length > 0));
    await page.waitForFunction(() => document.querySelector('.count-note .disclosure-body').getAnimations().length === 0);
    await note.locator('summary').press('Enter');
    await page.waitForFunction(() => !document.querySelector('.count-note').open);
    for (const screen of ['calendar', 'catalog']) {
      await page.locator(`[data-screen="${screen}"]`).click();
      assert.ok(await page.locator('#content').evaluate(el => el.getAnimations().length > 0));
      for (const width of [320, 390, 840]) {
        await page.setViewportSize({ width, height: 844 });
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${screen} overflow at ${width}`);
        const bar = await nav.boundingBox();
        assert.ok(bar.x >= 0 && bar.x + bar.width <= width && bar.y + bar.height <= page.viewportSize().height);
        const headerBefore = await page.locator('header').boundingBox();
        await page.locator('.scroll-region').evaluate(el => { el.scrollTop = el.scrollHeight; });
        const region = await page.locator('.scroll-region').boundingBox();
        const last = await page.locator(screen === 'catalog' ? '.catalog-question' : '.day-detail').last().boundingBox();
        assert.ok(last.y + last.height <= region.y + region.height - 12, `${screen} last item obscured`);
        assert.ok(region.y + region.height < bar.y, `${screen} content hidden by navigation`);
        assert.deepEqual(await page.locator('header').boundingBox(), headerBefore);
        assert.equal(await page.evaluate(() => window.scrollY), 0);
        assert.ok(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight));
        assert.notEqual(await page.locator('.scroll-region').evaluate(el => getComputedStyle(el).maskImage), 'none');
      }
    }
    await page.setViewportSize({ width: 402, height: 874 });
    await page.locator('.scroll-region').evaluate(el => { el.scrollTop = 0; });
    await page.screenshot({ path: path.resolve(__dirname, '../output/catalog.png'), fullPage: true, animations: 'disabled' });
    const headerAtRest = await page.locator('header').boundingBox();
    const navAtRest = await nav.boundingBox();
    await pullFrom(220);
    assert.match(await page.locator('.stretch-content').evaluate(el => el.style.transform), /scaleY/);
    assert.deepEqual(await page.locator('header').boundingBox(), headerAtRest);
    assert.deepEqual(await nav.boundingBox(), navAtRest);
    await page.screenshot({ path: path.resolve(__dirname, '../output/scroll-stretch.png') });
    await releaseTouch();
    assert.equal(await page.locator('.stretch-content').evaluate(el => getComputedStyle(el).transform), 'none');
    await page.locator('.scroll-region').evaluate(el => { el.scrollTop = el.scrollHeight; });
    await pullFrom(600, -1);
    assert.match(await page.locator('.stretch-content').evaluate(el => el.style.transform), /scaleY/);
    assert.equal(await page.locator('.stretch-content').evaluate(el => el.style.transformOrigin), 'center bottom');
    await releaseTouch();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.locator('.scroll-region').evaluate(el => { el.scrollTop = 0; });
    await pullFrom(220);
    assert.equal(await page.locator('.stretch-content').evaluate(el => el.style.transform), '');
    await releaseTouch();
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    // Model both the full display and the shorter area available in an embedded WebView.
    for (const height of [874, 760, 640]) {
      await page.setViewportSize({ width: 402, height });
      await page.locator('.scroll-region').evaluate(el => { el.scrollTop = el.scrollHeight; });
      assert.ok(await page.locator('.scroll-region').evaluate(el => el.scrollTop > 0));
      assert.ok(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight));
      assert.equal(await page.evaluate(() => window.scrollY), 0);
    }
    await page.setViewportSize({ width: 402, height: 874 });
    await page.locator('.scroll-region').evaluate(el => { el.scrollTop = 0; });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.locator('.catalog-question').first().locator('summary').evaluate(el => el.click());
    assert.equal(await page.locator('.catalog-question .disclosure-body').first().evaluate(el => el.getAnimations().length), 0);
    await page.getByRole('button', { name: 'カレンダー', exact: true }).click();
    assert.equal(await page.locator('#content').evaluate(el => el.getAnimations().length), 0);
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.reload();
    await page.getByRole('button', { name: 'カレンダー', exact: true }).click();
    assert.match(await page.locator('.month-total').innerText(), /3回/);
    await nav.getByRole('button', { name: '一覧', exact: true }).click();
    await page.getByLabel('教科', { exact: true }).selectOption({ label: '数理統計' });
    await page.locator('[data-deck="statistics-lesson01"]').click();
    await page.getByRole('button', { name: '答えを見る', exact: true }).click();
    await page.locator('.answer-main').waitFor();
    const overbars = page.locator('.question mover, .answer-main mover');
    assert.equal(await overbars.count(), 2);
    for (const mover of await overbars.all()) {
      const bounds = await mover.evaluate(el => {
        const base = el.querySelector('mi').getBoundingClientRect();
        const bar = el.lastElementChild.getBoundingClientRect();
        return { gap: base.top - bar.bottom, offset: Math.abs((base.left + base.right - bar.left - bar.right) / 2) };
      });
      assert.ok(bounds.gap >= 1.5, 'overbar overlaps the X');
      assert.ok(bounds.offset < 3, 'overbar is not centered over the X');
    }
    await page.screenshot({ path: path.resolve(__dirname, '../output/statistics-overbar.png'), animations: 'disabled' });
    const gardenContext = await browser.newContext({ viewport: { width: 402, height: 874 }, isMobile: true, hasTouch: true });
    const gardenState = require('../src/core.js').initial();
    gardenState.garden.coins = 130;
    await gardenContext.addInitScript(state => {
      if (!localStorage.getItem('recall-quiz-preview-v1')) localStorage.setItem('recall-quiz-preview-v1', JSON.stringify(state));
    }, gardenState);
    const gardenPage = await gardenContext.newPage();
    await gardenPage.goto(siteURL);
    await gardenPage.getByRole('button', { name: '庭', exact: true }).click();
    await gardenPage.locator('.open-garden-shop').click();
    await gardenPage.locator('.draw-gacha').evaluate(el => { el.click(); el.click(); });
    await gardenPage.waitForFunction(async () => (await window.RecallRuntime.snapshot()).state.garden.draws.length === 1);
    assert.equal(await gardenPage.locator('#coins').innerText(), '120');
    await gardenPage.locator('.gacha-result img').waitFor();
    await gardenPage.screenshot({ path: path.resolve(__dirname, '../output/gacha-result.png'), animations: 'disabled' });
    await gardenPage.getByRole('button', { name: 'ラインナップ', exact: true }).click();
    assert.equal(await gardenPage.locator('.lineup-card.owned').count(), 1);
    assert.equal(await gardenPage.locator('.lineup-card.locked').count(), 12);
    assert.equal(await gardenPage.locator('.lineup-card.locked img').count(), 0);
    assert.equal(await gardenPage.locator('.lineup-card img').count(), 1);
    await gardenPage.locator('[data-lineup]').click();
    await gardenPage.locator('.lineup-detail img').waitFor();
    await gardenPage.getByRole('button', { name: 'ラインナップに戻る', exact: false }).click();
    await gardenPage.getByRole('dialog').getByRole('button', { name: 'ガチャ', exact: true }).click();
    for (let i = 1; i < 13; i++) {
      await gardenPage.locator('.draw-gacha').click();
      await gardenPage.waitForFunction(async count => (await window.RecallRuntime.snapshot()).state.garden.draws.length === count, i + 1);
      assert.equal(await gardenPage.locator('#coins').innerText(), String(130 - (i + 1) * 10));
    }
    assert.equal(await gardenPage.getByRole('button', { name: 'コンプリート', exact: true }).isDisabled(), true);
    await gardenPage.getByRole('button', { name: 'ラインナップ', exact: true }).click();
    assert.equal(await gardenPage.locator('.lineup-card.owned').count(), 13);
    assert.equal(await gardenPage.locator('.lineup-card.locked').count(), 0);
    await gardenPage.waitForFunction(() => [...document.querySelectorAll('.lineup-card img')].every(img => img.complete && img.naturalWidth > 0));
    await gardenPage.screenshot({ path: path.resolve(__dirname, '../output/garden-lineup-complete.png'), animations: 'disabled' });
    await gardenPage.getByRole('button', { name: 'ガチャを閉じる', exact: true }).click();
    await gardenPage.waitForFunction(() => !document.querySelector('.garden-shop').open);
    assert.equal(await gardenPage.locator('.garden-animal').count(), 13);
    await gardenPage.screenshot({ path: path.resolve(__dirname, '../output/garden-populated.png'), animations: 'disabled' });
    await gardenPage.reload();
    await gardenPage.getByRole('button', { name: '庭', exact: true }).click();
    await gardenPage.locator('.garden-animal').first().waitFor();
    assert.equal(await gardenPage.locator('.garden-animal').count(), 13);
    const savedDraws = await gardenPage.evaluate(async () => (await window.RecallRuntime.snapshot()).state.garden.draws);
    assert.equal(savedDraws.length, 13);
    assert.equal(new Set(savedDraws.map(draw => draw.animalId)).size, 13);
    await gardenPage.emulateMedia({ reducedMotion: 'reduce' });
    assert.ok(await gardenPage.locator('.animal-roam, .animal-body').evaluateAll(nodes => nodes.every(node => node.getAnimations().length === 0)));
    for (const width of [320, 402, 768]) {
      await gardenPage.setViewportSize({ width, height: 874 });
      await gardenPage.locator('.open-garden-shop').click();
      const sheet = await gardenPage.locator('.garden-shop').boundingBox();
      assert.ok(sheet.x >= 0 && sheet.x + sheet.width <= width && sheet.y >= 0 && sheet.y + sheet.height <= 874);
      await gardenPage.getByRole('button', { name: 'ガチャを閉じる', exact: true }).click();
    }
    await gardenContext.close();
    const libraryContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const libraryPage = await libraryContext.newPage();
    await libraryPage.goto(siteURL);
    await libraryPage.getByRole('button', { name: '一覧', exact: true }).click();
    await libraryPage.getByLabel('教科', { exact: true }).selectOption({ label: '数理統計' });
    await libraryPage.locator('.catalog-question').first().waitFor();
    await libraryPage.locator('[data-deck="statistics-lesson01"]').click();
    assert.equal(await libraryPage.locator('.eyebrow').innerText(), '数理統計');
    await libraryPage.reload();
    await libraryPage.getByRole('button', { name: '答えを見る', exact: true }).waitFor();
    assert.equal(await libraryPage.locator('.eyebrow').innerText(), '数理統計');
    await libraryPage.getByRole('button', { name: '一覧', exact: true }).click();
    await libraryPage.getByLabel('教科', { exact: true }).selectOption({ label: '微分積分学続論II' });
    await libraryPage.locator('[data-deck="calc2-lesson01"]').click();
    assert.equal(await libraryPage.locator('.eyebrow').innerText(), '微分積分学続論II');
    assert.equal(await libraryPage.locator('#coins').innerText(), '0');
    await libraryPage.getByRole('button', { name: '設定', exact: true }).click();
    const downloadEvent = libraryPage.waitForEvent('download');
    await libraryPage.getByRole('button', { name: '学習記録を書き出す', exact: true }).click();
    const download = await downloadEvent;
    const exported = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
    assert.equal(exported.format, 'recall-quiz-browser');
    assert.equal(exported.state.garden.coins, 0);
    exported.state.garden.coins = 10;
    libraryPage.on('dialog', dialog => dialog.accept());
    const chooserEvent = libraryPage.waitForEvent('filechooser');
    await libraryPage.getByRole('button', { name: '学習記録を読み込む', exact: true }).click();
    await (await chooserEvent).setFiles({ name: 'backup.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(exported)) });
    await libraryPage.waitForFunction(() => document.querySelector('#coins').textContent === '10');
    const stalePage = await libraryContext.newPage();
    await stalePage.goto(siteURL);
    await stalePage.getByRole('button', { name: '答えを見る', exact: true }).waitFor();
    await libraryPage.getByRole('button', { name: '庭', exact: true }).click();
    await libraryPage.locator('.open-garden-shop').click();
    await libraryPage.locator('.draw-gacha').click();
    await libraryPage.waitForFunction(async () => (await window.RecallRuntime.snapshot()).state.garden.coins === 0);
    await stalePage.getByRole('button', { name: '庭', exact: true }).click();
    await stalePage.locator('.open-garden-shop').click();
    await stalePage.locator('.draw-gacha').click();
    await stalePage.waitForFunction(() => document.querySelector('#coins').textContent === '0');
    const conflictState = await stalePage.evaluate(async () => (await window.RecallRuntime.snapshot()).state);
    assert.equal(conflictState.garden.draws.length, 1);
    assert.equal(conflictState.garden.coins, 0);
    await libraryContext.close();
    console.log('カレンダー・問題別出題数と正誤・教科別閲覧と教材切り替え・再読込を確認しました。');
    console.log('スマホ幅・原典トグルの開閉と拡大縮小・MathML・再読込・自己判定・3問終了・ガチャ・途中終了・外部通信なしを確認しました。');
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
