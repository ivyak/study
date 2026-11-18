"""Capture a macOS book viewer and export chapter PDFs."""

import argparse
from base64 import b64decode
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import ctypes
from hashlib import blake2b
from io import BytesIO
import json
import os
from pathlib import Path
from shlex import join as shell_join
import shutil
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Lock
import time

import img2pdf
from PIL import Image
import pikepdf

from book_screenshot_chapters import book_chapters
from book_screenshot_chrome import ChromeConnection


POLL_INTERVAL = 0.5
TIMEOUT = 60
WAIT_PROGRESS_INTERVAL = 5
NATIVE_SOURCE = Path(__file__).with_name("book_screenshot_macos.swift")


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


def wait_for_page(read_page, previous, stable_seconds, deadline, number, report):
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
      report(f"{number} 枚目の表示を待っています。{elapsed} 秒経過、上限 {TIMEOUT} 秒。")
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
  print("章の自動判定では、PNGの紙面全体の文字と位置を読み取るために使います。", flush=True)
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

  yield from capture_pages(args, read_screen, right, check_front)


def list_chrome_tabs(tabs):
  if not tabs:
    raise ValueError("Chromeに撮影できるタブがありません。")
  windows = {}
  for tab in tabs:
    windows.setdefault(tab.get("windowId"), []).append(tab)

  choices = []
  window_ids = sorted(windows, key=lambda window_id: (window_id is None, window_id))
  for number, window_id in enumerate(window_ids, 1):
    heading = f"ウィンドウ {number}" if window_id is not None else "ウィンドウが確認できなかったタブ"
    print(f"\n{heading}")
    for tab in windows[window_id]:
      choices.append(tab)
      title = " ".join(tab["title"].splitlines()).strip() or "タイトルなし"
      print(f'  {len(choices):2}  {title}\n      {tab["url"]}')
  return choices


def select_chrome_tab(tabs):
  choices = list_chrome_tabs(tabs)
  answer = input("\n撮影するタブの番号を入力してください。 ")
  if not answer.isdecimal() or not 1 <= int(answer) <= len(choices):
    raise ValueError("一覧にあるタブの番号を指定してください。")
  return choices[int(answer) - 1]


def capture_chrome_tab(chrome, args, tab, *, label="", prepare=None, stop=None):
  session = chrome.request("attach", target=tab["targetId"])
  print(f'{label}撮影を開始します。 {tab["title"]}', flush=True)

  def request(operation, **params):
    if stop is not None and stop.is_set():
      raise InterruptedError("撮影を中断しました。")
    return chrome.request(operation, sessionId=session, **params)

  def read_screen(deadline):
    remaining = int((deadline - time.monotonic()) * 1000)
    if remaining <= 0:
      return None
    image_data = request("screenshot", timeout=min(remaining, 5000))
    if image_data is None:
      return None
    with Image.open(BytesIO(b64decode(image_data))) as image:
      return image.convert("RGB")

  try:
    yield from capture_pages(args, read_screen, lambda: request("right"), label=label, prepare=prepare)
  finally:
    try:
      chrome.request("detach", sessionId=session)
    except ValueError:
      pass


def capture_chrome(args):
  with ChromeConnection(args.debug_port) as chrome:
    tabs = chrome.request("tabs", groupByWindow=not args.tab)
    if args.tab:
      matches = [tab for tab in tabs if tab["url"] == args.tab]
      if len(matches) != 1:
        raise ValueError("--tab とURLが一致するタブを1つ開いてください。")
      selected = matches[0]
    else:
      selected = select_chrome_tab(tabs)
    yield from capture_chrome_tab(chrome, args, selected)


def select_chrome_ranges(tabs, args):
  choices = list_chrome_tabs(tabs)
  print(f"本のページ順に {args.parallel} 個のタブ番号をカンマで入力してください。", flush=True)
  answer = input("枚数を個別に指定する例  3:25, 7:25, 9:17\nタブ番号と撮影枚数  ")
  specifications = [item.strip() for item in answer.split(",")]
  if len(specifications) != args.parallel:
    raise ValueError(f"異なるタブを {args.parallel} 個指定してください。")
  jobs = []
  used = set()
  for specification in specifications:
    index, separator, limit = specification.partition(":")
    index, limit = index.strip(), limit.strip()
    if not index.isdecimal() or not 1 <= int(index) <= len(choices) or int(index) in used:
      raise ValueError("一覧にある異なるタブ番号を指定してください。")
    count = args.max_pages
    if separator:
      count = int(limit) if limit.isdecimal() else None
    if not count:
      raise ValueError("各タブの撮影枚数を指定するか、--max-pages を指定してください。")
    used.add(int(index))
    jobs.append((choices[int(index) - 1], count))
  return jobs


