const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const mime = { '.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8' };
function createStaticServer({ directory, prefix = '/', transformHTML, status } = {}) {
  const root = path.resolve(directory);
  return http.createServer((request, response) => {
    response.setHeader('Cache-Control', 'no-store');
    if (request.method !== 'GET') { response.writeHead(405); response.end(); return; }
    let pathname;
    try { pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname); }
    catch (_) { response.writeHead(400); response.end(); return; }
    if (status && pathname === '/__dev_status') {
      response.setHeader('Content-Type', mime['.json']); response.end(JSON.stringify(status())); return;
    }
    if (!pathname.startsWith(prefix)) { response.writeHead(404); response.end(); return; }
    const relative = pathname.slice(prefix.length) || 'index.html';
    const file = path.resolve(root, relative);
    if (!file.startsWith(root + path.sep)) { response.writeHead(403); response.end(); return; }
    try {
      if (!fs.statSync(file).isFile()) throw Error('not a file');
      response.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream');
      if (path.extname(file) === '.html' && transformHTML) response.end(transformHTML(fs.readFileSync(file, 'utf8')));
      else fs.createReadStream(file).pipe(response);
    } catch (_) { response.writeHead(404); response.end(); }
  });
}
module.exports = { createStaticServer };
if (require.main === module) {
  const directory = path.resolve(__dirname, '../output/site');
  const port = Number(process.env.RECALL_QUIZ_PORT || 8766);
  createStaticServer({ directory }).listen(port, '127.0.0.1', () => console.log(`http://localhost:${port}/`));
}
