const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
    const network = [], errors = [];
    await context.route(/^https?:\/\//, route => { network.push(route.request().url()); return route.abort(); });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.resolve(__dirname, '../output/preview.html')).href);
    await page.getByRole('button', { name: '答えを見る', exact: true }).click();
    await page.getByRole('button', { name: '原典を見る（p.3）', exact: true }).click();
    await page.locator('#source-image').evaluate(image => image.decode());
    assert.ok(await page.locator('#source-image').evaluate(image => image.naturalWidth >= 1000));
    await page.getByRole('button', { name: '拡大', exact: true }).click();
    assert.ok(await page.locator('#source-scroll').evaluate(box => box.scrollWidth > box.clientWidth));
    await page.screenshot({ path: path.resolve(__dirname, '../output/source-viewer.png'), fullPage: true });
    await page.getByRole('button', { name: '原典を閉じる', exact: true }).click();
    assert.equal(await page.locator('#source-viewer').evaluate(view => view.open), false);
    await page.getByRole('button', { name: '出なかった', exact: true }).click();
    await page.getByRole('button', { name: '答えを見る', exact: true }).waitFor();
    await page.reload();
    assert.match(await page.locator('.step').innerText(), /2 \/ 3/);
    for (let i = 0; i < 2; i++) {
      await page.getByRole('button', { name: '答えを見る', exact: true }).click();
      if (i === 1) {
        assert.ok(await page.locator('math').count() > 0);
        await page.screenshot({ path: path.resolve(__dirname, '../output/question.png'), fullPage: true });
      }
      await page.getByRole('button', { name: '思い出せた', exact: true }).click();
    }
    await page.getByRole('heading', { name: '今日は、ここまででも。' }).waitFor();
    await page.getByRole('button', { name: '庭', exact: true }).click();
    await page.getByRole('button', { name: '3 コイン', exact: true }).click();
    await page.getByRole('button', { name: '庭にいます', exact: true }).waitFor();
    assert.equal(await page.locator('#coins').innerText(), '0');
    await page.screenshot({ path: path.resolve(__dirname, '../output/garden.png'), fullPage: true });
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
    console.log('スマホ幅・原典画像の表示と拡大・MathML・再読込・自己判定・3問終了・購入・途中終了・外部通信なしを確認しました。');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
