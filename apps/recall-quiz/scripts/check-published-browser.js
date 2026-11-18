const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');
const { createStaticServer } = require('./serve.js');

(async () => {
  const remote = process.argv[2];
  const server = remote ? null : createStaticServer({ directory: path.resolve(__dirname, '..'), prefix: '/study/apps/recall-quiz/' });
  if (server) await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const url = remote || `http://127.0.0.1:${server.address().port}/study/apps/recall-quiz/`;
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    await page.clock.setFixedTime(new Date());
    const errors = [], missing = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => { if (response.status() >= 400) missing.push(`${response.status()} ${response.url()}`); });
    const response = await page.goto(url);
    assert.equal(response.status(), 200);
    await page.getByRole('heading', { name: '今日のクイズ', exact: true }).waitFor();
    assert.equal(await page.evaluate(() => document.baseURI), new URL('./public/', url).href);
    await page.getByRole('button', { name: 'この教科で始める', exact: true }).click();
    await page.locator('.countdown-number').filter({ hasText: /^3$/ }).waitFor();
    await page.getByRole('button', { name: '答えを見る', exact: true }).waitFor();
    assert.equal(await page.locator('.main-nav').isVisible(), false);
    assert.equal(await page.locator('.quiz-scope, .course, #content .eyebrow').count(), 0);
    const promptSize = await page.locator('.question').evaluate(el => parseFloat(getComputedStyle(el).fontSize));
    await page.getByRole('button', { name: '答えを見る', exact: true }).click();
    await page.locator('#quiz-controls').waitFor();
    assert.ok(await page.locator('.question').evaluate(el => parseFloat(getComputedStyle(el).fontSize)) < promptSize);
    assert.equal(await page.locator('.main-nav').isVisible(), false);
    assert.deepEqual(await page.locator('#quiz-controls .rating-symbol').allTextContents(), ['×', '△', '○']);
    const colors = await page.locator('.rating-symbol').evaluateAll(nodes => nodes.map(el => getComputedStyle(el).color));
    assert.equal(new Set(colors).size, 3);
    assert.equal(await page.locator('[data-timer-seconds]').innerText(), '15秒');
    const source = page.locator('.source-toggle').first();
    await source.locator('summary').click();
    await source.locator('img').evaluate(image => image.complete && image.naturalWidth ? null : new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = () => reject(Error('原典画像を読み込めません。'));
    }));
    for (const [width, height] of [[320, 640], [390, 844], [768, 1024]]) {
      await page.setViewportSize({ width, height });
      await page.locator('.scroll-region').evaluate(el => { el.scrollTop = 0; });
      const before = await page.locator('#quiz-controls').boundingBox();
      await page.locator('.scroll-region').evaluate(el => { el.scrollTop = el.scrollHeight; });
      assert.deepEqual(await page.locator('#quiz-controls').boundingBox(), before);
      for (const button of await page.locator('#quiz-controls button').all()) {
        const bounds = await button.boundingBox();
        assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width && bounds.y + bounds.height <= height);
        assert.ok(await button.evaluate(el => {
          const rect = el.getBoundingClientRect();
          return el.contains(document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2));
        }));
      }
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('.scroll-region').evaluate(el => { el.scrollTop = 0; });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await page.screenshot({ path: path.resolve(__dirname, '../output/quiz-fixed-ratings.png'), animations: 'disabled' });
    await page.getByRole('button', { name: 'あやふや', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('.step')?.textContent.includes('2 / 5'));
    await page.reload();
    await page.getByRole('button', { name: '答えを見る', exact: true }).waitFor();
    assert.match(await page.locator('.step').innerText(), /2 \/ 5/);
    await page.getByRole('button', { name: '今日はここまで', exact: true }).click();
    await page.getByRole('heading', { name: '今日は、ここまで。', exact: true }).waitFor();
    assert.equal(await page.locator('.main-nav').isVisible(), true);
    assert.equal(await page.locator('#quiz-controls').isVisible(), false);
    await page.locator('[data-screen="history"]').click();
    assert.equal(await page.locator('.history-question').count(), 1);
    assert.equal(await page.locator('.history-question .result-badge').innerText(), '△');
    assert.deepEqual(errors, []);
    assert.deepEqual(missing, []);
    await page.screenshot({ path: path.resolve(__dirname, '../output/published-quiz.png'), animations: 'disabled' });
    console.log(`${url} の画面、教材、原典画像、カウントダウン、回答保存、再読み込みを確認しました。`);
  } finally {
    await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
