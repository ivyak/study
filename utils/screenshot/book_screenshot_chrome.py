"""Send concurrent requests over one Chrome connection."""

import json
from pathlib import Path
from queue import Empty, Queue
import subprocess
from threading import Lock, Thread


SOURCE = Path(__file__).with_name("book_screenshot_chrome.mjs")


class ChromeConnection:
  def __init__(self, debug_port):
    self.command = ["node", SOURCE]
    if debug_port:
      self.command.append(str(debug_port))
    self.lock = Lock()
    self.pending = {}
    self.next_id = 0
    self.failure = None

  def __enter__(self):
    print("Chromeに接続します。接続の許可が表示されたら、Chromeで許可してください。", flush=True)
    self.process = subprocess.Popen(
      self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, start_new_session=True,
    )
    self.reader = Thread(target=self.read_replies)
    self.reader.start()
    return self

  def read_replies(self):
    failure = "Chromeとの接続が終了しました。Node.js 22 以上を確認してください。"
    try:
      for line in self.process.stdout:
        reply = json.loads(line)
        if "id" not in reply:
          failure = reply["error"]
          break
        with self.lock:
          pending = self.pending.get(reply["id"])
          if pending is not None:
            pending.put(reply)
    except (OSError, ValueError, KeyError) as error:
      failure = f"Chromeからの応答を読み取れませんでした。{error}"
    finally:
      with self.lock:
        self.failure = failure
        for pending in self.pending.values():
          pending.put({"error": failure})

  def request(self, operation, **params):
    response = Queue()
    with self.lock:
      if self.failure is not None:
        raise ValueError(self.failure)
      self.next_id += 1
      request_id = self.next_id
      self.pending[request_id] = response
      try:
        self.process.stdin.write(json.dumps({"id": request_id, "command": operation, **params}) + "\n")
        self.process.stdin.flush()
      except BrokenPipeError:
        # The read thread reports the process's error or EOF.
        pass

    timeout = 125 if operation == "tabs" else max(15, params.get("timeout", 0) / 1000 + 3)
    try:
      reply = response.get(timeout=timeout)
      if reply.get("timeout") and operation == "screenshot":
        return None
      if "error" in reply:
        raise ValueError(reply["error"])
      return reply["result"]
    except Empty as error:
      raise ValueError("Chromeの制御プログラムから応答がありません。") from error
    finally:
      with self.lock:
        self.pending.pop(request_id, None)

  def __exit__(self, exc_type, exc, traceback):
    try:
      self.process.stdin.close()
    except BrokenPipeError:
      pass
    try:
      self.process.wait(timeout=3)
    except subprocess.TimeoutExpired:
      self.process.kill()
      self.process.wait()
    self.reader.join()
    self.process.stdout.close()
