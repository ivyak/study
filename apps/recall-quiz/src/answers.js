/* Structured accounting answers shared by the builder and deck validation. */
const RecallAnswers = (() => {
  const fail = () => { throw Error('仕訳・勘定口座・表の解答データを確認してください。'); };
  const label = value => typeof value === 'string' && value.trim().length > 0;
  const side = value => Array.isArray(value) && value.every(item => item && label(item.account) && label(item.amount));
  function validate(blocks) {
    if (!Array.isArray(blocks) || !blocks.length) fail();
    for (const block of blocks) {
      if (!block || (block.caption !== undefined && typeof block.caption !== 'string') ||
        (block.note !== undefined && typeof block.note !== 'string')) fail();
      if (['journal', 'ledger'].includes(block.type)) {
        if (!side(block.debit) || !side(block.credit) || !block.debit.length && !block.credit.length ||
          block.type === 'journal' && (!block.debit.length || !block.credit.length) ||
          block.type === 'ledger' && !label(block.caption)) fail();
      } else if (block.type === 'table') {
        if (!Array.isArray(block.headers) || block.headers.length < 2 || !block.headers.every(label) ||
          !Array.isArray(block.rows) || !block.rows.length || block.rows.some(row => !Array.isArray(row) ||
            row.length !== block.headers.length || row.some(cell => typeof cell !== 'string')) ||
          block.totalRows !== undefined && (!Array.isArray(block.totalRows) ||
            block.totalRows.some(i => !Number.isInteger(i) || i < 0 || i >= block.rows.length))) fail();
      } else fail();
    }
    return blocks;
  }
  const escape = text => String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  function render(blocks, text = escape) {
    validate(blocks);
    return `<div class="structured-answer">${blocks.map(block => {
      const caption = block.caption ? `<caption>${text(block.caption)}</caption>` : '';
      const note = block.note ? `<p class="accounting-note">${text(block.note)}</p>` : '';
      if (block.type === 'table') {
        const head = block.headers.map(cell => `<th scope="col">${text(cell)}</th>`).join('');
        const rows = block.rows.map((row, index) => `<tr${block.totalRows?.includes(index) ? ' class="accounting-total"' : ''}>${row.map((cell, column) => column === 0 ? `<th scope="row">${text(cell)}</th>` : `<td>${text(cell)}</td>`).join('')}</tr>`).join('');
        return `<div class="accounting-table-wrap"><table class="accounting-table accounting-grid">${caption}<thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>${note}`;
      }
      const rows = Array.from({ length: Math.max(block.debit.length, block.credit.length) }, (_, i) => {
        const cells = [block.debit[i], block.credit[i]].map(item => {
          const account = item ? block.type === 'journal' ? `(${text(item.account)})` : text(item.account) : '';
          return `<td class="accounting-account">${account}</td><td class="accounting-amount">${item ? text(item.amount) : ''}</td>`;
        }).join('');
        return `<tr>${cells}</tr>`;
      }).join('');
      return `<div class="accounting-table-wrap"><table class="accounting-table accounting-${block.type}">${caption}<colgroup><col class="accounting-account-col"><col class="accounting-amount-col"><col class="accounting-account-col"><col class="accounting-amount-col"></colgroup><thead><tr><th scope="col" colspan="2">借方</th><th scope="col" colspan="2">貸方</th></tr></thead><tbody>${rows}</tbody></table></div>${note}`;
    }).join('')}</div>`;
  }
  return { validate, render };
})();
if (typeof module !== 'undefined') module.exports = RecallAnswers;
