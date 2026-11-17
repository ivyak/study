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
  if (pages && (pages.source?.branch !== 'gh-pages' || pages.source?.path !== '/')) {
    throw Error('既存のPages公開設定が異なります。公開先を確認してください。');
  }
  if (!pages && !repository.permissions?.admin) throw Error('Pagesの初回設定にはリポジトリの管理権限が必要です。');
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'recall-pages-'));
  try {
    run('git', ['init', '-b', 'gh-pages', temporary]);
    run('git', ['remote', 'add', 'origin', remote], temporary);
    const existing = run('git', ['ls-remote', '--heads', 'origin', 'gh-pages']);
    if (existing) {
      run('git', ['fetch', '--depth=1', 'origin', 'gh-pages'], temporary);
      run('git', ['checkout', '-B', 'gh-pages', 'FETCH_HEAD'], temporary);
    }
    for (const name of fs.readdirSync(temporary)) {
      if (name !== '.git') fs.rmSync(path.join(temporary, name), { recursive: true, force: true });
    }
    fs.cpSync(site, temporary, { recursive: true });
    run('git', ['config', 'user.name', run('git', ['config', 'user.name'])], temporary);
    run('git', ['config', 'user.email', run('git', ['config', 'user.email'])], temporary);
    run('git', ['add', '--all'], temporary);
    if (run('git', ['status', '--porcelain'], temporary)) {
      run('git', ['commit', '-m', 'deploy: Recall Quizを更新'], temporary);
      run('git', ['push', 'origin', 'HEAD:refs/heads/gh-pages'], temporary);
    }
    if (!pages) {
      pages = JSON.parse(execFileSync('gh', ['api', '--method', 'POST', `repos/${repo}/pages`, '--input', '-'], {
        cwd: root, encoding: 'utf8', input: JSON.stringify({ build_type: 'legacy', source: { branch: 'gh-pages', path: '/' } })
      }));
    }
    console.log(pages.html_url);
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}
if (require.main === module) {
  try { deploy(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
