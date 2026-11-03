"""照合・分類の参考案を生成する。確認状態の変更・記帳・公開はしない。"""
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal
from datetime import date
from difflib import SequenceMatcher
import re
import unicodedata
from .models import Decision, ImportBatch, RawRecord, Transaction
from .parsers import NAMES
from .plans import category_name, entry, plan_digest
from .services import validate_plan

BANKS = {'Sumitomo_Mitsui_Banking_Corporation', 'THE_KYOTO_SHINKIN_BANK', 'JAPAN_POST_BANK', 'RAKUTEN_BANK_LTD'}
CARDS = {'Vpass', 'Rakuten_Card'}


def norm(value):
  value = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)), value or '')
  return unicodedata.normalize('NFKC', value).upper().replace('カ-ド', 'カード')


def shop_key(value):
  value = norm(value)
  for word in ['VISA国内利用', '/NFC', '利用国CN', '利用国KR', '株式会社', '有限会社', 'ショッピングセンター', '生活協同組合', 'デイリーカナート']:
    value = value.replace(word, '')
  return re.sub(r'[^\wぁ-んァ-ヶ一-龥]', '', value)


def canon(value):
  return category_name({'給与所得': '給与', '通信': '通信・サブスク'}.get(value, value))


def assessment(reason, confidence='high', assumptions=None):
  return {'actor': 'codex', 'confidence': confidence, 'reason': reason, 'assumptions': assumptions or []}


def signed_value(raw, direction=None):
  direction = direction or raw.direction
  return (raw.amount or Decimal(0)) * (1 if direction == 'in' else -1 if direction == 'out' else 0)


def classify(title):
  text = norm(title)
  rules = [
    ('通信・サブスク', r'OPENAI|CHATGPT|GOOGLE|アーティスト|ユーネクスト|AMAZONプライム'),
    ('美容・衣服', r'メンズサロン|MEN.?S.*SALON|サロン.*レイ|リゼクリニック|ユニクロ|ZOZOTOWN|SHEIN'),
    ('交通', r'SUICA|スイカ|METRO|TRANSP|TRANS利用国|HELLOBIKE|鉄道|バス|スマートEX|TRIP.COM|トリップドットコム|アーキエムズ|ア―キエムズ|くるっとパーク'),
    ('教育・教養', r'ブックセンタ|書籍|コボデンシ|資格・検定'),
    ('エンタメ', r'STEAM|MOVIX|映画|劇場|ユニバーサル|UNIVERSAL|USJ|カラオケ|ジャンカラ|展望室|水族館|イベント|アソビュー|SPACE.*MARKET|スペースマーケット'),
    ('食費', r'松屋|マツヤ|松弁|マクドナルド|サイゼリヤ|ラーメン|らーめん|麺|うどん|餃子|王将|なか卯|バーガー|ゼッテリア|レストラン|食堂|ビストロ|モス|サブウエイ|サブウェイ|サフ゛ウエイ|丸亀|キラメキ|コレモ|イズミヤ|フレスコ|ライフ|セブン|7.ELEVEN|ファミリ|フアミリ|ローソン|ロ-ソン|LAWSON|FOOD|SPRING|つけめん|ドーナツ|ビール|鍋|油そば|リンガーハット|自動販売機'),
    ('日用雑貨', r'コーナン|コ-ナン|セリア|ダイソー|ドラッグ|ユタカ|ココカラファイン|ロフト|DCM|家具|カグ|エディオン|ドン・キホーテ'),
  ]
  for category, pattern in rules:
    if re.search(pattern, text):
      return category, assessment('明細の店舗・サービス名によるCodex分類。品目がある場合はZaimを優先。', 'medium')
  return 'その他', assessment('購入・支払いであることは明細に記載。用途の詳細を特定できないため、一般カテゴリ「その他」で記録。', 'assumed', ['品目・用途は特定していない。'])


