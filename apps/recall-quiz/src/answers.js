/* Structured accounting content shared by the builder and deck validation. */
const RecallAnswers = (() => {
  const fail = () => { throw Error('仕訳・勘定口座・表のデータを確認してください。'); };
  const label = value => typeof value === 'string' && value.trim().length > 0;
  function validate(blocks, { allowBlanks = false } = {}) {
    const cell = value => typeof value === 'string' || allowBlanks && value === null;
    const entry = value => label(value) || allowBlanks && value === null;
    const side = value => Array.isArray(value) && value.every(item => item && entry(item.account) && entry(item.amount));
    if (!Array.isArray(blocks) || !blocks.length) fail();
    for (const block of blocks) {
      if (!block || (block.caption !== undefined && typeof block.caption !== 'string') ||
        (block.note !== undefined && typeof block.note !== 'string')) fail();
      if (block.type === 'text') {
        if (!label(block.text)) fail();
      } else if (['journal', 'ledger'].includes(block.type)) {
        if (!side(block.debit) || !side(block.credit) || !block.debit.length && !block.credit.length ||
          block.type === 'journal' && (!block.debit.length || !block.credit.length) ||
          block.type === 'ledger' && !label(block.caption)) fail();
      } else if (block.type === 'table') {
        if (!Array.isArray(block.headers) || block.headers.length < 2 || !block.headers.every(label) ||
          !Array.isArray(block.rows) || !block.rows.length || block.rows.some(row => !Array.isArray(row) ||
            row.length !== block.headers.length || row.some(value => !cell(value))) ||
          block.totalRows !== undefined && (!Array.isArray(block.totalRows) ||
            block.totalRows.some(i => !Number.isInteger(i) || i < 0 || i >= block.rows.length))) fail();
      } else fail();
    }
    return blocks;
  }
  const escape = text => String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  function render(blocks, text = escape, options = {}) {
    validate(blocks, options);
    const value = (cell, key, name = '解答欄') => cell === null ?
      `<input type="text" class="accounting-blank" data-field="${key}" aria-label="${name}" autocomplete="off" spellcheck="false">` : text(cell);
    return `<div class="structured-answer">${blocks.map((block, bi) => {
      if (block.type === 'text') return `<p class="exercise-text">${text(block.text)}</p>`;
      const caption = block.caption ? `<caption>${text(block.caption)}</caption>` : '';
      const note = block.note ? `<p class="accounting-note">${text(block.note)}</p>` : '';
      if (block.type === 'table') {
        const head = block.headers.map(cell => `<th scope="col">${text(cell)}</th>`).join('');
        const rows = block.rows.map((row, ri) => `<tr${block.totalRows?.includes(ri) ? ' class="accounting-total"' : ''}>${row.map((cell, ci) => {
          const content = value(cell, `b${bi}-r${ri}-c${ci}`);
          return ci === 0 ? `<th scope="row">${content}</th>` : `<td>${content}</td>`;
        }).join('')}</tr>`).join('');
        return `<div class="accounting-table-wrap"><table class="accounting-table accounting-grid">${caption}<thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>${note}`;
      }
      const rows = Array.from({ length: Math.max(block.debit.length, block.credit.length) }, (_, ri) => {
        const cells = [block.debit[ri], block.credit[ri]].map((item, si) => {
          const account = item ? value(item.account, `b${bi}-s${si}-r${ri}-account`, '科目の解答欄') : '';
          const amount = item ? value(item.amount, `b${bi}-s${si}-r${ri}-amount`, '金額の解答欄') : '';
          return `<td class="accounting-account">${item && block.type === 'journal' ? `(${account})` : account}</td><td class="accounting-amount">${amount}</td>`;
        }).join('');
        return `<tr>${cells}</tr>`;
      }).join('');
      return `<div class="accounting-table-wrap"><table class="accounting-table accounting-${block.type}">${caption}<colgroup><col class="accounting-account-col"><col class="accounting-amount-col"><col class="accounting-account-col"><col class="accounting-amount-col"></colgroup><thead><tr><th scope="col" colspan="2">借方</th><th scope="col" colspan="2">貸方</th></tr></thead><tbody>${rows}</tbody></table></div>${note}`;
    }).join('')}</div>`;
  }
  return { validate, render };
})();
if (typeof module !== 'undefined') module.exports = RecallAnswers;