def capture_chrome_batch(args, temp):
  stop = Event()
  output_lock = Lock()
  output_created = False
  with ChromeConnection(args.debug_port) as chrome:
    jobs = select_chrome_ranges(chrome.request("tabs", groupByWindow=True), args)

    def prepare():
      nonlocal output_created
      with output_lock:
        if not output_created:
          create_capture_folder(args)
          output_created = True

    def take_part(index, tab, expected):
      label = f"[区間 {index}] "
      part = argparse.Namespace(**vars(args))
      part.folder = args.folder / f"part-{index:02d}"
      part.max_pages = expected
      paths = []
      try:
        for path in capture_chrome_tab(chrome, part, tab, label=label, prepare=prepare, stop=stop):
          paths.append(path)
      except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"{label}{error}", file=sys.stderr, flush=True)
      print(f"{label}{len(paths)}/{expected} 枚を保存しました。", flush=True)
      return paths

    with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
      futures = [executor.submit(take_part, index, tab, count) for index, (tab, count) in enumerate(jobs, 1)]
      try:
        for future in as_completed(futures):
          future.result()
      except KeyboardInterrupt:
        print("\n並列撮影を中断しています。", flush=True)
        stop.set()
        for future in futures:
          future.cancel()
      parts = [future.result() if not future.cancelled() else [] for future in futures]

  if not any(parts):
    return 1
  if any(len(paths) != count for paths, (_, count) in zip(parts, jobs)):
    print("指定した枚数に届かなかった区間があります。撮影済みのPNGは各 part フォルダに保存しました。", flush=True)
    print("ページの抜けを避けるため、全区間を連結するPDFの作成を中止しました。", flush=True)
    return 1

  with TemporaryDirectory(dir=args.folder) as staging:
    pending = Path(staging) / "pages"
    pending.mkdir()
    for number, path in enumerate((path for part in parts for path in part), 1):
      combined = pending / f"{number:06d}.png"
      try:
        os.link(path, combined)
      except OSError:
        shutil.copyfile(path, combined)
    pending.rename(args.folder / "pages")
  export_pdf(args, temp)
  return 0


def capture_pages(args, read_screen, right, check_target=None, *, label="", prepare=None):
  def report(message):
    print(label + message, flush=True)

  report("撮影範囲を確認しています。")
  deadline = time.monotonic() + TIMEOUT
  while True:
    screen = read_screen(deadline)
    if screen is not None:
      break
    if time.monotonic() >= deadline:
      raise ValueError("画面を取得できませんでした。")
    time.sleep(min(POLL_INTERVAL, max(0, deadline - time.monotonic())))
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
      report("1 枚目の表示が安定するのを待っています。")
    result = wait_for_page(read_page, previous, args.stable, deadline, number, report)
    if result is None:
      report(f"{TIMEOUT} 秒以内に新しいページを確認できなかったため停止しました。")
      return
    page, previous = result
    if check_target is not None:
      check_target()
    if number == 1:
      if prepare is not None:
        prepare()
      create_capture_folder(args)
      (args.folder / "pages").mkdir()

    path = args.folder / "pages" / f"{number:06d}.png"
    pending = path.with_suffix(".tmp")
    page.save(pending, format="PNG")
    pending.replace(path)
    yield path
    report(f"{number} 枚目を保存しました。")
    if number == args.max_pages:
      report(f"指定された {number} 枚の撮影が完了しました。")
      return
    number += 1
    right()
    deadline = time.monotonic() + TIMEOUT
    report(f"右矢印キーを送りました。{number} 枚目の表示を待っています。")


def chapter_spec(value):
  start, colon, title = value.partition(":")
  title = title.strip()
  if not colon or not start.isdecimal() or int(start) < 1 or not title:
    raise argparse.ArgumentTypeError("章は 12:第1章 のように、撮影順の番号と章名を指定してください。")
  if any(ord(char) < 32 for char in title):
    raise argparse.ArgumentTypeError("章名には制御文字を使えません。")
  return int(start), title


