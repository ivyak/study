const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '../../..');
const site = path.resolve(__dirname, '../output/site');
function run(command, args, cwd = root) {
  return execFileSync(command, args, { cwd, encoding: 'utf8', stdio: ['pipe', 'pipe', 'inherit'] }).trim();
}
function deploy() {
  if (!fs.existsSync(path.join(site, 'index.html'))) throw Error('先に npm run build を実行してください。');
  const remote = run('git', ['remote', 'get-url', 'origin']);
  const match = remote.match(/github\.com[:/]([^/]+)\/([^/]+?)(?:\.git)?$/);
  if (!match) throw Error('origin にGitHubリポジトリを設定してください。');
  const repo = `${match[1]}/${match[2]}`;
  const repository = JSON.parse(run('gh', ['api', `repos/${repo}`]));
  if (!repository.permissions?.push) throw Error(`${repo}への書き込み権限がありません。gh auth login で公開可能なアカウントに認証してください。`);
  let pages;
  try { pages = JSON.parse(run('gh', ['api', `repos/${repo}/pages`])); }
  catch (error) {
    if (!String(error.stdout).includes('404')) throw error;
  }
  if (pages && (pages.build_type !== 'legacy' || pages.source?.path !== '/' ||
    !['master', 'gh-pages'].includes(pages.source?.branch))) {
    throw Error('この公開元には対応していません。masterかgh-pagesのルートを指定してください。');
  }
  const configure = !pages || pages.source.branch !== 'gh-pages';
  if (configure && !repository.permissions?.admin) throw Error('Pagesの公開元変更にはリポジトリの管理権限が必要です。');
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'recall-pages-'));
  const temporary = path.join(workspace, 'site');
  try {
    run('git', ['init', '-b', 'gh-pages', temporary]);
    run('git', ['remote', 'add', 'origin', remote], temporary);
    const existing = run('git', ['ls-remote', '--heads', 'origin', 'gh-pages']);
    if (existing) run('git', ['fetch', '--depth=1', 'origin', 'gh-pages'], temporary);
    else run('git', ['fetch', root, 'HEAD'], temporary);
    run('git', ['checkout', '-B', 'gh-pages', 'FETCH_HEAD'], temporary);
    for (const name of fs.readdirSync(temporary)) {
      if (name !== '.git') fs.rmSync(path.join(temporary, name), { recursive: true, force: true });
    }
    // Keep the existing site at its current URLs, then add the compiled quiz.
    const archive = path.join(workspace, 'source.tar');
    run('git', ['archive', '--format=tar', `--output=${archive}`, 'HEAD']);
    run('tar', ['-xf', archive, '-C', temporary]);
    const quiz = path.join(temporary, 'apps/recall-quiz');
    fs.rmSync(quiz, { recursive: true, force: true });
    fs.cpSync(site, quiz, { recursive: true });
    fs.writeFileSync(path.join(temporary, '.nojekyll'), '');
    if (process.argv.includes('--dry-run')) {
      const html = fs.readFileSync(path.join(quiz, 'index.html'), 'utf8');
      if (html.includes('__BOOTSTRAP__') || !fs.existsSync(path.join(quiz, 'decks/manifest.json')) ||
        !fs.existsSync(path.join(temporary, 'Kyoto_Univ/index.html'))) throw Error('公開用ファイルが不足しています。');
      console.log('既存のLIFEと、apps/recall-quiz/のビルド済みHTML・教材・画像を確認しました。送信はしていません。');
      return;
    }
    run('git', ['config', 'user.name', run('git', ['config', 'user.name'])], temporary);
    run('git', ['config', 'user.email', run('git', ['config', 'user.email'])], temporary);
    run('git', ['add', '--all'], temporary);
    if (run('git', ['status', '--porcelain'], temporary)) {
      run('git', ['commit', '-m', 'deploy: Recall Quizを更新'], temporary);
      run('git', ['push', 'origin', 'HEAD:refs/heads/gh-pages'], temporary);
    }
    if (configure) {
      pages = JSON.parse(execFileSync('gh', ['api', '--method', pages ? 'PUT' : 'POST', `repos/${repo}/pages`, '--input', '-'], {
        cwd: root, encoding: 'utf8', input: JSON.stringify({ build_type: 'legacy', source: { branch: 'gh-pages', path: '/' } })
      }));
    }
    console.log(`${pages.html_url}apps/recall-quiz/`);
  } finally {
    fs.rmSync(workspace, { recursive: true, force: true });
  }
}
if (require.main === module) {
  try { deploy(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
