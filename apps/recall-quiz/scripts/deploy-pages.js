const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const app = path.resolve(__dirname, '..');
const site = path.join(app, 'output/site');

function prepare() {
  execFileSync(process.execPath, [path.join(__dirname, 'build.js')], { cwd: app, stdio: 'inherit' });
  const html = fs.readFileSync(path.join(site, 'index.html'), 'utf8');
  if (html.includes('__BOOTSTRAP__')) throw Error('公開用HTMLのビルドが完了していません。');
  const target = path.join(app, 'public');
  fs.rmSync(target, { recursive: true, force: true });
  fs.mkdirSync(target, { recursive: true });
  for (const directory of ['assets', 'decks']) {
    fs.cpSync(path.join(site, directory), path.join(target, directory), { recursive: true });
  }
  fs.writeFileSync(path.join(app, 'index.html'), html.replace('<head>', '<head>\n  <base href="./public/">'));
  console.log('masterで公開するindex.htmlとpublic/を更新しました。コミットしてpushするとPagesに反映されます。');
}
if (require.main === module) {
  try { prepare(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
module.exports = { prepare };
