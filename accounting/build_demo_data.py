#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""実CSVを読み、9〜10月のUI試作用スナップショットだけを再生成する。"""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata
from collections import Counter, defaultdict
from demo_user_answers import apply_answers
from demo_import_store import ImportStore

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'accounting' / 'csv_raw_data'
OUTPUT = ROOT / 'Kyoto_Univ' / 'ui' / 'accounting-data.js'
START, END = '2026-09-01', '2026-10-31'
CARDS = {'Vpass': '三井住友カード未払金', 'Rakuten_Card': '楽天カード未払金'}


def normalize(value):
  return unicodedata.normalize('NFKC', value).strip()


def amount(value):
  return int(normalize(value).replace(',', '').replace('円', '').replace('¥', '').replace('\\', '') or '0')


def date(value):
  match = re.fullmatch(r'(20\d{2})[/-]?(\d{1,2})[/-]?(\d{1,2})', value.strip())
  return '-'.join([match[1], match[2].zfill(2), match[3].zfill(2)]) if match else None


def reference(path, line):
  return IMPORT_STORE.resolve({'file': path.relative_to(RAW).as_posix(), 'line': line})


def classification(memo):
  name = normalize(memo).upper()
  rules = [
    ('交通費', r'SUICA|スイカ|バス|鉄道|METRO'),
    ('通信・サブスク', r'OPENAI|CHATGPT|GOOGLE|ユーネクスト|AMAZONプライム|アーティスト・サイト'),
    ('美容', r'メンズサロン|MENS.*SALON|MEN’S.*SALON|ﾒﾝｽﾞ|リゼクリニック'),
    ('食費', r'マツヤ|松屋|なか卯|マクドナルド|サブウェイ|ゼッテリア|キラメキ|サイゼリヤ|バーガーキング|コレモ|イズミヤ.*シヨクヒン|ビストロ|モスバーガー|丸亀製麺'),
    ('衣服', r'ユニクロ|ZOZOTOWN'),
    ('娯楽費', r'劇場|MOVIX|ユニバーサル|展望室'),
    ('日用雑貨', r'セリア|コーナン|ドラッグ|ココカラファイン'),
  ]
  for category, pattern in rules:
    if re.search(pattern, name):
      return category, '店名による試作分類。品目との対応は未確認。'
  return '未分類', '店名のみでは用途を確定できないため未分類。'


