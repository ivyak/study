# 教材データ

実例は `apps/recall-quiz/decks/calc2-lesson01.json`。JSONのインデントはスペース2つ。

| フィールド | 内容 |
|---|---|
| `schemaVersion` | 1。アプリのデータ形式。 |
| `id` | 英小文字・数字・ハイフンによる固定のデッキID。 |
| `version` | 1以上の整数。教材更新で増加させる。 |
| `title`、`subtitle`、`scope` | 科目名、授業回、今回の出題範囲と未対象範囲。 |
| `sourceManifest` | 原資料ごとのリポジトリ相対パス `file`、`sha256`、`pageCount`、照合済みの `reviewedPages`、照合方法 `method`。 |
| `questions` | 次の問題オブジェクトの配列。 |

問題は `id`、`version`、`prompt`、`answer`、`criterion`、`explanation`、`sources` を持つ。

- `id` は科目・授業回を含め、他デッキとも衝突しない固定IDにする。
- `prompt` は問い、`answer` は短い答え、`criterion` は自己判定基準。`explanation` は任意の補足文で、不要な場合も空文字を入れる。
- 数式の区切りは `\( ... \)`。JSONに書くときは `"\\( ... \\)"` のようにバックスラッシュを二重にする。任意のHTMLは書かない。
- `sources` は `file` にPDFのファイル名、`page` に1始まりの物理ページ番号を持つ配列。`sourceManifest` のファイル名と照合する。印刷上のページ番号と違う場合は補足に明記する。
- `promptHtml` などの表示用フィールドと `renderVersion` はビルドが生成する。手で書かない。iPhoneの教材読み込みでは生成済みの `.compiled.json` を使う。

学習記録は教材と別の `state.json` に保存される。回答イベントに問題IDと問題版を残し、古い版への回答も消さない。問題を変更して版を増やすと、その問題は新しく確認する候補に戻る。
