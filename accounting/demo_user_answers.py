"""セッションで得た回答を、原本を変更せずデモへ適用する。"""
import json
from pathlib import Path


def apply_answers(transactions, evidence, store):
  history = []
  review_dir = Path(__file__).with_name('review')
  anchors_path = review_dir / 'answer_anchors.json'
  if anchors_path.exists():
    anchors = json.loads(anchors_path.read_text())
  else:
    migration = json.loads((review_dir / 'zaim_source_migration.json').read_text())
    anchors = {str(old): [store.resolve({'file': migration['newFile'], 'line': migration['lineMap'][str(old)]})['recordId']]
      for old in [1588, 1608]}
    anchors['held'] = [store.resolve({'file': migration['newFile'], 'line': line})['recordId'] for line in [1598,1599]]
    anchors_path.write_text(json.dumps(anchors, ensure_ascii=False, indent=2)+'\n')

  def select(day, value, memo=None, account=None):
    rows = [r for r in transactions if r['date'] == day and r['amount'] == value
      and (memo is None or memo in r['memo']) and (account is None or r['account'] == account)]
    assert len(rows) == 1, (day, value, memo, len(rows))
    return rows[0]

  def update(row, answer, **values):
    before = dict(row)
    row.update(values, status='ユーザー確認済み')
    history.append({'answer': answer, 'sources': row['sources'], 'before': before, 'after': dict(row)})

  def create(day, kind, value, account, memo, category='振替', to=''):
    row = {'id': f'answer-{len(history)+1}', 'date': day, 'kind': kind, 'amount': value,
      'account': account, 'to': to, 'category': category, 'memo': memo,
      'sources': [], 'splits': [], 'status': 'ユーザー確認済み'}
    transactions.append(row)
    history.append({'answer': 'セッション回答による補完', 'sources': [], 'before': None, 'after': dict(row)})
    return row

  def attach(row, start, end, legacy=False):
    identifiers = [identifier for i in range(start,end+1) for identifier in anchors[str(i)]] if legacy else None
    items = [z for z in evidence if z['source']['recordId'] in identifiers] if legacy else [z for z in evidence if start <= z['source']['line'] <= end]
    assert items and sum(z['amount'] for z in items) == row['amount']
    assert all(not z.get('matchedTransactionId') for z in items)
    for z in items:
      z['matchedTransactionId'] = row['id']
    row['zaimItems'] = [dict(z) for z in items]
    row['zaimMatch'] = {'status': 'ユーザー確認済み', 'reason': 'セッションで精算方法を確認。', 'store': items[0]['store']}
    row['sources'] += [z['source'] for z in items]
    row['categoryAmounts'] = [{'category': row['category'], 'amount': row['amount']}]

  # B1〜B4。ただし質問された里山食堂は回答が確定するまで変更しない。
  for row in transactions:
    if row['kind'] == 'pending' and row['account'] == 'PayPayポイント':
      update(row, 'B1', kind='income', category='ポイント還元', memo='PayPayポイント還元')
    elif row['kind'] == 'expense' and row['category'] == '未分類':
      if any(term in row['memo'] for term in ['自動販売機', '松弁ネット', '麺や虎鉄', 'ファミリーマート', 'ローソン', 'ﾛ-ｿﾝ']):
        update(row, 'B2〜B4', category='食費')

  overrides = [
    ('2026-09-17', 1090, '洛北阪急', '食費', '濃厚魚介つけ汁／丸亀製麺 洛北阪急スクエア'),
    ('2026-09-17', 29740, '旅行センタ', '旅行費', '京都大学生協 時計台旅行センター'),
    ('2026-09-20', 2000, 'Ａｎｃｈｏｒ', '食費', 'Anchor1889'),
    ('2026-10-02', 2970, 'ｷｮｳﾄ', '書籍・教材費', 'ゼミナール コーポレートファイナンス'),
    ('2026-10-16', 7808, 'ミスターマックス', 'エンタメ', '【SW2】ゼルダの伝説 時のオカリナ<MrMax早期購入オリジナル特典付>'),
    ('2026-09-01', 1080, '個人宛', '食費', '太平燕／紅蘭亭 下通本店'),
    ('2026-09-03', 1500, '個人宛', '食費', 'お酒代の割り勘'),
    ('2026-09-03', 1030, '個人宛', '食費', '煮玉子入りらーめん／博多らーめんShinShin アミュプラザ小倉店'),
  ]
  for day, value, memo, category, description in overrides:
    update(select(day, value, memo), 'C1〜C5・D1・D3・D4', kind='expense', category=category, memo=description)
  update(select('2026-09-03', 386, account='楽天銀行'), 'D2', kind='transfer',
    account='立替金', to='楽天銀行', category='振替', memo='立替金の回収')

  # A2：2人分の支払いを自分の食費と立替金へ分け、回収を別に記録する。
  row = select('2026-10-14', 1960, '状元楼')
  update(row, 'A2', amount=980, category='食費', memo='エビチリセット／状元楼（自分の負担分）')
  attach(row, 1588, 1588, legacy=True)
  create('2026-10-14', 'transfer', 980, 'PayPay残高', '状元楼・友人分の立替', to='立替金')
  update(select('2026-10-14', 980, '受取'), 'A2・D18', kind='transfer', account='立替金',
    to='PayPay残高', category='振替', memo='状元楼・立替金の回収')

  # A3：映画の友人分1500円を、夕食1250円と現金250円で精算する。
  row = select('2026-10-23', 3000, '塚口')
  update(row, 'A3', amount=1500, category='エンタメ', memo='バックルームズ（字幕版）／塚口サンサン劇場（自分の負担分）')
  attach(row, 1608, 1608, legacy=True)
  create('2026-10-23', 'transfer', 1500, '三井住友カード未払金', '映画代・友人分の立替', to='立替金')
  create('2026-10-23', 'expense', 1250, '立替金', 'ラーメン＋セカンドインパクト／ラーメン荘 歴史を刻め 大阪日本橋店', category='食費')
  create('2026-10-23', 'transfer', 250, '立替金', '映画代と夕食代の差額を現金で回収', to='現金')

  # 追加CSVに書かれた用途を、既存決済・確認済みの精算へ補完する。
  for link in store.decision_file(review_dir / 'zaim_additional_links.json'):
    candidates = [r for r in transactions if r['date'] == link['date'] and r['amount'] == link['amount']
      and (link['paymentSource'] in r['sources'] if link['paymentSource'] else r['memo'] == link['generatedMemo'])]
    assert len(candidates) == 1, link
    row = candidates[0]
    items = [z for z in evidence if z['source'] in link['sources']]
    assert len(items) == len(link['sources'])
    update(row, '追加Zaim CSVによる用途の補完', kind='expense', category=items[0]['category'],
      memo=items[0]['store'] if items[0]['store'] != '-' else items[0]['item'])
    attach(row, min(z['source']['line'] for z in items), max(z['source']['line'] for z in items))

  # 10/9：現金1500円の会計のうち自己負担900円、600円は立替回収。
  items = [z for z in evidence if z['source']['recordId'] in anchors['held']]
  assert len(items) == 2 and sum(z['amount'] for z in items) == 1500
  row = create('2026-10-09', 'expense', 1500, '現金', 'サイゼリヤ 百万遍店（自己負担分）', category='食費')
  attach(row, min(z['source']['line'] for z in items), max(z['source']['line'] for z in items))
  update(row, 'ユーザー確認：1500円支払い、600円回収、旧900円行は削除',
    amount=900, receiptTotal=1500, advanceAmount=600, categoryAmounts=[{'category':'食費','amount':900}])
  create('2026-10-09', 'transfer', 600, '現金', 'サイゼリヤ・友人分の立替', to='立替金')
  update(select('2026-10-09', 600, '受取'), 'ユーザー確認：サイゼリヤ精算', kind='transfer',
    account='立替金', to='PayPay残高', category='振替', memo='サイゼリヤ・立替金600円を回収')

  # 10/17：2食分1190+1150円を送金1690+650円のまとまりへ対応付ける。
  first = select('2026-10-17', 1690, '個人宛')
  second = select('2026-10-17', 650, '個人宛')
  update(first, 'ユーザー確認：2食分と2送金は同じ精算', kind='expense', amount=2340,
    category='食費', memo='びっくりドンキー＋地球規模で考えろ（2食分の精算）', sources=first['sources']+second['sources'])
  transactions.remove(second)
  items = [z for z in evidence if z['date']=='2026-10-17' and z['store'] in ['びっくりドンキー 河原町三条店','ラーメン荘 地球規模で考えろ サン']]
  assert len(items)==2 and sum(z['amount'] for z in items)==2340
  attach(first, min(z['source']['line'] for z in items), max(z['source']['line'] for z in items))

  for value in [500,200]:
    update(select('2026-10-31', value, account='Suica'), 'ユーザー確認：Suicaチャージはクレジットカード',
      kind='transfer', account='クレジットカード未払金', to='Suica', category='振替',
      memo='クレジットカードからSuicaへチャージ（カード名は確認待ち）')

  # 同額が複数あるチャージは恣意的に1対1にせず、まとまりとして確定する。
  duplicate_groups = {}
  for row in transactions:
    if row.get('excludeFromBalances'):
      duplicate_groups.setdefault(tuple(sorted(row['duplicateCandidateIds'])), []).append(row)
  removed = set()
  for ids, duplicates in duplicate_groups.items():
    originals = [r for r in transactions if r['id'] in ids]
    total = sum(r['amount'] for r in originals)
    assert total == sum(r['amount'] for r in duplicates)
    first = originals[0]
    sources = [ref for r in originals + duplicates for ref in r['sources']]
    update(first, 'ユーザー承認：同じ複数回のチャージとしてまとめる', amount=total,
      sources=sources, memo=f'チャージ{len(originals)}回分（双方の明細を対応付け）')
    removed.update(r['id'] for r in originals[1:] + duplicates)
  transactions[:] = [r for r in transactions if r['id'] not in removed]

  # 決済に結び付かなかったZaimは、ユーザー指定の現金払いとする。
  remaining = [z for z in evidence if not z.get('matchedTransactionId') and z['source']['recordId'] not in anchors['held']]
  groups = []
  for z in remaining:
    if not groups or (groups[-1][0]['date'], groups[-1][0]['store']) != (z['date'], z['store']):
      groups.append([])
    groups[-1].append(z)
  for items in groups:
    row = create(items[0]['date'], 'expense', sum(z['amount'] for z in items), '現金',
      items[0]['store'] if items[0]['store'] != '-' else items[0]['item'], category=items[0]['category'])
    attach(row, items[0]['source']['line'], items[-1]['source']['line'])

  Path(__file__).with_name('review').mkdir(exist_ok=True)
  Path(__file__).with_name('review').joinpath('applied_answers.json').write_text(
    json.dumps({'date': '2026-11-03', 'waiting': '未解決の送金・入金8件とSuicaのカード名は確認待ち。',
      'history': history}, ensure_ascii=False, indent=2)+'\n')
