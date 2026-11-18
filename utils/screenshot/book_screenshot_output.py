"""Keep captures in one directory and append pages without overwriting."""

import fcntl
import os
from threading import Lock


def page_number(path):
  return int(path.stem) if path.stem.isdecimal() else 0


def page_paths(folder):
  return sorted(
    (path for path in folder.glob("*") if path.suffix.lower() == ".png" and path.is_file()),
    key=lambda path: (page_number(path), path.name),
  )


class CaptureOutput:
  def __init__(self, folder):
    self.folder = folder
    self.pages = folder / "pages"
    self.fd = None
    self.first_number = None
    self.lock = Lock()

  def validate(self):
    for path in (self.folder, self.pages):
      if os.path.lexists(path) and not path.is_dir():
        raise ValueError(f"{path} はフォルダとして使えません。撮影先にはフォルダのパスを指定してください。")

  def lock_folder(self):
    descriptor = os.open(self.folder, os.O_RDONLY)
    try:
      fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
      os.close(descriptor)
      raise
    self.fd = descriptor

  def acquire(self, *, create=False):
    self.validate()
    if create:
      self.folder.mkdir(parents=True, exist_ok=True)
    if not self.folder.is_dir():
      raise ValueError(f"撮影先フォルダが見つかりません。 {self.folder}")
    try:
      self.lock_folder()
    except BlockingIOError as error:
      raise ValueError(f"別の撮影またはPDF作成がこのフォルダを使用しています。 {self.folder}") from error

  def save(self, page, offset):
    with self.lock:
      if self.first_number is None:
        if self.fd is None:
          self.acquire(create=True)
        self.pages.mkdir(exist_ok=True)
        self.first_number = max((page_number(path) for path in page_paths(self.pages)), default=0) + 1
      path = self.pages / f"{self.first_number + offset:06d}.png"

    created = False
    try:
      with path.open("xb") as stream:
        created = True
        page.save(stream, format="PNG")
    except BaseException:
      if created:
        path.unlink(missing_ok=True)
      raise
    return path

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    if self.fd is not None:
      os.close(self.fd)
