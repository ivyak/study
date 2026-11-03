"""CSVの同一行を出現数込みで取り込み、原本行と固定IDを保持する。"""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import re


class ImportStore:
  def __init__(self, path):
    self.path = Path(path)
    self.data = json.loads(self.path.read_text()) if self.path.exists() else {'version': 1, 'records': {}, 'files': {}}
    self.records = self.data['records']
    self.lookup = {}
    self.added = 0
    self.existing = 0
    self.added_ids = []
    self.edit_candidates = []

  def ingest(self, file, rows):
    source = file.split('/')[0]
    # カードは請求月が違えば同じ利用日の分割払いでも別の請求行。
    scope = source
    if source in ['Vpass', 'Rakuten_Card']:
      match = re.search(r'20\d{4}', Path(file).stem)
      scope += ':' + (match[0] if match else file)
    counts = Counter()
    ids = []
    for line, row in rows:
      content = json.dumps([scope, row], ensure_ascii=False, separators=(',', ':'))
      fingerprint = hashlib.sha256(content.encode()).hexdigest()
      counts[fingerprint] += 1
      identifier = f'raw-{fingerprint}-{counts[fingerprint]}'
      ref = {'file': file, 'line': line}
      if identifier not in self.records:
        # 同日・同品目の変更らしい行は、重複計上せず確認待ちにする。
        similar = []
        if source == 'zaim' and row and re.fullmatch(r'20\d{2}-\d{2}-\d{2}', row[0]) and len(row) >= 12:
          similar = [r['id'] for r in self.records.values() if r['scope'] == scope
            and len(r['row']) == len(row) and r['row'] != row
            and all(r['row'][i] == row[i] for i in [0, 1, 6, 8])]
        self.records[identifier] = {'id': identifier, 'scope': scope, 'row': row,
          'occurrence': counts[fingerprint], 'sources': [], 'currentSource': ref,
          'possibleEditsOf': similar}
        self.added += 1
        self.added_ids.append(identifier)
      else:
        self.existing += 1
      record = self.records[identifier]
      if ref not in record['sources']:
        record['sources'].append(ref)
      record['currentSource'] = ref
      self.lookup[(file, line)] = identifier
      ids.append(identifier)
    self.data['files'][file] = ids

  def resolve(self, ref):
    identifier = ref.get('recordId')
    if not identifier:
      identifier = self.lookup.get((ref['file'], ref['line']))
    if not identifier:
      identifiers = [r['id'] for r in self.records.values() if {'file': ref['file'], 'line': ref['line']} in r['sources']]
      if len(identifiers) != 1:
        raise ValueError(f'原本参照を一意に特定できません: {ref}')
      identifier = identifiers[0]
    return {**self.records[identifier]['currentSource'], 'recordId': identifier}

  def decision_file(self, path):
    path = Path(path)
    def visit(value):
      if isinstance(value, dict):
        if 'file' in value and 'line' in value:
          return self.resolve(value)
        return {k: visit(v) for k, v in value.items()}
      if isinstance(value, list):
        return [visit(v) for v in value]
      return value
    result = visit(json.loads(path.read_text()))
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return result

  def all_inputs(self, root):
    result = defaultdict(list)
    for record in self.records.values():
      if record.get('inactive'):
        continue
      if record.get('possibleEditsOf') and not record.get('editResolved'):
        self.edit_candidates.append({'recordId': record['id'], 'source': record['currentSource'],
          'possibleEditsOf': record['possibleEditsOf']})
        continue
      ref = record['currentSource']
      result[Path(root) / ref['file']].append((ref['line'], record['row']))
    return {path: sorted(rows) for path, rows in result.items()}

  def save(self):
    self.path.parent.mkdir(parents=True, exist_ok=True)
    self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2)+'\n')
