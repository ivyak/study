import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";

async function endpoint(debugPort) {
  let port = debugPort;
  let path;
  if (port) {
    const response = await fetch(`http://127.0.0.1:${port}/json/version`, {
      redirect: "error",
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) throw new Error("Chromeのデバッグポートに接続できません。");
    path = new URL((await response.json()).webSocketDebuggerUrl).pathname;
  } else {
    const activePort = join(homedir(), "Library", "Application Support", "Google", "Chrome", "DevToolsActivePort");
    try {
      [port, path] = (await readFile(activePort, "utf8")).trim().split(/\r?\n/);
    } catch (error) {
      if (error.code === "EACCES" || error.code === "EPERM") {
        throw new Error("Chromeの接続情報を読めません。macOSのファイルとフォルダの設定で、実行元のターミナルにGoogle Chromeへのアクセスを許可してください。");
      }
      if (error.code === "ENOENT") {
        throw new Error("Chromeを起動し、chrome://inspect/#remote-debugging でリモートデバッグを有効にしてください。");
      }
      throw error;
    }
  }
  if (!/^\d{1,5}$/.test(port) || Number(port) < 1 || Number(port) > 65535 ||
      !/^\/devtools\/browser\/[\w-]+$/.test(path)) {
    throw new Error("Chromeの接続情報を確認できません。リモートデバッグを設定し直してください。");
  }
  return `ws://127.0.0.1:${port}${path}`;
}

async function connect(url) {
  const socket = new WebSocket(url);
  let id = 0;
  const pending = new Map();
  socket.addEventListener("message", ({ data }) => {
    const reply = JSON.parse(data);
    pending.get(reply.id)?.(reply);
  });
  socket.addEventListener("close", () => {
    for (const complete of pending.values()) {
      complete({ error: { message: "Chromeとの接続が切れました。" } });
    }
  });
  if (!(await new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), 60000);
    const done = (ok) => {
      clearTimeout(timer);
      resolve(ok);
    };
    socket.addEventListener("open", () => done(true), { once: true });
    socket.addEventListener("close", () => done(false), { once: true });
    socket.addEventListener("error", () => done(false), { once: true });
  }))) {
    socket.close();
    throw new Error("Chromeへの接続ができません。Chromeに接続許可の画面が出ている場合は許可してください。");
  }

  function send(method, params = {}, sessionId, timeout = 5000) {
    if (socket.readyState !== WebSocket.OPEN) throw new Error("Chromeとの接続が切れました。");
    const requestId = ++id;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(requestId);
        const error = new Error(`${method} が時間内に応答しませんでした。`);
        error.name = "TimeoutError";
        reject(error);
      }, timeout);
      pending.set(requestId, (reply) => {
        pending.delete(requestId);
        clearTimeout(timer);
        if (reply.error) reject(new Error(reply.error.message));
        else resolve(reply.result);
      });
      socket.send(JSON.stringify({ id: requestId, method, params, sessionId }));
    });
  }
  return { send, close: () => socket.close() };
}

let client;
let sessionId;
try {
  client = await connect(await endpoint(process.argv[2]));
  const key = { key: "ArrowRight", code: "ArrowRight", windowsVirtualKeyCode: 39 };
  for await (const line of createInterface({ input: process.stdin })) {
    try {
      const request = JSON.parse(line);
      let result;
      switch (request.command) {
        case "tabs": {
          const { targetInfos } = await client.send("Target.getTargets", {}, undefined, 60000);
          const tabs = targetInfos.filter((tab) => tab.type === "page" && /^(https?|file):/.test(tab.url));
          result = request.groupByWindow ? await Promise.all(tabs.map(async (tab) => {
            try {
              const { windowId } = await client.send("Browser.getWindowForTarget", { targetId: tab.targetId });
              return { ...tab, windowId };
            } catch {
              // A tab can close while its window is being looked up.
              return { ...tab, windowId: null };
            }
          })) : tabs;
          break;
        }
        case "attach":
          ({ sessionId } = await client.send("Target.attachToTarget", { targetId: request.target, flatten: true }));
          // Keep the reader active internally while a different tab is selected in Chrome.
          await client.send("Emulation.setFocusEmulationEnabled", { enabled: true }, sessionId);
          break;
        case "screenshot":
          ({ data: result } = await client.send("Page.captureScreenshot", {
            format: "png",
            fromSurface: true,
          }, sessionId, request.timeout));
          break;
        case "right":
          await client.send("Input.dispatchKeyEvent", { ...key, type: "rawKeyDown" }, sessionId);
          await client.send("Input.dispatchKeyEvent", { ...key, type: "keyUp" }, sessionId);
          break;
        default:
          throw new Error("未対応のChrome操作です。");
      }
      process.stdout.write(JSON.stringify({ result: result ?? null }) + "\n");
    } catch (error) {
      process.stdout.write(JSON.stringify({ error: error.message, timeout: error.name === "TimeoutError" }) + "\n");
    }
  }
} catch (error) {
  process.stdout.write(JSON.stringify({ error: error.message }) + "\n");
} finally {
  if (sessionId) {
    try {
      await client.send("Emulation.setFocusEmulationEnabled", { enabled: false }, sessionId, 1000);
    } catch {
      // If the target is gone, there is no remaining focus state to reset.
    }
  }
  client?.close();
}
