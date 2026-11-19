const test = require('node:test');
const assert = require('node:assert/strict');
const answers = require('../src/answers');
const core = require('../src/core');
const deck = require('../decks/bookkeeping-chapter02.json');

const payroll = { type: 'journal', caption: '賃金給料の支払い',
  debit: [{ account: '賃金給料', amount: '7,000' }],
  credit: [{ account: '預り金', amount: '800' }, { account: '現金', amount: '6,200' }] };

test('structured answers preserve unequal debit and credit line counts without changing data', () => {
  const blocks = [structuredClone(payroll)];
  const before = structuredClone(blocks);
  const html = answers.render(blocks);
  assert.deepEqual(blocks, before);
  for (const value of ['賃金給料', '7,000', '預り金', '800', '現金', '6,200']) assert.ok(html.includes(value));
  assert.ok(!html.includes('***'));
  assert.doesNotThrow(() => answers.validate([{ type: 'ledger', caption: '材料', debit: [],
    credit: [{ account: '仕掛品', amount: '5,000' }] }]));
});
test('account names, captions, notes and cells cannot insert executable HTML', () => {
  const attack = '<img src=x onerror=alert(1)>';
  const html = answers.render([{ ...payroll, caption: attack, note: '<script>alert(1)</script>',
    debit: [{ account: attack, amount: '***' }] },
  { type: 'table', headers: ['項目', '金額'], rows: [[attack, '***']] }]);
  assert.doesNotMatch(html, /<(?:img|script)\b/);
  assert.ok(html.includes('&lt;img'));
  assert.ok(html.includes('&lt;script&gt;'));
});
test('invalid accounting layouts are rejected during deck validation', () => {
  for (const block of [
    { ...payroll, debit: [] },
    { ...payroll, credit: [{ account: '現金', amount: 7000 }] },
    { type: 'ledger', debit: payroll.debit, credit: [] },
    { type: 'table', headers: ['摘要', '金額'], rows: [['値']] },
    { type: 'table', headers: ['摘要', '金額'], rows: [['値', '***']], totalRows: [1] },
    { type: 'html', value: '<table></table>' }
  ]) {
    const broken = structuredClone(deck);
    broken.questions[0].answerBlocks = [block];
    assert.throws(() => core.validateDeck(broken));
  }
});
test('all existing bookkeeping layouts validate and textual answers remain available', () => {
  assert.doesNotThrow(() => core.validateDeck(deck));
  for (const q of deck.questions) {
    assert.ok(q.answer.trim());
    if (q.answerBlocks) assert.ok(answers.render(q.answerBlocks).includes('<table'));
  }
});
