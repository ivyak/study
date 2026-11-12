const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const port = Number(process.env.RECALL_QUIZ_PORT || 8766);
if (!Number.isInteger(port) || port < 1 || port > 65535) throw Error('ポート番号を確認してください。');
let revision = 0, error = '', timer;
function build() {
  try {
    execFileSync(process.execPath, [path.join(__dirname, 'build.js')], { cwd: root, stdio: 'pipe' });
    revision++;
    error = '';
    console.log('プレビューを更新しました。');
  } catch (failure) {
    error = failure.stderr ? failure.stderr.toString() : failure.message;
    console.error(error);
  }
}
build();
const refresh = `<script>
(() => {
  let revision = null;
  async function poll() {
    try {
      const status = await fetch('/__dev_status', { cache: 'no-store' }).then(r => r.json());
      let overlay = document.getElementById('dev-error');
      if (status.error) {
        if (!overlay) {
          overlay = document.createElement('pre');
          overlay.id = 'dev-error';
          overlay.style.cssText = 'position:fixed;inset:10px;z-index:9999;overflow:auto;padding:20px;background:#fff0ed;color:#762d1f;white-space:pre-wrap;border:2px solid #bd705b;border-radius:12px;font-size:13px';
          document.body.appendChild(overlay);
        }
        overlay.textContent = 'ビルドできませんでした。修正して保存すると再試行します。\\n\\n' + status.error;
      } else {
        if (overlay) overlay.remove();
        if (revision !== null && revision !== status.revision) { location.reload(); return; }
      }
      revision = status.revision;
    } catch (_) { /* Keep the last working preview while the server is restarting. */ }
    setTimeout(poll, 700);
  }
  poll();
})();
</script>`;
const server = http.createServer((request, response) => {
  response.setHeader('Cache-Control', 'no-store');
  const host = request.headers.host;
  if (![ 'localhost:' + port, '127.0.0.1:' + port ].includes(host)) {
    response.writeHead(403); response.end('Forbidden'); return;
  }
  if (request.method !== 'GET') { response.writeHead(405); response.end(); return; }
  const pathname = new URL(request.url, 'http://localhost').pathname;
  if (pathname === '/__dev_status') {
    response.setHeader('Content-Type', 'application/json; charset=utf-8');
    response.end(JSON.stringify({ revision, error })); return;
  }
  if (!['/', '/preview.html'].includes(pathname)) { response.writeHead(404); response.end('Not found'); return; }
  response.setHeader('Content-Type', 'text/html; charset=utf-8');
  const preview = path.join(root, 'output/preview.html');
  let html = fs.existsSync(preview) ? fs.readFileSync(preview, 'utf8') : '<!doctype html><html><body></body></html>';
  // Only the development response may connect to the local reload endpoint.
  html = html.replace("connect-src 'none'", "connect-src 'self'").replace('</body>', refresh + '</body>');
  response.end(html);
});
const targets = ['src', 'decks'].map(folder => path.join(root, folder));
const watchers = targets.map(target => fs.watch(target, { recursive: true }, () => {
  clearTimeout(timer); timer = setTimeout(build, 150);
}));
watchers.push(fs.watch(path.join(__dirname, 'build.js'), () => {
  clearTimeout(timer); timer = setTimeout(build, 150);
}));
server.on('error', failure => {
  console.error(failure.code === 'EADDRINUSE' ? `${port}番ポートは使用中です。RECALL_QUIZ_PORTで別の番号を指定できます。` : failure);
  watchers.forEach(w => w.close()); process.exitCode = 1;
});
server.listen(port, '127.0.0.1', () => console.log(`PCで編集: http://localhost:${port}/ （終了はCtrl+C）`));
function stop() {
  clearTimeout(timer); watchers.forEach(w => w.close()); server.close();
}
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
