"""Identify chapter openings from the text and layout of scanned pages."""

from dataclasses import dataclass
import re
from statistics import median


SECTION = re.compile(r"^([1-9][0-9]?)\s*\.\s*([1-9][0-9]*)(?=[^0-9]|$)")
EXPLICIT = re.compile(r"^(?:第\s*([1-9][0-9]?)\s*章|chapter\s+([1-9][0-9]?)\b)", re.I)
NUMBERED = re.compile(r"^([1-9][0-9]?)\s*\.\s*(?=\S)")
LEADERS = re.compile(r"(?:[.·・…‥]\s*){3,}")
FOLIO = re.compile(r"[0-9]{1,4}")


@dataclass(frozen=True)
class Line:
  text: str
  x: float
  y: float
  width: float
  height: float

  @property
  def center_x(self):
    return self.x + self.width / 2

  @property
  def center_y(self):
    return self.y + self.height / 2


def is_contents(lines):
  for line in lines:
    label = re.sub(r"\s+", "", line.text).casefold()
    if line.y < 0.30 and label in {"目次", "contents", "tableofcontents"}:
      return True
    if line.y < 0.12 and label == "目" and any(
      other.text.strip() == "次" and abs(line.center_y - other.center_y) < 0.02
      for other in lines
    ):
      return True

  numbered_sections = [line for line in lines if SECTION.match(line.text)]
  leaders = sum(bool(LEADERS.search(line.text)) for line in lines)
  aligned_folios = sum(
    line.y > 0.075 and line.x + line.width > 0.80
    and bool(FOLIO.fullmatch(line.text))
    and any(other.x < line.x - 0.12 and abs(line.center_y - other.center_y) < 0.012 for other in lines)
    for line in lines
  )
  return leaders >= 4 or (len(numbered_sections) >= 3 and aligned_folios >= 4)


def chapter_opening(raw_lines):
  lines = [Line(**{**item, "text": " ".join(item["text"].split())}) for item in raw_lines]
  lines = [line for line in lines if line.text]
  if not lines or is_contents(lines):
    return None

  body_heights = [line.height for line in lines if line.y > 0.38 and len(line.text) >= 4]
  body_height = median(body_heights) if body_heights else 0.019
  title_height = max(0.023, body_height * 1.23)
  upper = [line for line in lines if 0.075 <= line.y <= 0.38]
  explicit = []
  for line in upper:
    if line.height < title_height:
      continue
    match = EXPLICIT.match(line.text)
    if match:
      explicit.append((int(match[1] or match[2]), line.text))
      continue
    match = NUMBERED.match(line.text)
    if match and not SECTION.match(line.text):
      explicit.append((int(match[1]), line.text))
  if explicit:
    return explicit[0] if len(explicit) == 1 else None

  # Some chapter openings print the number and title separately, and the number can
  # be part of a decoration that OCR misses. The first subsection supplies the number.
  if any(line.y < 0.075 and line.width > 0.070 for line in lines):
    return None
  titles = [
    line for line in upper
    if line.y >= 0.16 and 0.24 <= line.center_x <= 0.76
    and line.height >= title_height and line.width < 0.62
    and not SECTION.match(line.text) and any(char.isalpha() for char in line.text)
  ]
  if not titles:
    return None
  first_title = min(titles, key=lambda line: line.y)
  if any(line.width >= 0.55 and 0.075 <= line.y < first_title.y - 0.015 for line in lines):
    return None
  titles = [line for line in titles if line.y - first_title.y <= 0.06]
  titles.sort(key=lambda line: (round((line.center_y - first_title.center_y) / 0.018), line.x))
  large_numbers = [
    int(line.text) for line in upper
    if line.y < first_title.y and line.height >= max(0.035, body_height * 1.75)
    and FOLIO.fullmatch(line.text) and 1 <= int(line.text) <= 99
  ]
  subsection_numbers = {
    int(match[1]) for line in lines
    if first_title.y + 0.09 <= line.y <= 0.83 and (match := SECTION.match(line.text)) and match[2] == "1"
  }
  numbers = set(large_numbers) or subsection_numbers
  if len(numbers) != 1 or (large_numbers and subsection_numbers and numbers.isdisjoint(subsection_numbers)):
    return None
  number = numbers.pop()
  title = ""
  for line in titles:
    if title and title[-1].isascii() and line.text[0].isascii():
      title += " "
    title += line.text
  return number, f"{number}. {title}"