def build():
  global IMPORT_STORE
  IMPORT_STORE = ImportStore(ROOT / 'accounting' / 'demo_store' / 'raw_records.json')
  inputs, inventory, hashes = {}, [], {}
  for path in sorted(RAW.rglob('*.csv')):
    raw = path.read_bytes()
    hashes[path] = hashlib.sha256(raw).hexdigest()
    try:
      text, encoding = raw.decode('utf-8-sig'), 'utf-8-sig'
    except UnicodeDecodeError:
      text, encoding = raw.decode('cp932'), 'cp932'
    reader = csv.reader(io.StringIO(text, newline=''))
    rows = []
    while True:
      line = reader.line_num + 1
      try:
        row = next(reader)
      except StopIteration:
        break
      rows.append((line, row))
    IMPORT_STORE.ingest(path.relative_to(RAW).as_posix(), rows)
    inputs[path] = rows
    inventory.append({'file': path.relative_to(RAW).as_posix(), 'encoding': encoding,
      'rows': len(rows), 'physicalLines': len(text.splitlines())})
  inputs = IMPORT_STORE.all_inputs(RAW)
  transactions, bills, evidence = [], [], []
  source_dates = defaultdict(list)

  def add(day, kind, value, account, memo, refs, to='', category='未分類', status='確認済み', **extra):
    record = {'id': f'tx-{len(transactions)+1:04d}', 'date': day, 'kind': kind,
      'amount': value, 'account': account, 'to': to, 'category': category,
      'memo': memo, 'sources': refs, 'status': status, 'splits': [], **extra}
    if value and START <= day <= END:
      transactions.append(record)
      return record
    return None

  # 請求月と利用日を分ける。カード名義などのヘッダーは出力しない。
  for path, rows in inputs.items():
    family = path.parent.name
    if family not in CARDS:
      continue
    billing_digits = re.search(r'20\d{4}', path.stem)[0]
    billing_month = billing_digits[:4]+'-'+billing_digits[4:]
    bill = {'id': f'{family}-{billing_digits}', 'account': CARDS[family],
      'billingMonth': billing_month, 'total': 0, 'sources': [], 'items': [],
      'paymentTransactionIds': [], 'totalBasis': '明細金額の合計'}
    printed_total = None
    for line, row in rows:
      day = date(row[0]) if row else None
      if not day:
        if family == 'Vpass' and len(row) == 7 and not any(row[:5]) and row[5]:
          printed_total = amount(row[5])
          bill['sources'].append(reference(path, line))
        continue
      source_dates[family].append(day)
      ref = reference(path, line)
      memo = row[1].strip()
      if family == 'Vpass':
        modern = len(row) >= 10
        use_amount = amount(row[6] if modern else row[2])
        billed_amount = amount((row[7] if re.fullmatch(r'-?[\d,]+',row[7]) else row[6]) if modern else row[5])
      else:
        use_amount = amount(row[4])
        header = rows[0][1]
        billed_column = header.index('当月請求額') if '当月請求額' in header else 7
        billed_amount = amount(row[billed_column])
      bill['items'].append({'date': day, 'memo': memo, 'amount': billed_amount, 'sources': [ref]})
      bill['sources'].append(ref)
      if not START <= day <= END:
        continue
      if re.search(r'SUICA|スイカ', normalize(memo).upper()):
        record = add(day, 'transfer', use_amount, CARDS[family], 'Suicaチャージ', [ref], to='Suica', category='振替', billId=bill['id'])
      elif '大学生協電子マネー入金サイト' in normalize(memo):
        record = add(day, 'transfer', use_amount, CARDS[family], '大学生協電子マネーチャージ', [ref], to='大学生協電子マネー', category='振替', billId=bill['id'])
      else:
        category, basis = classification(memo)
        record = add(day, 'expense', use_amount, CARDS[family], memo, [ref], category=category,
          categoryBasis=basis, billId=bill['id'], refundOriginalStatus='未確認' if use_amount < 0 else None)
    bill['total'] = sum(item['amount'] for item in bill['items'])
    if printed_total is not None:
      assert bill['total'] == printed_total, f'請求合計不一致: {bill["id"]}'
      bill['totalBasis'] = 'CSV末尾の請求合計と明細合計の一致'
    if billing_month in ['2026-09', '2026-10', '2026-11']:
      bills.append(bill)

  bank_charges, bank_card_payments, bank_incoming, bank_outgoing = [], [], [], []
  for path, rows in inputs.items():
    family = path.parent.name
    if family not in ['Sumitomo_Mitsui_Banking_Corporation', 'RAKUTEN_BANK_LTD']:
      continue
    account = '三井住友銀行' if family.startswith('Sumitomo') else '楽天銀行'
    for line, row in rows:
      day = date(row[0]) if row else None
      if not day:
        continue
      source_dates[family].append(day)
      if not START <= day <= END:
        continue
      value = amount(row[2])-amount(row[1]) if account == '三井住友銀行' else amount(row[1])
      description = normalize(row[3]).replace('カ-ド','カード')
      refs = [reference(path,line)]
      if account == '三井住友銀行' and description == 'PAYPAY':
        record = add(day,'pending',abs(value),account,'PayPayチャージとの照合待ち',refs,status='未確認',direction='out')
        bank_charges.append(record)
      elif 'ミツイスミトモカード' in description or 'ラクテンカード' in description:
        card = CARDS['Vpass'] if 'ミツイ' in description else CARDS['Rakuten_Card']
        record = add(day,'transfer',-value,account,'カード請求の引き落とし',refs,to=card,category='振替')
        bank_card_payments.append(record)
      elif value > 0 and '利息' in description:
        add(day,'income',value,account,'預金利息',refs,category='利息')
      elif value > 0 and description.startswith('給与'):
        add(day,'income',value,account,'給与入金',refs,category='給与')
      elif value < 0 and 'カンサイデンリヨク' in description:
        add(day,'expense',-value,account,'電力料金',refs,category='水道光熱費',categoryBasis='銀行摘要の電力会社名。')
      else:
        record = add(day,'pending',abs(value),account,'用途未確認の入金' if value > 0 else '用途未確認の出金',refs,status='未確認',direction='in' if value > 0 else 'out')
        if value > 0:
          bank_incoming.append(record)
        else:
          bank_outgoing.append((record,description))

  # 送金先銀行の明示と同日同額の一意一致がある銀行間振替だけを統合する。
  removed = set()
  for outgoing, description in bank_outgoing:
    candidates = [r for r in bank_incoming if r['date'] == outgoing['date'] and r['amount'] == outgoing['amount']
      and r['account'] != outgoing['account'] and r['account'] in description]
    reverse = [r for r,desc in bank_outgoing if (r['date'],r['amount'],r['account']) == (outgoing['date'],outgoing['amount'],outgoing['account'])]
    if len(candidates) == len(reverse) == 1 and candidates[0]['id'] not in removed:
      incoming = candidates[0]
      outgoing.update(kind='transfer',to=incoming['account'],category='振替',memo='銀行間振替',status='確認済み',sources=outgoing['sources']+incoming['sources'])
      removed.add(incoming['id'])

  paypay_charges = []
  for path, rows in inputs.items():
    if path.parent.name != 'PayPay_Corporation':
      continue
    for line, row in rows:
      day = date(row[0].split(' ')[0]) if row else None
      if not day:
        continue
      source_dates['PayPay_Corporation'].append(day)
      if not START <= day <= END:
        continue
      out = amount(row[1]) if row[1] != '-' else 0
      inc = amount(row[2]) if row[2] != '-' else 0
      action, method, memo = row[7], normalize(row[9]), row[8]
      refs = [reference(path,line)]
      if action == 'チャージ' and '三井住友銀行' in method:
        record = add(day,'transfer',inc,'三井住友銀行','銀行からPayPayへチャージ',refs,to='PayPay残高',category='振替')
        paypay_charges.append(record)
      elif action in ['支払い','返金']:
        category, basis = classification(memo)
        record = add(day,'expense',out or -inc,'PayPay残高',memo,refs,category=category,categoryBasis=basis,
          refundOriginalStatus='未確認' if action == '返金' else None)
        parts = re.findall(r'(PayPayポイント|PayPay残高) \(([\d,]+)円\)',method)
        if parts:
          record['splits'] = [{'account': name, 'amount': amount(value)} for name,value in parts]
          assert sum(part['amount'] for part in record['splits']) == record['amount']
      else:
        points = 'ポイント' in method
        add(day,'pending',out or inc,'PayPayポイント' if points else 'PayPay残高',
          'ポイント獲得（収益区分未確認）' if points else '個人宛送金（用途未確認）' if out else '受取（用途未確認）',refs,
          status='未確認',direction='out' if out else 'in')
  for bank in bank_charges:
    candidates = [r for r in paypay_charges if (r['date'],r['amount']) == (bank['date'],bank['amount'])]
    reverse = [r for r in bank_charges if (r['date'],r['amount']) == (bank['date'],bank['amount'])]
    if len(candidates) == len(reverse) == 1:
      candidates[0]['sources'] += bank['sources']
      removed.add(bank['id'])
    elif candidates:
      bank.update(memo='PayPayチャージの重複候補（集計除外）',status='重複候補・集計除外',
        duplicateCandidateIds=[r['id'] for r in candidates],excludeFromBalances=True)

  card_suica = [r for r in transactions if r['kind'] == 'transfer' and r['to'] == 'Suica']
  suica_incoming = []
  for path, rows in inputs.items():
    if path.parent.name != 'Super_Urban_Intelligent_Card':
      continue
    year = None
    for line,row in rows:
      if row and re.fullmatch(r'# (\d{4})年',row[0]):
        year = int(row[0][2:6])
      match = re.fullmatch(r'(\d{1,2})月(\d{1,2})日',row[0]) if row else None
      if not match or not year:
        continue
      day = f'{year}-{int(match[1]):02d}-{int(match[2]):02d}'
      source_dates['Super_Urban_Intelligent_Card'].append(day)
      if not START <= day <= END or not row[6]:
        continue
      value = amount(row[6]); refs = [reference(path,line)]
      if value > 0:
        suica_incoming.append(add(day,'pending',value,'Suica','Suica入金（決済元未確認）',refs,status='未確認',direction='in'))
      else:
        memo = normalize(row[2])+' → '+normalize(row[4]) if row[1] == '入' else '路線バス' if 'バス' in normalize(row[1]) else 'Suica利用'
        add(day,'expense',-value,'Suica',memo,refs,category='交通費',categoryBasis='Suica原本の入出場・バス種別。')
  for incoming in suica_incoming:
    candidates = [r for r in card_suica if (r['date'],r['amount']) == (incoming['date'],incoming['amount'])]
    reverse = [r for r in suica_incoming if (r['date'],r['amount']) == (incoming['date'],incoming['amount'])]
    if len(candidates) == len(reverse) == 1:
      candidates[0]['sources'] += incoming['sources']
      removed.add(incoming['id'])
    elif candidates:
      incoming.update(memo='Suica入金の重複候補（カード明細との対応保留・集計除外）',status='重複候補・集計除外',
        duplicateCandidateIds=[r['id'] for r in candidates],excludeFromBalances=True)

  transactions = [r for r in transactions if r['id'] not in removed]
  for payment in bank_card_payments:
    candidates = [b for b in bills if b['account'] == payment['to'] and b['billingMonth'] == payment['date'][:7] and b['total'] == payment['amount']]
    if len(candidates) == 1:
      bill = candidates[0]
      bill['paymentTransactionIds'].append(payment['id'])
      payment['billId'] = bill['id']
      payment['memo'] = f'{bill["billingMonth"]}請求分の引き落とし'
    else:
      payment['status'] = '請求内訳未対応'

  for path,rows in inputs.items():
    if path.parent.name != 'zaim':
      continue
    for line,row in rows:
      day = date(row[0]) if row else None
      if not day:
        continue
      source_dates['zaim'].append(day)
      if START <= day <= END:
        evidence.append({'date':day,'category':row[2],'detail':row[3],'item':row[6],
          'store':row[8],'amount':amount(row[11]),'income':amount(row[10]),'method':row[1],
          'status':'支払元・決済対応未確認','source':reference(path,line)})

  # 候補の計算と照合判断を分離し、セッションで検討した対応を再利用する。
  links = IMPORT_STORE.decision_file(ROOT / 'accounting' / 'zaim_demo_links.json')
  used_evidence = set()
  ref_key = lambda ref: (ref['file'], ref['line'])
  for link in links:
    matches = [r for r in transactions if link['paymentSource'] in r['sources']]
    assert len(matches) == 1, '決済元の対応が一意ではない'
    record = matches[0]
    items = [z for z in evidence if z['source'] in link['zaimSources']]
    assert len(items) == len(link['zaimSources']) and items
    assert all(z['date'] == record['date'] and z['method'] == 'payment' for z in items)
    assert sum(z['amount'] for z in items) == record['amount']
    assert not record.get('zaimItems'), '同じ決済への複数レシート対応は要確認'
    for item in items:
      key = ref_key(item['source'])
      assert key not in used_evidence, 'Zaimの同じ行を二重使用している'
      used_evidence.add(key)
      item['matchedTransactionId'] = record['id']
    record['zaimItems'] = [dict(z) for z in items]
    record['zaimMatch'] = {'status':link['status'], 'reason':link['reason'], 'store':items[0]['store']}
    record['sources'] += [z['source'] for z in items]
    category_amounts = defaultdict(int)
    for item in items:
      category_amounts[item['category']] += item['amount']
    record['categoryAmounts'] = [{'category':name,'amount':value} for name,value in category_amounts.items() if value]
    record['category'] = ' / '.join(category_amounts)
    record['categoryBasis'] = 'Zaim品目内訳。' + link['reason']

  apply_answers(transactions, evidence, IMPORT_STORE)
  id_map = {}
  for row in transactions:
    identifiers = [row['sources'][0]['recordId']] if row['sources'] else []
    identity = identifiers or ['manual', row['date'], row['kind'], row['account'], row['to'], row['memo']]
    identifier = 'tx-' + hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:24]
    id_map[row['id']] = identifier
    row['id'] = identifier
  history_path = ROOT / 'accounting' / 'review' / 'applied_answers.json'
  def stable_history(value):
    if isinstance(value, str):
      return id_map.get(value, value)
    if isinstance(value, dict):
      return {key: stable_history(item) for key,item in value.items()}
    if isinstance(value, list):
      return [stable_history(item) for item in value]
    return value
  history = stable_history(json.loads(history_path.read_text()))
  history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2)+'\n')
  audit_path = ROOT / 'accounting' / 'demo_store' / 'decision_history.json'
  audit_path.parent.mkdir(exist_ok=True)
  audit = json.loads(audit_path.read_text()) if audit_path.exists() else []
  digest = hashlib.sha256(json.dumps(history, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
  if not any(entry['digest'] == digest for entry in audit):
    audit.append({'digest': digest, 'snapshot': history})
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
  for item in evidence:
    if item.get('matchedTransactionId'):
      item['matchedTransactionId'] = id_map[item['matchedTransactionId']]
  for row in transactions:
    for item in row.get('zaimItems', []):
      item['matchedTransactionId'] = row['id']
  for bill in bills:
    bill['paymentTransactionIds'] = [id_map[key] for key in bill['paymentTransactionIds']]
  transactions.sort(key=lambda r:(r['date'],r['id']))
  evidence.sort(key=lambda r:(r['date'],r['source']['line']))
  coverage = {'complete':False,'openingBalancesKnown':False,'scope':'原本に存在する2026年9〜10月の行のみ。完全な2か月分の家計ではない。',
    'sources':[{'source':name,'observedStart':min(days),'observedEnd':max(days),
      'selectedTransactions':sum(any(ref['file'].startswith(name+'/') for ref in r['sources']) for r in transactions)} for name,days in sorted(source_dates.items())],
    'evidenceByMonth':dict(Counter(r['date'][:7] for r in evidence)),
    'limitations':['各銀行を含め、提供CSVに存在する原本行のみ収録。取得範囲外の取引は補完しない。',
      '京都信用金庫・ゆうちょのCSVはデモの帳簿変換へ未統合。現金の開始残高と生協電子マネー利用明細は未設定。',
      'Vpass202611は請求合計の印字がないため、金額列の合計を利用する。',
      '同日同額の複数候補は統合せず、候補元を保持し重複側の残高変動を除外する。',
      'Zaimの照合判断はzaim_demo_links.jsonに保存。確認済み以外はデモ照合案であり、未対応行を別支出として計上しない。']}
  result = {'start':START,'end':END,'transactions':transactions,'evidence':evidence,
    'bills':bills,'coverage':coverage,'inputFiles':inventory,
    'importSummary':{'addedRawRows':IMPORT_STORE.added,'existingRawRows':IMPORT_STORE.existing,'editCandidates':IMPORT_STORE.edit_candidates}}
  ids = {r['id'] for r in transactions}
  assert len(ids) == len(transactions)
  for row in transactions:
    assert START <= row['date'] <= END and isinstance(row['amount'],int) and row['amount']
    for ref in row['sources']:
      assert any(line == ref['line'] for line,_ in inputs[RAW/ref['file']])
  for bill in bills:
    assert bill['total'] == sum(item['amount'] for item in bill['items'])
    assert all(identifier in ids for identifier in bill['paymentTransactionIds'])
  assert all(hashlib.sha256(path.read_bytes()).hexdigest() == original for path,original in hashes.items())
  IMPORT_STORE.save()
  (ROOT / 'accounting' / 'demo_store' / 'last_import.json').write_text(json.dumps({
    'addedRecordIds': IMPORT_STORE.added_ids, 'existingRows': IMPORT_STORE.existing,
    'editCandidates': IMPORT_STORE.edit_candidates}, ensure_ascii=False, indent=2)+'\n')
  OUTPUT.write_text('/* Generated by accounting/build_demo_data.py. Memory-only UI snapshot. */\nwindow.LifeAccountingData = '+json.dumps(result,ensure_ascii=False,indent=2).replace('<','\\u003c')+';\n',encoding='utf-8')
  for month in ['2026-09','2026-10']:
    selected = [r for r in transactions if r['date'].startswith(month)]
    print(month, 'transactions',len(selected),'income',sum(r['amount'] for r in selected if r['kind'] == 'income'),
      'expense',sum(r['amount'] for r in selected if r['kind'] == 'expense'),'Zaim',sum(r['date'].startswith(month) for r in evidence))
  print('Raw import: added', IMPORT_STORE.added, 'existing', IMPORT_STORE.existing)
  print('Bills:',[(b['id'],b['total'],len(b['items']),len(b['paymentTransactionIds'])) for b in bills])
  print('Input CSV files:',len(inventory),'All raw CSV hashes unchanged.')


if __name__ == '__main__':
  build()
