const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');
const { createStaticServer } = require('./serve');
const exerciseQuestions = require('../decks/bookkeeping-chapter02-exercises.json').questions;
const questionCount = exerciseQuestions.length;

(async () => {
  const remote = process.argv[2];
  const server = remote ? null : createStaticServer({ directory: path.resolve(__dirname, '..'), prefix: '/study/apps/recall-quiz/' });
  if (server) await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = remote || `http://127.0.0.1:${server.address().port}/study/apps/recall-quiz/`;
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.clock.setFixedTime(new Date());
    await page.goto(`${base}?screen=catalog&lesson=bookkeeping-chapter02`);
    await page.waitForFunction(() => document.querySelectorAll('.catalog-question').length === 22);
    assert.equal(await page.locator('.catalog-prompt').filter({ hasText: /とは何か？/ }).count(), 22);
    await page.locator('[data-study-type="exercise"]').click();
    assert.equal(new URL(page.url()).pathname, new URL(base).pathname);
    assert.equal(await page.locator('[data-open-lesson]').count(), 1);
    await page.locator('[data-open-lesson]').click();
    await page.waitForFunction(count => document.querySelectorAll('.catalog-question').length === count, questionCount);
    await page.locator('.catalog-question > summary').first().click();
    assert.ok(await page.locator('.catalog-question').first().locator('.accounting-blank').count() === 6);
    await page.locator('[data-deck]').click();
    await page.locator('.exercise-title').waitFor();
    assert.equal(await page.locator('.exercise-title').innerText(), exerciseQuestions[0].label);
    assert.equal(await page.locator('.quiz-timer').count(), 0);
    assert.equal(await page.locator('.main-nav').isVisible(), false);
    const input = page.locator('[data-draft-key] input').first();
    await input.fill('材料');
    await page.reload();
    await page.locator('.exercise-title').waitFor();
    assert.equal(await input.inputValue(), '材料');
    await page.clock.setFixedTime(new Date(Date.now() + 60000));
    await page.waitForTimeout(300);
    assert.equal(await page.locator('.answer').count(), 0);
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 844 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const button = page.locator('#quiz-controls [data-action="reveal"]');
      const before = await button.boundingBox();
      await page.locator('.scroll-region').evaluate(el => { el.scrollTop = el.scrollHeight; });
      assert.deepEqual(await button.boundingBox(), before);
      assert.ok(before.y + before.height <= 844 && before.x >= 0);
      assert.equal(await page.locator('.exercise-question .accounting-table').evaluateAll(tables => tables.every(table => table.scrollWidth <= table.clientWidth + 2)), true);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('.scroll-region').evaluate(el => { el.scrollTop = 0; });
    await page.screenshot({ path: path.resolve(__dirname, '../output/exercise-question.png'), animations: 'disabled' });
    await page.locator('#quiz-controls [data-action="reveal"]').click();
    await page.locator('.answer').waitFor();
    assert.equal(await input.inputValue(), '材料');
    assert.equal(await page.locator('.answer .accounting-blank').count(), 0);
    assert.deepEqual(await page.locator('#quiz-controls .rating-symbol').allTextContents(), ['×', '△', '○']);
    await page.screenshot({ path: path.resolve(__dirname, '../output/exercise-answer.png'), animations: 'disabled' });
    for (let n = 1; n <= questionCount; n++) {
      assert.equal(await page.locator('.exercise-title').innerText(), exerciseQuestions[n - 1].label);
      if (n > 1) {
        assert.equal(await page.locator('.answer').count(), 0);
        assert.ok(await page.locator('.exercise-question .accounting-blank').count() >= 6);
        if (n === 8) assert.match(await page.locator('.exercise-question').innerText(), /12,000円/);
        if (n === 9) assert.match(await page.locator('.exercise-question').innerText(), /18,000円/);
        await page.locator('#quiz-controls [data-action="reveal"]').click();
        await page.locator('.answer').waitFor();
      }
      await page.locator('#quiz-controls [data-result="good"]').click();
      if (n < questionCount) await page.waitForFunction(label => document.querySelector('.exercise-title')?.textContent === label, exerciseQuestions[n].label);
    }
    await page.getByRole('heading', { name: `${questionCount}問、おつかれさま。` }).waitFor();
    await page.locator('[data-screen="history"]').click();
    assert.equal(await page.locator('.history-question').count(), questionCount);
    await page.locator('[data-study-type="knowledge"]').click();
    assert.equal(await page.locator('.history-question').count(), 0);
    await page.locator('[data-screen="quiz"]').click();
    await page.getByRole('button', { name: '全教科から始める', exact: true }).click();
    await page.locator('.question').waitFor();
    assert.equal(await page.locator('.quiz-timer').count(), 1);
    const snapshot = await page.evaluate(async () => {
      const { state, deck } = window.RecallRuntime.boot();
      return { mode: state.session.mode, length: state.session.queue.length, mixed: deck.questions.some(q => q.promptBlocks), reviews: state.reviews.length, coins: state.garden.coins };
    });
    assert.equal(snapshot.mode, undefined);
    assert.equal(snapshot.length, 5);
    assert.equal(snapshot.mixed, false);
    assert.equal(snapshot.reviews, questionCount);
    assert.equal(snapshot.coins, questionCount);
    const oldPrompt = await page.evaluate(async () => {
      const runtime = window.RecallRuntime;
      const backup = await runtime.export();
      const old = (await runtime.loadDeck('bookkeeping-chapter02')).retiredQuestions[0];
      backup.state.reviews.push({ id: 'legacy-bookkeeping', deckId: 'bookkeeping-chapter02', questionId: old.id,
        questionVersion: old.version, result: 'uncertain', reviewedAt: new Date().toISOString() });
      const combined = (await runtime.loadDeck('bookkeeping-chapter02-exercises')).retiredQuestions[0];
      backup.state.reviews.push({ id: 'legacy-combined-exercise', deckId: 'bookkeeping-chapter02-exercises', questionId: combined.id,
        questionVersion: combined.version, studyType: 'exercise', result: 'uncertain', reviewedAt: new Date().toISOString() });
      backup.state.session = null;
      await runtime.restore(backup);
      return old.prompt;
    });
    await page.goto(`${base}?screen=history&studyType=knowledge`);
    await page.waitForFunction(prompt => document.querySelector('.history-question .math-text')?.textContent === prompt, oldPrompt);
    assert.equal(await page.locator('.history-question .catalog-prompt .math-text').innerText(), oldPrompt);
    await page.locator('.history-question > summary').click();
    assert.ok(await page.locator('.history-question .source-toggle').count() > 0);
    assert.equal(await page.locator('#coins').innerText(), String(questionCount));
    await page.locator('[data-study-type="exercise"]').click();
    assert.equal(new URL(page.url()).pathname, new URL(base).pathname);
    await page.reload();
    await page.waitForFunction(count => document.querySelectorAll('.history-question').length === count, questionCount + 1);
    const combined = page.locator('.history-question').filter({ has: page.locator('summary .math-text', { hasText: /^範例2-1$/ }) });
    await combined.locator(':scope > summary').click();
    assert.equal(await combined.locator('.exercise-question .exercise-text').count(), 7);
    assert.ok(await combined.locator('.source-toggle').count() > 0);
    assert.deepEqual(errors, []);
    console.log('小問単位の演習9問、空欄入力、前の取引の記入、再読み込み、固定ボタン、旧範例の履歴保存を確認しました。');
  } finally {
    await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
