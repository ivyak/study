const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 402, height: 874 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
    const network = [], errors = [];
    await context.route(/^https?:\/\//, route => { network.push(route.request().url()); return route.abort(); });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.resolve(__dirname, '../output/preview.html')).href);
    assert.ok(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight));
    assert.ok(await page.locator('.scroll-region').evaluate(el => el.scrollHeight <= el.clientHeight), 'initial quiz should fit without scrolling');
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
    assert.ok((await page.locator('footer').boundingBox()).height <= 12);
    const safeArea = await page.addStyleTag({ content: '.shell { padding-top: 62px; padding-bottom: 120px; } .main-nav { bottom: 34px; }' });
    assert.ok(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight));
    assert.ok(await page.locator('.scroll-region').evaluate(el => el.scrollHeight <= el.clientHeight));
    await safeArea.evaluate(el => el.remove());
    await page.getByRole('button', { name: '答えを見る', exact: true }).click();
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
    assert.equal(await source.evaluate(view => view.open), false);
    await summary.click();
    await waitForSource();
    assert.equal(await source.locator('output').innerText(), '100%');
    await summary.click();
    await page.getByRole('button', { name: '出なかった', exact: true }).click();
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
    await page.getByRole('button', { name: '庭', exact: true }).click();
    await page.getByRole('button', { name: '3 コイン', exact: true }).click();
    await page.getByRole('button', { name: '庭にいます', exact: true }).waitFor();
    assert.equal(await page.locator('#coins').innerText(), '0');
    await page.screenshot({ path: path.resolve(__dirname, '../output/garden.png'), fullPage: true, animations: 'disabled' });
    await page.locator('#content').getByRole('button', { name: 'クイズに戻る', exact: true }).click();
    await page.getByRole('button', { name: 'あと3問', exact: true }).click();
    await page.getByRole('button', { name: '答えを見る', exact: true }).waitFor();
    await page.getByRole('button', { name: '今日はここまで', exact: true }).click();
    await page.getByRole('heading', { name: 'いまは、ひと休み。' }).waitFor();
    for (const width of [320, 390, 840]) {
      await page.setViewportSize({ width, height: 844 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `overflow at ${width}px`);
    }
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('recall-quiz-preview-v1')));
    assert.equal(saved.reviews.length, 3);
    assert.deepEqual(saved.garden.items, ['sprout']);
    assert.equal(network.length, 0);
    assert.deepEqual(errors, []);
    await page.getByRole('button', { name: 'カレンダー', exact: true }).click();
    await page.getByRole('heading', { name: '学習カレンダー' }).waitFor();
    const today = new Date();
    await page.getByRole('button', { name: `${today.getFullYear()}年${today.getMonth()+1}月${today.getDate()}日、3回答`, exact: true }).click();
    assert.equal(await page.locator('.day-count').innerText(), '3回回答');
    await page.getByRole('button', { name: '前の月', exact: true }).click();
    assert.equal(await page.locator('.calendar-day.has-answers').count(), 0);
    await page.getByRole('button', { name: '今月に戻る', exact: true }).click();
    await page.screenshot({ path: path.resolve(__dirname, '../output/calendar.png'), fullPage: true, animations: 'disabled' });
    await page.getByRole('button', { name: '一覧', exact: true }).click();
    assert.equal(await page.locator('.catalog-question').count(), 8);
    const firstCounts = await page.locator('.catalog-question').first().locator('.question-counts').innerText();
    assert.match(firstCounts, /出題\s+1/);
    await page.locator('.catalog-question').first().getByLabel('正解0回', { exact: true }).waitFor();
    await page.locator('.catalog-question').first().getByLabel('ミス1回', { exact: true }).waitFor();
    assert.notEqual(await page.locator('.correct').first().evaluate(el => getComputedStyle(el).color), await page.locator('.mistake').first().evaluate(el => getComputedStyle(el).color));
    await page.locator('.catalog-question').first().locator('summary').click();
    assert.ok(await page.locator('.catalog-question[open] math').count() > 0);
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
    await page.getByRole('button', { name: 'カレンダー', exact: true }).click();
    assert.equal(await page.locator('#content').evaluate(el => el.getAnimations().length), 0);
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.reload();
    await page.getByRole('button', { name: 'カレンダー', exact: true }).click();
    assert.match(await page.locator('.month-total').innerText(), /3回/);
    const libraryContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
    await libraryContext.route(/^https?:\/\//, route => route.abort());
    await libraryContext.addInitScript(() => {
      Object.defineProperty(window, 'BOOT', { configurable: true, set(value) {
        delete window.BOOT;
        value.decks = [value.deck, { ...value.deck, id: 'physics-lesson01', title: '物理学',
          questions: value.deck.questions.map(q => ({ ...q, id: 'physics-' + q.id })) }];
        window.BOOT = value;
      } });
    });
    const libraryPage = await libraryContext.newPage();
    await libraryPage.goto(pathToFileURL(path.resolve(__dirname, '../output/preview.html')).href);
    await libraryPage.getByRole('button', { name: '一覧', exact: true }).click();
    await libraryPage.getByLabel('教科', { exact: true }).selectOption({ label: '物理学' });
    assert.equal(await libraryPage.locator('.catalog-question').count(), 8);
    await libraryPage.getByRole('button', { name: 'この教材で学習', exact: true }).click();
    assert.equal(await libraryPage.locator('.eyebrow').innerText(), '物理学');
    await libraryPage.reload();
    assert.equal(await libraryPage.locator('.eyebrow').innerText(), '物理学');
    await libraryPage.getByRole('button', { name: '一覧', exact: true }).click();
    await libraryPage.getByLabel('教科', { exact: true }).selectOption({ label: '微分積分学続論II' });
    await libraryPage.getByRole('button', { name: 'この教材で学習', exact: true }).click();
    assert.equal(await libraryPage.locator('.eyebrow').innerText(), '微分積分学続論II');
    await libraryContext.close();
    console.log('カレンダー・問題別出題数と正誤・教科別閲覧と教材切り替え・再読込を確認しました。');
    console.log('スマホ幅・原典トグルの開閉と拡大縮小・MathML・再読込・自己判定・3問終了・購入・途中終了・外部通信なしを確認しました。');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