class Reconciler:
  def __init__(self, batch_id):
    self.batch = ImportBatch.objects.get(pk=batch_id)
    if self.batch.status != 'review':
      raise ValueError('確認中の更新を指定してください。')
    ids = self.batch.occurrences.filter(raw_record__transaction_date__isnull=False).values_list('raw_record_id', flat=True)
    self.raws = list(RawRecord.objects.filter(pk__in=ids).order_by('pk'))
    self.raw_map = {r.pk: r for r in self.raws}
    self.deferred_ids = {r.pk for r in self.raws if r.source == 'univ_coop'}
    self.plans = []
    self.covered = set()
    self.decisions = list(self.batch.decisions.filter(kind='transaction').order_by('pk'))
    self.learned = defaultdict(set)
    self.direction_overrides = {}
    self.balance_chains = {}
    self.balance_checks = []
    self.receipt_matches = 0
    self.cash_receipt_groups = 0

  def direction(self, raw):
    return self.direction_overrides.get(raw.pk, raw.direction)

  def link(self, raw, role='payment'):
    return {'raw_record_id': raw.pk, 'role': role, 'linked_amount': str(raw.amount or 0)}

  def add(self, plan):
    self.plans.append(plan)
    self.covered.update(plan.get('raw_ids', []))
    return plan

  def spend(self, raw, category=None, title=None, account=None, value=None, kind='expense', why=None):
    value = Decimal(str(value if value is not None else raw.amount))
    title = title or raw.store or raw.memo or raw.item_name or '支払い'
    if category is None:
      category, why = classify(title)
    category = canon(category)
    account = account or NAMES[raw.source]
    p = {'operation': 'upsert', 'key': raw.dedupe_key, 'date': str(raw.transaction_date), 'kind': kind,
      'title': title, 'amount': str(value), 'currency': 'JPY', 'raw_ids': [raw.pk],
      'entries': [entry(category, value, 'debit' if kind == 'expense' else 'credit', kind),
        entry(account, value, 'credit' if kind == 'expense' else 'debit')],
      'items': [{'category': category, 'name': raw.item_name or title, 'store': raw.store,
        'subcategory': raw.subcategory_name, 'amount': str(value), 'receipt_amount': None, 'source_raw_record_id': None}],
      'sources': [self.link(raw)], 'assessment': why or assessment('原本に用途・分類が明示された収支。'),
      '_eligible': True, '_store': raw.store or raw.memo, '_direction': 'in' if kind == 'income' else 'out'}
    if raw.source == 'PayPay_Corporation' and kind == 'expense':
      parts = re.findall(r'(PayPayポイント|PayPay残高)\s*\(([\d,]+)円\)', raw.raw_data['values'][9])
      if parts:
        amounts = [(name, Decimal(amount.replace(',', ''))) for name, amount in parts]
        if sum(a for _, a in amounts) != abs(value):
          raise ValueError(f'元行{raw.pk}のPayPay内訳が一致しません。')
        p['entries'] = p['entries'][:1]+[entry(name, amount if value > 0 else -amount, 'credit') for name, amount in amounts]
    return p

  def transfer(self, raw, outgoing, incoming, title, why=None, side=None, eligible=False):
    value = abs(raw.amount or 0)
    side = side or ('in' if self.direction(raw) == 'in' else 'out')
    return {'operation': 'upsert', 'key': raw.dedupe_key, 'date': str(raw.transaction_date), 'kind': 'transfer',
      'title': title, 'amount': str(value), 'currency': 'JPY', 'raw_ids': [raw.pk],
      'entries': [entry(incoming, value, 'debit'), entry(outgoing, value, 'credit')], 'items': [],
      'sources': [self.link(raw, 'transfer_in' if side == 'in' else 'transfer_out')],
      'assessment': why or assessment('明細に記載された口座間の資金移動。'),
      '_outgoing': outgoing, '_incoming': incoming, '_side': side, '_eligible': eligible,
      '_store': raw.store or raw.memo, '_direction': side}

  def suspense(self, raw):
    direction = self.direction(raw)
    account = NAMES[raw.source]
    why = assessment('入出金自体は原本で確認。用途を断定せず、出金は仮払金、入金は仮受金への資金移動として記録。',
      'assumed', ['用途の判明後に仮払金・仮受金を本来の勘定へ振り替える。'])
    return self.transfer(raw, account if direction == 'out' else '仮受金', '仮払金' if direction == 'out' else account,
      '個人間送金・その他出金（仮払金）' if direction == 'out' else '入金（仮受金）', why, eligible=direction == 'out')

  def inspect_balances(self):
    for source in BANKS | {'Super_Urban_Intelligent_Card'}:
      rows = [r for r in self.raws if r.source == source and r.balance is not None]
      if not rows:
        continue
      orders = [rows, list(reversed(rows))]
      ordered = next((rs for rs in orders if all(a.transaction_date <= b.transaction_date for a, b in zip(rs, rs[1:]))), rows)
      if len(ordered) > 1:
        alternate = next((rs for rs in orders if all(a.transaction_date <= b.transaction_date and a.balance+signed_value(b) == b.balance for a, b in zip(rs, rs[1:]))), None)
        if alternate:
          ordered = alternate
      for previous, raw in zip(ordered, ordered[1:]):
        delta = raw.balance-previous.balance
        if previous.transaction_date <= raw.transaction_date and delta == -signed_value(raw) and raw.amount:
          self.direction_overrides[raw.pk] = 'out' if delta < 0 else 'in'
      valid = all(a.transaction_date <= b.transaction_date and a.balance+signed_value(b, self.direction(b)) == b.balance for a, b in zip(ordered, ordered[1:]))
      if valid:
        self.balance_chains[source] = ordered

  def adopt_existing(self):
    for d in self.decisions:
      p = deepcopy(d.proposal)
      if p.get('operation') == 'upsert' and p.get('kind') != 'pending':
        if p.get('kind') == 'transfer':
          incoming = [e['account'] for e in p['entries'] if Decimal(e['debit']) > 0]
          if len(incoming) == 1:
            # 承認済みの片側チャージも開始残高の同日調整に含める。
            p['_incoming'] = incoming[0]
        p['assessment'] = assessment('既存セッションで確認済み。' if d.status == 'confirmed' else
          '既存デモの対応・品目合計・仕訳を検証した参考案。ユーザー確認待ち。',
          'user' if d.status == 'confirmed' else 'medium')
        self.add(p)
        for source in p['sources']:
          raw = self.raw_map.get(source['raw_record_id'])
          if raw and raw.source != 'zaim':
            for item in p.get('items', []):
              if item.get('store'):
                self.learned[shop_key(raw.store or raw.memo)].add(shop_key(item['store']))
    for tx in Transaction.objects.prefetch_related('sources'):
      self.covered.update(s.raw_record_id for s in tx.sources.all())

  def create_financial_plans(self):
    incoming_bank = defaultdict(list)
    explicit_receivers = {}
    for raw in self.raws:
      if raw.source in BANKS and self.direction(raw) == 'in':
        incoming_bank[(raw.transaction_date, abs(raw.amount or 0))].append(raw)
    for raw in self.raws:
      if raw.source not in BANKS or self.direction(raw) != 'out':
        continue
      candidates = [r for r in incoming_bank[(raw.transaction_date, abs(raw.amount or 0))]
        if r.source != raw.source and NAMES[r.source] in norm(raw.memo)]
      if len(candidates) == 1:
        explicit_receivers[raw.pk] = candidates[0]
    reverse_receivers = {value.pk: self.raw_map[key] for key, value in explicit_receivers.items()}
    for raw in self.raws:
      if raw.pk in self.covered or raw.source in {'zaim', 'univ_coop'}:
        continue
      if not raw.amount:
        continue
      text, direction = norm(raw.memo), self.direction(raw)
      value = raw.amount
      if raw.source in CARDS:
        if re.search('SUICA|スイカ', text):
          p = self.transfer(raw, NAMES[raw.source], 'Suica', 'クレジットカードからSuicaへチャージ')
        elif '大学生協電子マネー入金サイト' in text:
          p = self.transfer(raw, NAMES[raw.source], '大学生協電子マネー', '生協電子マネーへチャージ')
        else:
          p = self.spend(raw, value=-value if direction == 'in' else value)
      elif raw.source == 'PayPay_Corporation':
        method = norm(raw.raw_data['values'][9])
        if raw.memo == 'チャージ':
          bank = '三井住友銀行' if '三井住友銀行' in method else '携帯電話料金未払金'
          p = self.transfer(raw, bank, 'PayPay残高', 'PayPayチャージ', side='in')
        elif raw.memo in {'支払い', '返金', '請求書払い'}:
          p = self.spend(raw, value=-value if raw.memo == '返金' else value)
        elif 'ポイント' in method:
          if raw.memo == '期間限定ポイントの期限切れ':
            p = self.spend(raw, category='その他', account='PayPayポイント', title='PayPayポイント失効')
          else:
            p = self.spend(raw, category='ポイント還元', account='PayPayポイント', kind='income',
              value=-value if direction == 'out' else value, title='PayPayポイント還元' if direction == 'in' else 'PayPayポイント還元の取消')
        else:
          p = self.suspense(raw)
      elif raw.source == 'Super_Urban_Intelligent_Card':
        if direction == 'in':
          card = self.suica_card(raw)
          p = self.transfer(raw, card, 'Suica', 'Suicaチャージ', side='in',
            why=assessment('ユーザー指定によりSuicaチャージはクレジットカード。'+('同日同額のカード明細と対応。' if card != 'クレジットカード未払金' else 'カード名は特定せず共通の未払金へ記録。'),
              'high' if card != 'クレジットカード未払金' else 'assumed', [] if card != 'クレジットカード未払金' else ['チャージ元のカード名は未特定。']))
        else:
          transport = '入' == raw.memo or 'バス' in text
          p = self.spend(raw, category='交通' if transport else 'その他', title=(f'{raw.store} → {raw.counterparty_hint}' if raw.memo == '入' else 'Suicaバス利用' if transport else 'Suica物販'),
            why=assessment('Suicaの入出場・バス・物販の種別に基づく分類。', 'high' if transport else 'assumed', [] if transport else ['物販の品目は特定していない。']))
      else:
        account = NAMES[raw.source]
        if raw.pk in explicit_receivers:
          p = self.transfer(raw, account, NAMES[explicit_receivers[raw.pk].source], '銀行間振替')
        elif raw.pk in reverse_receivers:
          p = self.transfer(raw, NAMES[reverse_receivers[raw.pk].source], account, '銀行間振替')
        elif 'PAYPAY' in text or 'ペイペイ' in text:
          p = self.transfer(raw, account, 'PayPay残高', '銀行からPayPayへチャージ') if direction == 'out' else self.transfer(raw, 'PayPay残高', account, 'PayPayから銀行へ出金')
        elif raw.source == 'Sumitomo_Mitsui_Banking_Corporation' and direction == 'out' and re.sub(r'\s+', '', text) == 'NSカ)クエストカン':
          p = self.spend(raw, category='家賃', title='家賃',
            why=assessment('ユーザー指定によりSMBCのNS ｶ)ｸｴｽﾄｶﾝの引き落としは家賃。'))
        elif direction == 'out' and any(t in text for t in ['ミツイスミトモカード', 'ラクテンカード', 'ポケツトカード', 'ポケットカード']):
          card = '三井住友カード未払金' if 'ミツイ' in text else '楽天カード未払金' if 'ラクテン' in text else 'ポケットカード未払金'
          p = self.transfer(raw, account, card, 'カード請求の引き落とし')
        elif '利息' in text or '利子' in text:
          p = self.spend(raw, category='利息', kind='income', value=value if direction == 'in' else -value, title='預金利息')
        elif direction == 'in' and ('給与' in text or '給振' in text or 'デミア' in text):
          p = self.spend(raw, category='給与', kind='income', title='給与入金')
        elif '手数料' in text:
          p = self.spend(raw, category='その他', value=value if direction == 'out' else -value, title='銀行手数料' if direction == 'out' else '銀行手数料の戻入')
        elif direction == 'out' and 'カンサイデンリヨク' in text:
          p = self.spend(raw, category='水道光熱費', title='電力料金')
        elif re.search(r'^カード|^ATM|^通.?帳', text) and 'AMAZON' not in text:
          p = self.transfer(raw, account if direction == 'out' else '現金', '現金' if direction == 'out' else account,
            '現金引き出し' if direction == 'out' else '現金預け入れ', assessment('銀行のカード・通帳・ATM表記を現金の入出金として扱う。', 'medium'))
        elif direction == 'out' and 'AMAZON' in text:
          p = self.spend(raw, title='Amazon利用')
        else:
          p = self.suspense(raw)
      if raw.pk in self.direction_overrides:
        p['assessment'] = assessment(p['assessment']['reason']+' CSVの入出金欄と残高推移が反対のため、金額と連続残高の一致を優先して仕訳の向きを補正。',
          'medium', p['assessment']['assumptions']+['原本の入出金欄に矛盾があり、残高推移から補正した。'])
      self.add(p)

  def suica_card(self, raw):
    cards = {NAMES[r.source] for r in self.raws if r.source in CARDS and r.transaction_date == raw.transaction_date
      and r.amount == raw.amount and re.search('SUICA|スイカ', norm(r.memo))}
    return next(iter(cards)) if len(cards) == 1 else 'クレジットカード未払金'

  def merge_transfers(self):
    # 複数カードと同額の複数チャージは、恣意的な1対1対応を作らず全体で結ぶ。
    suica_days = defaultdict(list)
    for p in self.plans:
      if p.get('_incoming') == 'Suica' and p.get('_side') in {'in', 'out'}:
        suica_days[p['date']].append(p)
    for plans in suica_days.values():
      outgoing = [p for p in plans if p['_side'] == 'out']
      incoming = [p for p in plans if p['_side'] == 'in']
      if not outgoing or not incoming or Counter(p['amount'] for p in outgoing) != Counter(p['amount'] for p in incoming):
        continue
      if not any(p['_outgoing'] == 'クレジットカード未払金' for p in incoming):
        continue
      parts = outgoing+incoming
      first = outgoing[0]
      total = sum((Decimal(p['amount']) for p in outgoing), Decimal(0))
      funding = defaultdict(Decimal)
      for p in outgoing:
        funding[p['_outgoing']] += Decimal(p['amount'])
      first.update(amount=str(total), raw_ids=sorted(rid for p in parts for rid in p['raw_ids']),
        sources=[s for p in parts for s in p['sources']],
        entries=[entry('Suica', total, 'debit')]+[entry(name, value, 'credit') for name, value in funding.items()],
        title=f'Suicaチャージ（{len(outgoing)}回分・複数明細の対応）', _side='both',
        assessment=assessment('同日同額の複数カード明細とSuica入金を、同件数のまとまりとして統合。個々のチャージのカード割当は作らない。'))
      self.plans = [p for p in self.plans if p is first or not any(p is other for other in parts)]
    groups = defaultdict(list)
    for p in self.plans:
      if p.get('_outgoing'):
        groups[(p['date'], p['_outgoing'], p['_incoming'])].append(p)
    removed = set()
    for _, plans in groups.items():
      outgoing = [p for p in plans if p['_side'] == 'out']
      incoming = [p for p in plans if p['_side'] == 'in']
      amounts = set(p['amount'] for p in outgoing) & set(p['amount'] for p in incoming)
      for amount in amounts:
        left = [p for p in outgoing if p['amount'] == amount]
        right = [p for p in incoming if p['amount'] == amount]
        if len(left) != len(right):
          continue
        parts = left+right
        first = left[0]
        total = Decimal(amount)*len(left)
        first.update(amount=str(total), raw_ids=sorted(rid for p in parts for rid in p['raw_ids']),
          sources=[s for p in parts for s in p['sources']], entries=[entry(first['_incoming'], total, 'debit'), entry(first['_outgoing'], total, 'credit')],
          title=first['title']+(f'（{len(left)}回分）' if len(left) > 1 else ''),
          assessment=assessment('同日・同額・同件数で、出金元と入金先の明示が一致する双方の明細を、同じ振替として統合。'))
        removed.update(id(p) for p in parts if p is not first)
    self.plans = [p for p in self.plans if id(p) not in removed]

  def merchant_similarity(self, title, store):
    left, right = shop_key(title), shop_key(store)
    if not left or not right or left == '_' or right == '_':
      return 0
    if right in self.learned.get(left, set()):
      return 1
    if min(len(left), len(right)) >= 3 and (left in right or right in left):
      return .9
    return SequenceMatcher(None, left, right).ratio()

  def receipt_candidates(self, group):
    total = sum((r.amount for r in group), Decimal(0))
    kind = 'income' if group[0].direction == 'in' else 'expense'
    candidates = []
    for p in self.plans:
      if not p.get('_eligible') or p.get('_matched') or p.get('_direction') != ('in' if kind == 'income' else 'out'):
        continue
      delta = abs((group[0].transaction_date-date.fromisoformat(p['date'])).days)
      if delta > 3 or Decimal(p['amount']) != total:
        continue
      similarity = self.merchant_similarity(p.get('_store', ''), group[0].store)
      score = similarity*4+(1 if delta == 0 else .1/(delta+1))
      if delta and similarity < .45:
        continue
      candidates.append((score, similarity, p))
    return sorted(candidates, key=lambda c: (-c[0], c[2]['key']))

  def attach_receipt(self, p, group, kind, confidence, reason):
    total = sum((r.amount for r in group), Decimal(0))
    totals = defaultdict(Decimal)
    for r in group:
      totals[canon(r.category_name or ('給与' if kind == 'income' else 'その他'))] += r.amount
    # 資金元は既存決済の仕訳を維持する。個人間送金の仮払金は品目判明により費用へ振替。
    payments = [e for e in p['entries'] if e['account_type'] in {'asset', 'liability'} and e['account'] not in {'仮払金', '仮受金'} and (Decimal(e['debit']) or Decimal(e['credit']))]
    if p['kind'] == 'transfer':
      side = 'credit' if kind == 'expense' else 'debit'
      payments = [e for e in p['entries'] if Decimal(e[side]) and e['account'] not in {'仮払金', '仮受金'}]
    p['entries'] = [entry(name, amount, 'debit' if kind == 'expense' else 'credit', kind) for name, amount in totals.items() if amount]+payments
    if not total:
      p['entries'] = [entry(canon(r.category_name or 'その他'), r.amount, 'debit' if kind == 'expense' else 'credit', kind) for r in group if r.amount]
    p.update(kind=kind, amount=str(total), title=group[0].store if group[0].store not in {'', '-'} else group[0].item_name or ('収入' if kind == 'income' else p['title']),
      items=[{'category': canon(r.category_name or ('給与' if kind == 'income' else 'その他')),
        'name': r.item_name or ('収入' if kind == 'income' else '支払い'), 'store': r.store, 'subcategory': r.subcategory_name,
        'amount': str(r.amount), 'receipt_amount': str(r.amount), 'source_raw_record_id': r.pk} for r in group],
      assessment=assessment(reason, confidence, ['同日同額の一意候補から対応付けた。店舗名の裏付けは弱い。'] if confidence == 'assumed' else []), _matched=True)
    for r in group:
      p['raw_ids'].append(r.pk)
      p['sources'].append(self.link(r, 'detail'))
      self.covered.add(r.pk)

  def match_receipts(self):
    groups = []
    for r in self.raws:
      if r.source != 'zaim' or r.pk in self.covered:
        continue
      k = (r.transaction_date, r.store, r.direction)
      if not groups or groups[-1][0] != k:
        groups.append((k, []))
      groups[-1][1].append(r)
    # 店名の裏付けの強い群を先に対応させ、同額候補の取り違えを減らす。
    groups.sort(key=lambda pair: -(self.receipt_candidates(pair[1])[0][1] if self.receipt_candidates(pair[1]) else 0))
    for _, group in groups:
      total = sum((r.amount for r in group), Decimal(0))
      if not total and not any(r.amount for r in group):
        continue
      candidates = self.receipt_candidates(group)
      kind = 'income' if group[0].direction == 'in' else 'expense'
      selected = None
      if candidates:
        best = candidates[0]
        gap = best[0]-candidates[1][0] if len(candidates) > 1 else 10
        if (best[1] >= .4 and gap >= .15) or (len(candidates) == 1 and best[0] >= 1):
          selected = best
      if selected:
        score, similarity, p = selected
        self.attach_receipt(p, group, kind, 'high' if similarity >= .65 else 'medium' if similarity >= .4 else 'assumed',
          'Zaimの連続する同日・同店・同方法の品目合計と決済金額が一致。日付と店舗名または一意性を根拠にCodexが対応付け。')
        self.receipt_matches += 1
      else:
        # 決済と結び付かないZaim支出はユーザー指定により現金扱い。
        raw = group[0]
        p = self.spend(raw, category=canon(raw.category_name or ('給与' if kind == 'income' else 'その他')),
          title=raw.store if raw.store not in {'', '-'} else raw.item_name or ('収入' if kind == 'income' else '現金支出'),
          account='現金', value=total, kind=kind)
        p['raw_ids'], p['sources'] = [], []
        self.attach_receipt(p, group, kind, 'medium' if not candidates else 'assumed',
          '決済明細との確実な対応がないZaim記録。ユーザーの既定方針に従い現金で計上。'+('同額候補はあるが複数または店舗不一致のため対応を断定していない。' if candidates else ''))
        if not total:
          p['assessment'] = assessment('Zaimの正負の品目が合計0円。図書カード・親負担など原本の相殺記録を保持し、自己負担0円として計上。')
        if candidates:
          p['assessment']['assumptions'].append('別明細との重複の可能性があり、現金扱いを暫定採用。')
        self.add(p)
        self.cash_receipt_groups += 1

  def add_openings(self):
    for source, ordered in self.balance_chains.items():
      if any(p.get('key') == 'opening:'+source for p in self.plans):
        continue
      first = ordered[0]
      opening = first.balance-signed_value(first, self.direction(first))
      adjustment = Decimal(0)
      if source == 'Super_Urban_Intelligent_Card' and not first.amount:
        for p in self.plans:
          if p['date'] != str(first.transaction_date) or p.get('_incoming') != 'Suica':
            continue
          if not any(self.raw_map[rid].source == source for rid in p['raw_ids']):
            adjustment += Decimal(p['amount'])
        opening -= adjustment
      name = NAMES[source]
      entries = [entry(name, abs(opening), 'debit' if opening >= 0 else 'credit'),
        entry('開始残高調整', abs(opening), 'credit' if opening >= 0 else 'debit')]
      raw_ids, sources = [], []
      if not first.amount and first.pk not in self.covered:
        raw_ids, sources = [first.pk], [self.link(first)]
      self.add({'operation': 'upsert', 'key': 'opening:'+source, 'date': str(first.transaction_date),
        'kind': 'opening', 'title': name+'の収録開始残高', 'amount': str(abs(opening)), 'currency': 'JPY',
        'raw_ids': raw_ids, 'sources': sources, 'items': [], 'entries': entries,
        'assessment': assessment('CSVの最初の取引後残高から、その取引の増減を差し引いた開始残高。収録期間の連続残高を全件検算。'+
          (f' 最初の残高表示に含まれる同日カードチャージ{adjustment}円も差し引き、二重計上を防止。' if adjustment else ''),
          'medium' if adjustment else 'high', ['開始日の残高表示を同日カードチャージ後の残高として扱う。'] if adjustment else [])})

  def build(self):
    self.inspect_balances()
    self.adopt_existing()
    self.create_financial_plans()
    self.merge_transfers()
    self.match_receipts()
    self.add_openings()
    clean = []
    for p in self.plans:
      p = {key: value for key, value in p.items() if not key.startswith('_')}
      validate_plan(p)
      clean.append(p)
    for source, ordered in self.balance_chains.items():
      name, start, end = NAMES[source], str(ordered[0].transaction_date), str(ordered[-1].transaction_date)
      actual = sum((Decimal(e['debit'])-Decimal(e['credit']) for p in clean if start <= p['date'] <= end
        for e in p['entries'] if e['account'] == name), Decimal(0))
      if actual != ordered[-1].balance:
        raise ValueError(f'{name}の記帳後残高がCSVの最終残高と一致しません。')
      self.balance_checks.append({'account': name, 'date': end, 'csv_balance': str(ordered[-1].balance), 'ledger_balance': str(actual)})
    assigned = set()
    documents = []
    new_plans = []
    by_key = {d.proposal.get('key'): d for d in self.decisions}
    for plan in clean:
      d = by_key.get(plan['key'])
      why = plan['assessment']['reason']
      if d and d.pk not in assigned:
        documents.append({'decision_id': d.pk, 'expected_digest': plan_digest(d.proposal), 'proposal': plan,
          'reason': why})
        assigned.add(d.pk)
      else:
        new_plans.append({'proposal': plan, 'reason': why})
    for d in self.decisions:
      if d.pk in assigned:
        continue
      ids = d.proposal.get('raw_ids', [])
      if set(ids) & self.deferred_ids:
        documents.append({'decision_id': d.pk, 'expected_digest': plan_digest(d.proposal),
          'proposal': d.proposal, 'reason': '生協CSVの照合候補はcoop_preview.jsonを参照。未確認のポイント・差額・資金元は確定しない。'})
        continue
      reason = '他の確定取引の対応元行として統合。重複して収支計上しない。' if set(ids) <= self.covered else '金額0の表示・残高情報。資金移動として重ねて計上しない。'
      uncovered = [rid for rid in ids if rid not in self.covered and self.raw_map[rid].amount]
      if uncovered:
        raise ValueError(f'元行の処理が不足しています: {uncovered}')
      documents.append({'decision_id': d.pk, 'expected_digest': plan_digest(d.proposal),
        'proposal': {'operation': 'ignore', 'raw_ids': ids, 'reason': reason}, 'reason': reason})
    for d in self.batch.decisions.filter(kind='mapping').exclude(status='confirmed'):
      documents.append({'decision_id': d.pk, 'expected_digest': plan_digest(d.proposal),
        'reason': '列対応はユーザー指示により確認省略の対象。'})
    return {'batch_id': self.batch.pk, 'preview_only': True, 'proposals': documents, 'new_proposals': new_plans,
      'reconciliation_summary': {'transactions': len(clean), 'receipt_groups_matched': self.receipt_matches,
        'cash_receipt_groups': self.cash_receipt_groups,
        'confidence': dict(Counter(p['assessment']['confidence'] for p in clean)),
        'direction_corrections': sorted(self.direction_overrides), 'opening_accounts': sorted(self.balance_chains),
        'deferred_coop_records': len(self.deferred_ids),
        'balance_checks': self.balance_checks}}
