"""Capture a macOS book viewer and export chapter PDFs."""

import argparse
from base64 import b64decode
from collections import Counter
import ctypes
from hashlib import blake2b
from io import BytesIO
import json
import os
from pathlib import Path
from shlex import join as shell_join
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.parse import urlsplit

import img2pdf
from PIL import Image


POLL_INTERVAL = 0.5
TIMEOUT = 60
WAIT_PROGRESS_INTERVAL = 5
NATIVE_SOURCE = Path(__file__).with_name("book_screenshot_macos.swift")
CHROME_SOURCE = Path(__file__).with_name("book_screenshot_chrome.mjs")


def terminal_app():
  if os.environ.get("TERM_PROGRAM", "").casefold() == "ghostty":
    return "Ghostty"
  return "このコマンドを実行したターミナルアプリ"


def accessibility_help():
  app = terminal_app()
  return (
    "右矢印キーを送信する許可がありません。\n"
    "システム設定の「プライバシーとセキュリティ」で"
    "「デバイスの制御とデータへのアクセス」を開いてください。"
    "この項目がない場合は、同じ画面の「アクセシビリティ」を開いてください。\n"
    f"{app}をオンにします。一覧にない場合は、追加ボタンから{app}を選びます。\n"
    "設定後、撮影コマンドをもう一度実行してください。許可が反映されない場合は、"
    f"{app}を終了して開き直してください。"
  )


