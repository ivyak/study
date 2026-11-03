# 家計バックエンド

LIFEの閲覧専用UIと、ローカル専用のDjango REST framework＋SQLiteを接続する。取引の内容はZaimで訂正し、決済対応・分類・立替精算はCodexセッションで確認する。HTTPの書き込みAPIや、外部LLM APIの自動実行は設けない。

## 準備と起動

リポジトリ直下で実行する。PythonとDRFは家計用の仮想環境に置く。

```sh
uv venv --python 3.12 accounting/.venv
uv pip install --python accounting/.venv/bin/python -r accounting/requirements.txt
accounting/.venv/bin/python accounting/backend/manage.py migrate
python3 accounting/run.py
```

LIFEは`http://127.0.0.1:8765/index.html#section=%E5%AE%B6%E8%A8%88`、DRFは127.0.0.1:8766。既存の授業・記事APIはそのまま使い、家計APIだけ同一オリジンの`/api/accounting/`から橋渡しする。起動時に既存index.htmlを再生成しない。

別のサーバーが8765を使用している場合は、そのプロセスを勝手に終了しない。次のように別のポートを指定できる。

```sh
python3 accounting/run.py --port 8768 --backend-port 8769
```

Ctrl+Cで、このコマンドが起動した2つのサーバーを終了する。仮想環境、DB、バックアップ、確認用の生成ファイルはGit管理から除外する。

## 現在の確認方針

CSVの列対応だけを確認省略で確定する。照合・分類・立替精算・開始残高などの判断は、Codexが案と根拠を示し、ユーザーの回答を得てから確定する。

「そのままやって」を取引全体の自動承認と解釈して行った1,876件の記帳は撤回し、記帳前のDBへ復元した。以前の個別承認済み86案は維持する。撤回した状態はバックアップに保存する。DRF・SQLite・CSV取り込み・API・UIの実装は維持する。

照合案の生成だけを行うコマンドは次のとおり。DBの判断状態や帳簿は変更しない。生成したプレビューをreviewコマンドへそのまま適用することもできない。

```sh
accounting/.venv/bin/python accounting/backend/manage.py accounting reconcile 1
```

個別確認を省略して記帳するオプションは撤去した。以後の確定は、ユーザーの回答を含むreviewと、整合性検査・バックアップを伴うpublishで行う。

## CSVを追加した後

CSVを`accounting/csv_raw_data/<サービス名>/`へ置き、Codexに「家計を更新して」と依頼する。LIFEへのアップロードは不要。

```sh
accounting/.venv/bin/python accounting/backend/manage.py accounting ingest
accounting/.venv/bin/python accounting/backend/manage.py accounting status
```

全CSVを検査してから元行をDBに取り込む。未知の列構成、不正な日付・金額、請求合計の不一致があれば、取り込み全体を止め、DBを変更しない。列変換は[列対応表](column_mapping.md)で確認する。取り込み後、次の資料を`accounting/review/generated/batch-<番号>/`へ生成する。

- `mapping_examples.json`：元行の全列と、DBの変換済み列。ファイル名・物理行番号付き。
- `questions.md`：人が読める、全件の質問と根拠。
- `questions.jsonl`：未確認の判断を1行1件で全件出力。件数の上限はない。
- `matching_candidates.json`：同額・近接日の候補、Zaimの連続品目群の合計候補。候補は未確定で、勝手に統合しない。
- `summary.json`：取り込み件数、確認済み・確認待ちの件数。
- `answers.template.json`：セッションの回答・判断を適用するためのひな形。

既存デモは実行せず、保存済みスナップショット・回答履歴から移す。ユーザー確認済みの86案は承認を引き継ぐ。デモの照合案や新規取引は、ユーザーの確認待ちとして保持する。最初の更新が確定するまではLIFEに「DB確認待ち・デモ」と表示し、従来のデモを維持する。新しい更新が確認途中の場合は、前回の確定済みデータを表示する。

## Codexセッションでの確認

質問には必ずCSVのファイル名と1始まりの物理行番号を付ける。金額、店名、品目、対応候補を示し、決められない内容は質問する。決済と重複しないZaim支出は、既定方針に従い現金払いとして扱う。複数レシート・複数送金・立替は多対多の対応と仕訳で表す。再取り込みを照合と混同しない。

回答ファイルの形式：

```json
{
  "batch_id": 1,
  "answers": [
    {
      "decision_id": 100,
      "expected_digest": "questions.jsonlにある値",
      "answer": "このセッションで得た回答、または既に承認された根拠。",
      "reason": "照合・分類・訂正を判断した理由。",
      "proposal": {}
    }
  ],
  "new_plans": []
}
```

`proposal`は質問ファイルの案を基にする。列変換を承認するだけなら省略できる。案が変更されていればダイジェスト検査で適用を拒否する。適用はまとめて検証し、一部だけ保存しない。

