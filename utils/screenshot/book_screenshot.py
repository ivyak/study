"""Capture a macOS book viewer and export chapter PDFs."""

import argparse
from collections import Counter
from hashlib import blake2b
import os
from pathlib import Path
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

import img2pdf
from PIL import Image


POLL_INTERVAL = 0.5
TIMEOUT = 60
NATIVE_SOURCE = Path(__file__).with_name("book_screenshot_macos.swift")


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


def wait_for_page(read_page, previous, stable_seconds, deadline):
  candidate = None
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
    time.sleep(min(POLL_INTERVAL, max(0, deadline - time.monotonic())))
  return None


def native_command(temp):
  binary = temp / "book_screenshot_macos"
  subprocess.run(
    ["swiftc", "-module-cache-path", str(temp / "swift-cache"), str(NATIVE_SOURCE), "-o", str(binary)],
    check=True,
  )
  return binary


def capture(args, temp, native):
  print(f"{args.delay} 秒後に撮影を始めます。書籍の最初のページを表示してください。", flush=True)
  time.sleep(args.delay)
  pid = subprocess.check_output([native, "front"], text=True).strip()
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
      raise ValueError("画面を撮影できませんでした。画面収録の設定を確認してください。") from error
    with Image.open(frame) as image:
      return image.convert("RGB")

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
      raise ValueError("撮影中に画面の解像度が変わったため停止しました。")
    return crop(current)

  previous = None
  number = 1
  deadline = time.monotonic() + TIMEOUT
  while True:
    result = wait_for_page(read_page, previous, args.stable, deadline)
    if result is None:
      print(f"{TIMEOUT} 秒以内に新しいページを確認できなかったため停止しました。", flush=True)
      return
    page, previous = result
    if subprocess.check_output([native, "front"], text=True).strip() != pid:
      raise ValueError("撮影開始時と異なるアプリが前面にあるため停止しました。")
    path = args.folder / "pages" / f"{number:06d}.png"
    pending = path.with_suffix(".tmp")
    page.save(pending, format="PNG")
    pending.replace(path)
    print(f"{number} 枚目を保存しました。", flush=True)
    if number == args.max_pages:
      return
    number += 1
    subprocess.run([native, "right", pid], check=True, timeout=5)
    deadline = time.monotonic() + TIMEOUT


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
    try:
      with pending.open("wb") as stream:
        img2pdf.convert([str(page) for page in pages[start - 1:stop - 1]], outputstream=stream)
      pending.replace(path)
    except img2pdf.ImageOpenError as error:
      raise ValueError(f"{start}〜{stop - 1} 枚目のどれかを開けませんでした。 {error}") from error
    finally:
      pending.unlink(missing_ok=True)
    print(f"{start}〜{stop - 1} 枚目を保存しました。 {path}", flush=True)


def positive_integer(value):
  number = int(value)
  if number < 1:
    raise argparse.ArgumentTypeError("1 以上を指定してください。")
  return number


def main():
  parser = argparse.ArgumentParser(description="macOSで書籍ビューアを撮影し、章ごとにPDFにまとめます。")
  commands = parser.add_subparsers(dest="command", required=True)
  capture_parser = commands.add_parser("capture", help="撮影してPDFにまとめる")
  pdf_parser = commands.add_parser("pdf", help="撮影済みの画像からPDFを作る")
  for command in (capture_parser, pdf_parser):
    command.add_argument("folder", type=Path, help="撮影フォルダ")
    command.add_argument("--chapter", action="append", type=chapter_spec, help="12:第1章 の形式で指定。複数指定可")
  capture_parser.add_argument("--crop", nargs=4, type=int, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
  capture_parser.add_argument("--delay", type=positive_integer, default=10, help="撮影開始までの秒数")
  capture_parser.add_argument("--stable", type=positive_integer, default=2, help="ページが静止したとみなすまでの秒数")
  capture_parser.add_argument("--max-pages", type=positive_integer, help="撮影する枚数の上限")
  args = parser.parse_args()
  numbers = [index for index, _ in args.chapter or []]
  if len(numbers) != len(set(numbers)):
    parser.error("同じ開始番号を複数の章に指定できません。")
  if args.command == "capture" and args.stable >= TIMEOUT:
    parser.error(f"--stable は {TIMEOUT} 秒未満にしてください。")

  try:
    with TemporaryDirectory(prefix="book-screenshot-") as directory:
      temp = Path(directory)
      native = None
      capture_failed = False
      if args.command == "capture":
        if sys.platform != "darwin":
          raise ValueError("画面撮影には macOS が必要です。")
        if args.folder.exists():
          raise ValueError(f"撮影先には新しいフォルダを指定してください。 {args.folder}")
        native = native_command(temp)
        args.folder.mkdir(parents=True)
        (args.folder / "pages").mkdir()
        with subprocess.Popen(["/usr/bin/caffeinate", "-di", "-w", str(os.getpid())]) as awake:
          try:
            capture(args, temp, native)
          except KeyboardInterrupt:
            print("\n撮影を中断しました。撮影済みの画像をPDFにまとめます。", flush=True)
            capture_failed = True
          except (OSError, ValueError, subprocess.SubprocessError) as error:
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
