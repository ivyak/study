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


def chapter_opening(lines):
  if not lines:
    return None

  body_heights = [line.height for line in lines if line.y > 0.38 and len(line.text) >= 4]
  body_height = median(body_heights) if body_heights else 0.019
  title_height = max(0.023, body_height * 1.23)
  upper = [line for line in lines if 0.075 <= line.y <= 0.38]
  first_subsections = [
    (line.y, int(match[1])) for line in lines
    if (match := SECTION.match(line.text)) and match[2] == "1"
  ]
  explicit = []
  for line in upper:
    if line.height < title_height:
      continue
    match = EXPLICIT.match(line.text)
    if match:
      number = int(match[1] or match[2])
      strength = 3 if any(n == number and y > line.y for y, n in first_subsections) else 2
      explicit.append((number, line.text, strength))
      continue
    match = NUMBERED.match(line.text)
    if match and not SECTION.match(line.text):
      number = int(match[1])
      strength = 3 if any(n == number and y > line.y for y, n in first_subsections) else 1
      explicit.append((number, line.text, strength))
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
    number for y, number in first_subsections if first_title.y + 0.09 <= y <= 0.83
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
  strength = 3 if large_numbers and number in subsection_numbers else 2
  return number, f"{number}. {title}", strength


def book_chapters(pages):
  contents = set()
  candidates = []
  for page in sorted(pages, key=lambda item: item["page"]):
    index = page["page"]
    lines = [Line(**{**item, "text": " ".join(item["text"].split())}) for item in page["lines"]]
    lines = [line for line in lines if line.text]
    if is_contents(lines):
      contents.add(index)
    else:
      heading = chapter_opening(lines)
      if heading is not None:
        candidates.append((index, *heading))

  # A sparse page between two contents pages can look like a chapter when read alone.
  candidates = [
    candidate for candidate in candidates
    if not (candidate[0] - 1 in contents and candidate[0] + 1 in contents)
  ]
  if not candidates:
    return []

  # Rank ordered sequences across the whole book so that an early false match does
  # not cause later, consecutive chapter openings to be dropped.
  scores = []
  previous = []
  for current, (_, number, _, strength) in enumerate(candidates):
    best_score = strength + (2 if number == 1 else 0)
    predecessor = None
    for earlier in range(current):
      gap = number - candidates[earlier][1] - 1
      if gap < 0:
        continue
      transition = 2 if gap == 0 else -min(gap, 4)
      score = scores[earlier] + strength + transition
      if score > best_score:
        best_score, predecessor = score, earlier
    scores.append(best_score)
    previous.append(predecessor)

  current = max(range(len(scores)), key=scores.__getitem__)
  chapters = []
  while current is not None:
    page, _, title, _ = candidates[current]
    chapters.append((page, title))
    current = previous[current]
  return list(reversed(chapters))