def find_chapters(native, pages_dir, page_count):
  print("全ページの紙面を文字認識しています。", flush=True)
  output = subprocess.check_output([native, "chapters", pages_dir], text=True)
  pages = [json.loads(line) for line in output.splitlines()]
  if len(pages) != page_count:
    print(f"文字認識を利用できた画像は {len(pages)}/{page_count} 枚です。", file=sys.stderr, flush=True)
  print("全ページの読み取りが終わりました。目次の続きと章の並びを確認しています。", flush=True)
  chapters = book_chapters(pages)
  for page, title in chapters:
    print(f"{page} 枚目を章の開始として認識しました。{title}", flush=True)
  return chapters


def export_pdf(args, temp, native=None):
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
      starts = find_chapters(native or native_command(temp), pages_dir, len(pages))
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
      print(f"章の読み取りが中断されました。 {error}", file=sys.stderr)
      starts = []
  if not starts:
    print("章の区切りが見つかりませんでした。撮影した画像はすべてPDFに入ります。", flush=True)
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

  path = output / "全ページ.pdf"
  print(f"{len(pages)} 枚を1つのPDFにまとめ、{len(starts)} 件のしおりを付けます。", flush=True)
  with TemporaryDirectory(dir=output) as staging:
    temporary_pdf = Path(staging) / path.name
    try:
      with (Path(staging) / "images.pdf").open("w+b") as stream:
        img2pdf.convert([str(page) for page in pages], outputstream=stream)
        stream.seek(0)
        with pikepdf.open(stream) as document:
          if starts:
            with document.open_outline() as outline:
              outline.root.extend(pikepdf.OutlineItem(title, start - 1) for start, title in starts)
            document.Root.PageMode = pikepdf.Name.UseOutlines
          document.save(temporary_pdf)
    except img2pdf.ImageOpenError as error:
      raise ValueError(f"撮影画像を開けませんでした。 {error}") from error
    except pikepdf.PdfError as error:
      raise ValueError(f"PDFのしおりを書き込めませんでした。 {error}") from error
    temporary_pdf.replace(path)
  print(f"PDFの作成が完了しました。保存先は {path} です。", flush=True)


def positive_integer(value):
  number = int(value)
  if number < 1:
    raise argparse.ArgumentTypeError("1 以上を指定してください。")
  return number


def create_capture_folder(args):
  try:
    args.folder.mkdir(parents=True)
  except FileExistsError as error:
    if not os.path.lexists(args.folder):
      raise
    raise destination_error(args) from error


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
    "まだ存在しない保存先を指定してください。フォルダは最初のPNGを保存するときに作成します。\n"
    f"実行例\n  {example}"
  )


def main():
  parser = argparse.ArgumentParser(description="macOSで書籍ビューアを撮影し、章のしおり付きPDFにまとめます。")
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
  chrome_parser.add_argument("--parallel", type=positive_integer, default=1, help="同時に撮影するChromeのタブ数")
  chrome_parser.add_argument("--tab", help="撮影するタブのURL。省略時は一覧から選ぶ")
  chrome_parser.add_argument("--debug-port", type=positive_integer, help="明示的に起動したChromeのローカルデバッグポート")
  args = parser.parse_args()
  numbers = [index for index, _ in args.chapter or []]
  if len(numbers) != len(set(numbers)):
    parser.error("同じ開始番号を複数の章に指定できません。")
  if args.command != "pdf" and args.stable >= TIMEOUT:
    parser.error(f"--stable は {TIMEOUT} 秒未満にしてください。")
  if args.command == "chrome" and args.parallel > 1 and args.tab:
    parser.error("--parallel で複数タブを選ぶ場合は --tab を省略してください。")
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
        captured = False
        assertion = "-di" if args.command == "capture" else "-i"
        with subprocess.Popen(["/usr/bin/caffeinate", assertion, "-w", str(os.getpid())]) as awake:
          try:
            if args.command == "chrome" and args.parallel > 1:
              return capture_chrome_batch(args, temp)
            capture_session = capture_chrome(args) if args.command == "chrome" else capture(args, temp, native)
            for _ in capture_session:
              captured = True
          except KeyboardInterrupt:
            print("\n撮影を中断しました。", flush=True)
            capture_failed = True
          except (OSError, ValueError, EOFError, subprocess.SubprocessError) as error:
            print(error, file=sys.stderr)
            capture_failed = True
          finally:
            awake.terminate()
        if not captured:
          return 1
      export_pdf(args, temp, native)
      return int(capture_failed)
  except (OSError, ValueError, subprocess.SubprocessError) as error:
    print(error, file=sys.stderr)
    return 1


if __name__ == "__main__":
  sys.exit(main())