class ViewerCrop:
  """Find the page against the viewer's flat gray margins."""

  def __init__(self, screen):
    width, height = screen.size
    self.probes = (width // 5, width * 4 // 5)
    pixels = screen.load()
    samples = [
      pixels[x, y]
      for x in self.probes
      for y in range(height // 3, height * 2 // 3, max(1, height // 100))
    ]
    self.gray, count = Counter(samples).most_common(1)[0]
    if count < len(samples) * 0.8 or max(self.gray) - min(self.gray) > 8:
      raise ValueError("左右の灰色の余白を検出できません。表示を調整するか、--crop を指定してください。")

    def gray_sides(y):
      return all(self.is_gray(pixels[x, y]) for x in self.probes)

    middle = height // 2
    if not gray_sides(middle):
      raise ValueError("画面中央に書籍ビューアを表示するか、--crop を指定してください。")
    self.top = middle
    self.bottom = middle + 1
    while self.top > 0 and gray_sides(self.top - 1):
      self.top -= 1
    while self.bottom < height and gray_sides(self.bottom):
      self.bottom += 1

  def is_gray(self, pixel):
    return max(abs(value - gray) for value, gray in zip(pixel, self.gray)) <= 4

  def __call__(self, screen):
    pixels = screen.load()
    center = screen.width // 2
    outer_left, outer_right = self.probes
    height = self.bottom - self.top
    edges = []
    for part in (0.20, 0.35, 0.50, 0.65, 0.80):
      y = self.top + round(height * part)
      if not all(self.is_gray(pixels[x, y]) for x in self.probes):
        continue
      left = outer_left
      right = outer_right
      while left < center and self.is_gray(pixels[left, y]):
        left += 1
      while right > center and self.is_gray(pixels[right, y]):
        right -= 1
      edges.append((left, right + 1))
    if len(edges) < 3:
      return None
    left = int(median(edge[0] for edge in edges))
    right = int(median(edge[1] for edge in edges))
    if (right - left < screen.width // 8 or
        any(sum(abs(edge[i] - bound) <= 3 for edge in edges) < 3
            for i, bound in enumerate((left, right)))):
      return None
    return screen.crop((left, self.top, right, self.bottom))


def signature(page):
  preview = page.copy()
  preview.thumbnail((256, 384), Image.Resampling.BILINEAR)
  # A scanned blank page has visible shading. Solid white or gray loading frames do not.
  if max(high - low for low, high in preview.getextrema()) <= 2:
    return None
  return page.size, blake2b(preview.tobytes(), digest_size=16).digest()


def wait_for_page(read_page, previous, stable_seconds, deadline, number):
  candidate = None
  started = deadline - TIMEOUT
  next_progress = started + WAIT_PROGRESS_INTERVAL
  while time.monotonic() < deadline:
    page = read_page(deadline)
    current = signature(page) if page is not None else None
    now = time.monotonic()
    if now >= deadline:
      break
    if current is None or current == previous:
      candidate = None
    elif current != candidate:
      candidate = current
      since = now
    elif now - since >= stable_seconds:
      return page, current
    if now >= next_progress:
      elapsed = int(now - started)
      print(f"{number} 枚目の表示を待っています。{elapsed} 秒経過、上限 {TIMEOUT} 秒。", flush=True)
      next_progress = now + WAIT_PROGRESS_INTERVAL
    time.sleep(min(POLL_INTERVAL, max(0, deadline - time.monotonic())))
  return None


def check_accessibility():
  print("右矢印キーを送信できるよう、アクセシビリティの許可を確認しています。", flush=True)
  framework = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
  trusted = framework.AXIsProcessTrusted
  trusted.argtypes = []
  trusted.restype = ctypes.c_bool
  if not trusted():
    raise ValueError(accessibility_help())


def native_command(temp, *, for_capture=False):
  binary = temp / "book_screenshot_macos"
  print("Swiftの補助プログラムを一時フォルダにコンパイルしています。数十秒かかる場合があります。", flush=True)
  if for_capture:
    print("撮影時は、前面のアプリの確認と、そのアプリへの右矢印キーの送信に使います。", flush=True)
  print("章の自動判定では、PNGの上部から見出しを読み取るために使います。", flush=True)
  subprocess.run(
    ["swiftc", "-module-cache-path", str(temp / "swift-cache"), str(NATIVE_SOURCE), "-o", str(binary)],
    check=True,
  )
  return binary


def run_native(native, action, *arguments):
  try:
    result = subprocess.run([native, action, *arguments], capture_output=True, text=True, timeout=5)
  except subprocess.TimeoutExpired as error:
    raise ValueError("macOSから操作の応答がなかったため停止しました。") from error
  if result.returncode == 2:
    raise ValueError(accessibility_help())
  if result.returncode:
    raise ValueError(result.stderr.strip() or "macOSの撮影操作に失敗しました。")
  return result.stdout.strip()


def capture(args, temp, native):
  print("書籍の最初のページを前面に表示してください。", flush=True)
  for seconds in range(args.delay, 0, -1):
    print(f"撮影開始まで {seconds} 秒。", flush=True)
    time.sleep(1)
  print("いま前面にあるアプリを撮影対象として確認しています。", flush=True)
  pid = run_native(native, "front")
  frame = temp / "screen.png"

  def read_screen(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
      return None
    try:
      subprocess.run(
        ["/usr/sbin/screencapture", "-xm", "-tpng", "-T0", frame],
        check=True, timeout=remaining,
      )
    except subprocess.TimeoutExpired:
      return None
    except subprocess.CalledProcessError as error:
      raise ValueError(
        "画面を撮影できませんでした。画面収録の許可を確認してください。\n"
        "システム設定の「プライバシーとセキュリティ」で"
        f"「画面収録とシステムオーディオ録音」を開き、{terminal_app()}をオンにしてください。"
      ) from error
    with Image.open(frame) as image:
      return image.convert("RGB")

  def check_front():
    if run_native(native, "front") != pid:
      raise ValueError("撮影開始時と異なるアプリが前面にあるため停止しました。")

  def right():
    run_native(native, "right", pid)

  capture_pages(args, read_screen, right, check_front)


def capture_chrome(args):
  command = ["node", CHROME_SOURCE]
  if args.debug_port:
    command.append(str(args.debug_port))
  print("Chromeに接続します。接続の許可が表示されたら、Chromeで許可してください。", flush=True)
  with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as chrome:
    def request(operation, **params):
      try:
        chrome.stdin.write(json.dumps({"command": operation, **params}) + "\n")
        chrome.stdin.flush()
      except BrokenPipeError:
        pass
      line = chrome.stdout.readline()
      if not line:
        raise ValueError("Chromeとの接続が終了しました。Node.js 22 以上を確認してください。")
      reply = json.loads(line)
      if reply.get("timeout") and operation == "screenshot":
        return None
      if "error" in reply:
        raise ValueError(reply["error"])
      return reply["result"]

    try:
      tabs = request("tabs")
      if args.tab:
        matches = [tab for tab in tabs if tab["url"] == args.tab]
        if len(matches) != 1:
          raise ValueError("--tab とURLが一致するタブを1つ開いてください。")
        selected = matches[0]
      else:
        if not tabs:
          raise ValueError("Chromeに撮影できるタブがありません。")
        for number, tab in enumerate(tabs, 1):
          print(f'{number:2}  {tab["title"]}  {urlsplit(tab["url"]).hostname or ""}')
        answer = input("撮影するタブの番号を入力してください。 ")
        if not answer.isdecimal() or not 1 <= int(answer) <= len(tabs):
          raise ValueError("一覧にあるタブの番号を指定してください。")
        selected = tabs[int(answer) - 1]
      request("attach", target=selected["targetId"])
      print(f'撮影を開始します。 {selected["title"]}', flush=True)

      def read_screen(deadline):
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
          return None
        image_data = request("screenshot", timeout=remaining)
        if image_data is None:
          return None
        with Image.open(BytesIO(b64decode(image_data))) as image:
          return image.convert("RGB")

      capture_pages(args, read_screen, lambda: request("right"))
    finally:
      try:
        chrome.stdin.close()
        chrome.wait(timeout=3)
      except subprocess.TimeoutExpired:
        chrome.kill()


def capture_pages(args, read_screen, right, check_target=None):
  print("撮影範囲を確認しています。", flush=True)
  screen = read_screen(time.monotonic() + TIMEOUT)
  if screen is None:
    raise ValueError("画面を取得できませんでした。")
  screen_size = screen.size
  if args.crop is None:
    crop = ViewerCrop(screen)
  else:
    left, top, right, bottom = args.crop
    if not (0 <= left < right <= screen.width and 0 <= top < bottom <= screen.height):
      raise ValueError(f"--crop は画面画像の範囲 {screen.width} × {screen.height} 内で指定してください。")
    crop = lambda image: image.crop(args.crop)

  def read_page(deadline):
    current = read_screen(deadline)
    if current is None:
      return None
    if current.size != screen_size:
      raise ValueError("撮影中に画像の大きさが変わったため停止しました。")
    return crop(current)

  previous = None
  number = 1
  deadline = time.monotonic() + TIMEOUT
  while True:
    if number == 1:
      print("1 枚目の表示が安定するのを待っています。", flush=True)
    result = wait_for_page(read_page, previous, args.stable, deadline, number)
    if result is None:
      print(f"{TIMEOUT} 秒以内に新しいページを確認できなかったため停止しました。", flush=True)
      return
    page, previous = result
    if check_target is not None:
      check_target()
    path = args.folder / "pages" / f"{number:06d}.png"
    pending = path.with_suffix(".tmp")
    page.save(pending, format="PNG")
    pending.replace(path)
    print(f"{number} 枚目を保存しました。", flush=True)
    if number == args.max_pages:
      print(f"指定された {number} 枚の撮影が完了しました。", flush=True)
      return
    number += 1
    right()
    deadline = time.monotonic() + TIMEOUT
    print(f"右矢印キーを送りました。{number} 枚目の表示を待っています。", flush=True)


def chapter_spec(value):
  start, colon, title = value.partition(":")
  title = title.strip()
  if not colon or not start.isdecimal() or int(start) < 1 or not title:
    raise argparse.ArgumentTypeError("章は 12:第1章 のように、撮影順の番号と章名を指定してください。")
  if any(char in "/\\" or ord(char) < 32 for char in title):
    raise argparse.ArgumentTypeError("章名にはスラッシュや制御文字を使えません。")
  return int(start), title


def find_chapters(native, pages_dir):
  # OCR outputs a tab-separated capture index, chapter number and heading for each candidate.
  print("章の見出しを読み取っています。", flush=True)
  output = subprocess.check_output([native, "chapters", pages_dir], text=True)
  chapters = []
  last_number = 0
  for line in output.splitlines():
    page, number, heading = line.split("\t", 2)
    number = int(number)
    if number > last_number:
      heading = heading.replace("/", " ").replace("\\", " ").strip()
      chapters.append((int(page), heading))
      last_number = number
  return chapters


def export_pdfs(args, temp, native=None):
  pages_dir = args.folder / "pages"
  pages = sorted(path for path in pages_dir.glob("*.png") if path.is_file())
  if not pages:
    raise ValueError("PDFにできる撮影画像がありません。")
  print(f"撮影済みの {len(pages)} 枚からPDFを作成します。", flush=True)
  if args.chapter:
    starts = sorted(args.chapter)
    missing = [index for index, _ in starts if index > len(pages)]
    if missing:
      if args.command == "pdf":
        raise ValueError(f"撮影済みの範囲を超える章開始番号があります。 {missing}")
      print(f"撮影済みの範囲を超える章開始番号があります。 {missing}", flush=True)
    starts = [(index, title) for index, title in starts if index <= len(pages)]
  else:
    try:
      starts = find_chapters(native or native_command(temp), pages_dir)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
      print(f"章の読み取りが中断されました。 {error}", file=sys.stderr)
      starts = []
  if not starts:
    print("章の区切りが見つからなかったため、撮影分を1冊のPDFにまとめます。", flush=True)
    starts = [(1, "全ページ")]
  elif starts[0][0] > 1:
    starts.insert(0, (1, "表紙・前付け"))

  output = args.folder / "pdf"
  suffix = 1
  while True:
    try:
      output.mkdir()
      break
    except FileExistsError:
      suffix += 1
      output = args.folder / f"pdf-{suffix}"

  stops = [index for index, _ in starts[1:]] + [len(pages) + 1]
  for chapter, ((start, title), stop) in enumerate(zip(starts, stops), 1):
    path = output / f"{chapter:02d} {title[:60]}.pdf"
    pending = path.with_suffix(".tmp")
    print(f"{chapter}/{len(starts)} 件目のPDFを作成しています。{start}〜{stop - 1} 枚目。", flush=True)
    try:
      with pending.open("wb") as stream:
        img2pdf.convert([str(page) for page in pages[start - 1:stop - 1]], outputstream=stream)
      pending.replace(path)
    except img2pdf.ImageOpenError as error:
      raise ValueError(f"{start}〜{stop - 1} 枚目のどれかを開けませんでした。 {error}") from error
    finally:
      pending.unlink(missing_ok=True)
    print(f"{start}〜{stop - 1} 枚目を保存しました。 {path}", flush=True)
  print(f"PDFの作成が完了しました。保存先は {output} です。", flush=True)


def positive_integer(value):
  number = int(value)
  if number < 1:
    raise argparse.ArgumentTypeError("1 以上を指定してください。")
  return number


def destination_error(args):
  folder = args.folder
  suffix = 2
  while True:
    alternative = folder.parent / f"{folder.name or 'book-capture'}-{suffix}"
    if not os.path.lexists(alternative):
      break
    suffix += 1
  example = shell_join([sys.executable, sys.argv[0], args.command, str(alternative)])
  return ValueError(
    f"保存先 {folder} はすでに存在します。既存の内容を上書きしないよう、撮影を開始しませんでした。\n"
    "まだ存在しない保存先を指定してください。フォルダは撮影ツールが作成します。\n"
    f"実行例\n  {example}"
  )


def main():
  parser = argparse.ArgumentParser(description="macOSで書籍ビューアを撮影し、章ごとにPDFにまとめます。")
  commands = parser.add_subparsers(dest="command", required=True)
  capture_parser = commands.add_parser("capture", help="撮影してPDFにまとめる")
  chrome_parser = commands.add_parser("chrome", help="Chromeの指定タブを撮影してPDFにまとめる")
  pdf_parser = commands.add_parser("pdf", help="撮影済みの画像からPDFを作る")
  for command in (capture_parser, chrome_parser, pdf_parser):
    command.add_argument("folder", type=Path, help="撮影フォルダ")
    command.add_argument("--chapter", action="append", type=chapter_spec, help="12:第1章 の形式で指定。複数指定可")
  for command in (capture_parser, chrome_parser):
    command.add_argument("--crop", nargs=4, type=int, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    command.add_argument("--stable", type=positive_integer, default=2, help="ページが静止したとみなすまでの秒数")
    command.add_argument("--max-pages", type=positive_integer, help="撮影する枚数の上限")
  capture_parser.add_argument("--delay", type=positive_integer, default=10, help="撮影開始までの秒数")
  chrome_parser.add_argument("--tab", help="撮影するタブのURL。省略時は一覧から選ぶ")
  chrome_parser.add_argument("--debug-port", type=positive_integer, help="明示的に起動したChromeのローカルデバッグポート")
  args = parser.parse_args()
  numbers = [index for index, _ in args.chapter or []]
  if len(numbers) != len(set(numbers)):
    parser.error("同じ開始番号を複数の章に指定できません。")
  if args.command != "pdf" and args.stable >= TIMEOUT:
    parser.error(f"--stable は {TIMEOUT} 秒未満にしてください。")
  if args.command == "chrome" and args.debug_port and args.debug_port > 65535:
    parser.error("--debug-port は 65535 以下にしてください。")

  try:
    with TemporaryDirectory(prefix="book-screenshot-") as directory:
      temp = Path(directory)
      native = None
      capture_failed = False
      if args.command != "pdf":
        if sys.platform != "darwin":
          raise ValueError("画面撮影には macOS が必要です。")
        if os.path.lexists(args.folder):
          raise destination_error(args)
        print(f"書籍の撮影を準備しています。保存先は {args.folder} です。", flush=True)
        if args.command == "capture":
          check_accessibility()
          native = native_command(temp, for_capture=True)
          run_native(native, "check-accessibility")
        try:
          args.folder.mkdir(parents=True)
        except FileExistsError as error:
          if not os.path.lexists(args.folder):
            raise
          raise destination_error(args) from error
        (args.folder / "pages").mkdir()
        assertion = "-di" if args.command == "capture" else "-i"
        with subprocess.Popen(["/usr/bin/caffeinate", assertion, "-w", str(os.getpid())]) as awake:
          try:
            if args.command == "chrome":
              capture_chrome(args)
            else:
              capture(args, temp, native)
          except KeyboardInterrupt:
            print("\n撮影を中断しました。撮影済みの画像をPDFにまとめます。", flush=True)
            capture_failed = True
          except (OSError, ValueError, EOFError, subprocess.SubprocessError) as error:
            print(error, file=sys.stderr)
            capture_failed = True
          finally:
            awake.terminate()
        if capture_failed and not any((args.folder / "pages").glob("*.png")):
          return 1
      export_pdfs(args, temp, native)
      return int(capture_failed)
  except (OSError, ValueError, subprocess.SubprocessError) as error:
    print(error, file=sys.stderr)
    return 1


if __name__ == "__main__":
  sys.exit(main())