確定取引案は次の構造。金額は文字列で渡し、小数の誤差を避ける。`raw_ids`には根拠の元行IDを列挙する。

```json
{
  "operation": "upsert",
  "key": "一度決めたら維持する取引キー",
  "date": "2026-10-01",
  "kind": "expense",
  "title": "スーパーA",
  "amount": "1000",
  "currency": "JPY",
  "raw_ids": [11, 12, 13],
  "entries": [
    {"account": "食費", "account_type": "expense", "debit": "800", "credit": "0"},
    {"account": "日用雑貨", "account_type": "expense", "debit": "200", "credit": "0"},
    {"account": "楽天カード未払金", "account_type": "liability", "debit": "0", "credit": "1000"}
  ],
  "items": [
    {"category": "食費", "name": "食料品", "amount": "800", "receipt_amount": "800", "source_raw_record_id": 12},
    {"category": "日用雑貨", "name": "洗剤", "amount": "200", "receipt_amount": "200", "source_raw_record_id": 13}
  ],
  "sources": [
    {"raw_record_id": 11, "role": "payment", "linked_amount": "1000"},
    {"raw_record_id": 12, "role": "detail", "linked_amount": "800"},
    {"raw_record_id": 13, "role": "detail", "linked_amount": "200"}
  ]
}
```

- `operation: ignore`は`raw_ids`と`reason`を持つ。別案に統合した候補や、計上しない資料を明示的に閉じる用途で、未確認を隠すためには使用しない。
- `operation: delete`は既存取引の`key`と`reason`を持つ。元行・判断履歴は消さず、確定取引の変更前を履歴へ残す。
- 追加の開始残高や、元資料のない承認済み精算は`new_plans`へ`proposal`、`answer`、`reason`を入れる。開始残高は`kind: opening`で、資産・負債と「開始残高調整」の仕訳を作る。確認できた0円の開始残高も登録できる。
- 振替は`kind: transfer`、`items: []`。役割は`transfer_out`・`transfer_in`。支出と収入へ重ねて加えない。
- 返金は負数の支出と逆向きの仕訳。値引きの品目も負数のまま残す。
- レシート総額と自己負担が違い、品目別の自己負担を決めていない場合は、レシート品目を`amount: 0`・`receipt_amount: 原本額`で保持し、別の集計用内訳にカテゴリ別の自己負担額を保存する。勝手な比例配分をしない。

```sh
accounting/.venv/bin/python accounting/backend/manage.py accounting review /path/to/answers.json
accounting/.venv/bin/python accounting/backend/manage.py accounting export 1
accounting/.venv/bin/python accounting/backend/manage.py accounting publish 1
```

すべての判断が確認済みで、元行の対応・非計上理由、カテゴリ、借方・貸方、内訳合計、元行の二重使用に問題がない場合だけ反映する。反映は1つのDBトランザクションで行い、途中でエラーになれば帳簿への変更をすべて戻す。確認中にCSVを訂正した場合は、`abandon <番号>`で今回の案を中止して再取り込みする。元行・回答履歴は消さない。以前承認した判断は、新しい更新の確認根拠として使える。

## 重複監査

10000円以上の現金引き出しは、用途が未確認ならユーザーへ確認する。`accounting cash-withdrawals`で用途の確認状態とCSVの物理行番号を取得する。近い日付の支出や同額入金は候補として扱い、本人の回答で確認する。回答待ちはwithdrawal_reviewに保存し、引き出しの振替記帳を維持する。用途が不明という回答も履歴に残し、確認済みの使途とは区別する。質問資料は[現金引き出しの用途確認](review/現金引き出し_用途確認_20261104.md)。

`accounting/.venv/bin/python accounting/backend/manage.py accounting audit-duplicates`で、全確定取引と既存のレシート対応も読み取り専用で検査する。結果はreview/generated/duplicate-audits/latest.json。全取引IDの検査対象一覧と、原本ファイル・行番号を含む候補を保存する。同額だけで同一支払いとは決めず、複数決済合算、品目単位、ポイント値引き前の購入額、店名・日付の違い、個人間精算も確認する。

Zaim単独の現金記録には、別の決済との重複が残る可能性がある。分類の確認済みは重複なしの保証ではない。既存の照合済み対応も誤対応の可能性があるため再検査する。全件走査でも、記録不足から意味上の重複がないことは証明できない。未回答の候補はduplicate_reviewに保持し、取引詳細の状態・根拠にも表示する。2026年11月4日の確認資料は[重複監査の確認事項](review/重複監査_確認事項_20261104.md)。

## バックアップと復元

