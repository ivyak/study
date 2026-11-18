const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');
const { createStaticServer } = require('./serve.js');

(async () => {
  const server = createStaticServer({ directory: path.resolve(__dirname, '../output/site'), prefix: '/study/' });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const now = Date.now();
    await page.clock.setFixedTime(now);
    await page.goto(`http://127.0.0.1:${server.address().port}/study/?screen=history`);
    await page.getByText('まだ回答履歴がありません。', { exact: true }).waitFor();
    await page.locator('[data-screen="quiz"]').click();
    await page.getByRole('button', { name: '全教科から始める', exact: true }).click();
    for (const label of ['3', '2', '1', 'スタート']) {
      await page.locator('.countdown-number').filter({ hasText: new RegExp(`^${label}$`) }).waitFor();
      assert.equal(await page.locator('.question, .timer-track').count(), 0);
      assert.equal((await page.evaluate(() => window.RecallRuntime.snapshot())).state.session, null);
      assert.equal(await page.locator('[data-screen="quiz"]').isDisabled(), true);
      if (label === '3') await page.screenshot({ path: path.resolve(__dirname, '../output/quiz-countdown.png'), animations: 'disabled' });
    }
    await page.locator('.timer-track[data-tone="blue"]').waitFor();
    assert.equal(await page.locator('[data-timer-seconds]').innerText(), '15秒');
    assert.match(await page.locator('.step').innerText(), /1 \/ 5/);
    const tone = async (elapsed, expected) => {
      await page.clock.setFixedTime(now + elapsed);
      await page.locator(`.timer-track[data-tone="${expected}"]`).waitFor();
    };
    await tone(9999, 'blue');
    await tone(10000, 'yellow');
    assert.equal(await page.locator('[data-timer-seconds]').innerText(), '5秒');
    await tone(13000, 'red');
    assert.equal(await page.locator('[data-timer-seconds]').innerText(), '2秒');
    await page.screenshot({ path: path.resolve(__dirname, '../output/quiz-timer-red.png') });
    await page.clock.setFixedTime(now + 15000);
    await page.getByRole('button', { name: 'あやふや', exact: true }).waitFor();
    await page.locator('.timer-track[data-tone="blue"]').waitFor();
    assert.equal(await page.locator('[data-timer-seconds]').innerText(), '15秒');
    await page.setViewportSize({ width: 390, height: 640 });
    await page.locator('.scroll-region').evaluate(el => { el.scrollTop = el.scrollHeight; });
    const pinned = await page.locator('.quiz-timer').boundingBox();
    const scroll = await page.locator('.scroll-region').boundingBox();
    assert.ok(await page.locator('.scroll-region').evaluate(el => el.scrollTop > 0));
    assert.ok(Math.abs(pinned.y - scroll.y) < 2, 'timer must stay at the top while scrolling');
    assert.equal(await page.locator('[data-timer-seconds]').innerText(), '15秒');
    await page.screenshot({ path: path.resolve(__dirname, '../output/quiz-answer-timer.png'), animations: 'disabled' });
    await page.clock.setFixedTime(now + 30000);
    await page.waitForFunction(() => document.querySelector('.step')?.textContent.includes('2 / 5'));
    let state = (await page.evaluate(() => window.RecallRuntime.snapshot())).state;
    assert.equal(state.reviews.length, 1);
    assert.equal(state.reviews[0].result, 'again');
    assert.equal(state.garden.coins, 0);
    await page.getByRole('button', { name: '答えを見る', exact: true }).click();
    await page.getByRole('button', { name: 'あやふや', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('.step')?.textContent.includes('3 / 5'));
    state = (await page.evaluate(() => window.RecallRuntime.snapshot())).state;
    assert.equal(state.reviews.length, 2);
    assert.equal(state.reviews[1].result, 'uncertain');
    assert.equal(state.garden.coins, 0);
    await page.locator('#settings-nav').click();
    await page.locator('[data-screen="history"]').click();
    assert.equal(await page.locator('.history-question').count(), 2);
    assert.equal(await page.locator('.history-question').first().locator('.result-badge').innerText(), '△');
    await page.locator('.history-question').first().locator('summary').click();
    await page.locator('.history-question[open] .catalog-answer .math-text').first().waitFor();
    const review = state.reviews[1];
    await page.locator('[data-screen="catalog"]').click();
    const item = await page.evaluate(id => window.RecallRuntime.decks().find(item => item.id === id), review.deckId);
    await page.locator('#subject').click();
    await page.getByRole('option', { name: item.title, exact: true }).click();
    await page.locator(`[data-open-lesson="${review.deckId}"]`).click();
    await page.locator('.catalog-question').first().waitFor();
    const stats = await page.locator('.catalog-question').filter({ has: page.locator('[aria-label="あやふや1回"]') }).count();
    assert.equal(stats, 1);
    // Keep more than thirty answers in storage while displaying only the latest thirty.
    await page.evaluate(async () => {
      const backup = await window.RecallRuntime.export();
      const sample = backup.state.reviews[1];
      backup.state.session = null;
      backup.state.reviews = Array.from({ length: 35 }, (_, index) => ({ ...sample, id: `history-${index}`,
        result: ['good', 'uncertain', 'again'][index % 3], reviewedAt: new Date(Date.now() + index * 1000).toISOString() }));
      await window.RecallRuntime.restore(backup);
    });
    await page.reload();
    await page.locator('[data-screen="history"]').click();
    assert.equal(await page.locator('.history-question').count(), 30);
    assert.equal(await page.locator('.history-question').first().locator('.result-badge').innerText(), '△');
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 844 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const nav = await page.locator('.main-nav').boundingBox();
    const region = await page.locator('.scroll-region').boundingBox();
    assert.ok(region.y + region.height < nav.y);
    await page.screenshot({ path: path.resolve(__dirname, '../output/quiz-history.png'), animations: 'disabled' });
    await page.reload();
    await page.locator('.history-question').first().waitFor();
    assert.equal(await page.locator('.history-question').count(), 30);
    assert.equal((await page.evaluate(() => window.RecallRuntime.snapshot())).state.reviews.length, 35);
    assert.deepEqual(errors, []);
    console.log('開始前のカウントダウン、15秒タイマーの色変更とスクロール中の固定、自動解答、自動進行、あやふや、一覧の△、直近30問の履歴と再読込を確認しました。');
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