確定前にSQLiteのbackup APIで整合した別DBを作る。整合性・外部キーを検査し、成功したコピーだけを`accounting/backups/`へ確定する。直近10個を残し、不完全なコピーは残さない。CLIの書き込みはファイルロックで直列化する。

```sh
accounting/.venv/bin/python accounting/backend/manage.py accounting backup
```

復元前にLIFEとDRFを停止する。復元元のDB構造・整合性を検査し、現在のDBも退避してから置き換える。

```sh
accounting/.venv/bin/python accounting/backend/manage.py accounting restore accounting/backups/対象.sqlite3 --server-stopped
```

バックアップには元行・帳簿・判断履歴・確認途中の案が含まれる。CSVファイル自体、プログラム、仮想環境は含まれない。同じPC内のコピーなので、PC故障への備えにはTime Machineなど別媒体の保存も必要。

## 閲覧API

すべてGETのみ。金額・原資料を含むレスポンスはキャッシュしない。

| パス | 内容 |
|---|---|
| `/api/accounting/status` | 確定済みか、確認待ち更新の有無 |
| `/api/accounting/snapshot` | 確定した取引・内訳・仕訳・月次集計・BS・請求内訳 |
| `/api/accounting/transactions?month=2026-10&kind=expense&category=食費` | 月・種類・カテゴリで検索。limit・offset対応 |
| `/api/accounting/transactions/101` | 取引の詳細・原本行 |
| `/api/accounting/summary?month=2026-10` | 月次収支・カテゴリ内訳。year指定で年次 |
| `/api/accounting/calendar?month=2026-10` | 日次の収入・支出・振替 |
| `/api/accounting/pl?month=2026-10` | 損益集計 |
| `/api/accounting/bs?month=2026-10` | 月末残高と期間内増減。year=2026指定で年末残高と年間増減。不明残高はnull |
| `/api/accounting/journal?month=2026-10` | 確定仕訳 |
| `/api/accounting/categories` | カテゴリ名・色 |
| `/api/accounting/coverage` | CSVの観測期間など |

最初の確定前のsnapshotには取引を返さない。新しい更新が確認途中でも、確定済みの帳簿は前回分を表示する。画面の既存レイアウト・カテゴリフィルター・金額非表示・PLからの絞り込みを維持する。

画面上部の月・年で、ホームの収支・カテゴリ別支出と帳簿の集計単位を切り替える。年間は暦年の1〜12月の収録分を対象にする。BSは月末残高の足し算ではなく、12月31日時点の残高と年間増減を表示する。PLから取引一覧へ進んだ場合も選択した年・月を維持する。カレンダーは月表示。

帳簿は取引・仕訳・決算書の3タブ。決算書内でBS・PL-グラフ・PL-表を選択する。取引は日付・金額のそれぞれ昇順・降順で並べ替えられ、種類・カテゴリの絞り込みと併用できる。右上の最終更新日時は最後に確定したImportBatch.published_at（日本時間）を使用し、画面操作やUIの変更では更新しない。金額を隠す設定はブラウザのlocalStorageに保存する。

ホームの「仕送りによる立替を除く」は表示だけの切り替え。家賃・新幹線代・免許合宿・参考書や教科書・コンタクト代に該当する内訳を、同月の仕送り収入を上限に収入・支出の両方から同額控除し、カテゴリ別支出も合わせて変更する。年表示は月別の控除額を合計し、他月の仕送りと相殺しない。仕送り不足時のカテゴリ別控除は対象支出額の比率で配分する。控除対象は確定内訳のカテゴリと品名で判定し、元の取引・仕訳・BS・PLは変更しない。実際の立替対応が確定したことを意味しない。

## テスト

生協CSVは`csv_raw_data/univ_coop/`に置く。マネー・ポイント履歴と商品購入履歴を原本のまま取り込み、照合候補を別途生成する。既に確認中の更新へ新しいCSVを追加する場合は、既存ファイルを変更せず次を実行する。

```sh
accounting/.venv/bin/python accounting/backend/manage.py accounting ingest --extend-review 1
accounting/.venv/bin/python accounting/backend/manage.py accounting coop-preview 1
```

追加前にバックアップを取得し、以前の承認は維持する。既存ファイルの変更・削除があれば追加を中止する。`coop_preview.json`には、各決済の商品候補、差額、出典行、カードチャージ候補を保存する。ポイント・不明差額・資金元は推測して確定しない。一般の`reconcile`も、生協の未確認行を無視や仮払金の確定案へ変換しない。

```sh
accounting/.venv/bin/python accounting/backend/manage.py test ledger --noinput
accounting/.venv/bin/python accounting/backend/manage.py check
node --check Kyoto_Univ/ui/accounting.js
```

テストには架空CSVと隔離したテストDBを使い、実データのDBを変更しない。実装と全列定義は[DB構造](schema.md)を参照する。
