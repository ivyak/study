# `npm install` の出力メッセージ解説

## 元のメッセージ

```
added 72 packages, and audited 73 packages in 1s

13 packages are looking for funding
  run `npm fund` for details

2 vulnerabilities (1 moderate, 1 high)

To address all issues, run:
  npm audit fix

Run `npm audit` for details.
```

これは `npm install`（または `npm i`）を実行したときに表示される**正常終了のメッセージ**です。エラーではなく、インストールは成功しています。ただし「既知の脆弱性が2件ある」という注意が含まれています。

---

## 1行ずつの意味

### `added 72 packages, and audited 73 packages in 1s`

| 部分 | 意味 |
|---|---|
| `added 72 packages` | 72個のパッケージを `node_modules` にインストールした |
| `audited 73 packages` | 73個のパッケージについてセキュリティチェック（監査）を行った |
| `in 1s` | 処理にかかった時間は約1秒 |

自分で指定したパッケージが1〜2個だけでも、それらが依存している別のパッケージ（依存の依存）もまとめて入るため、数十個になるのは普通です。audited の数が1つ多いのは、プロジェクト自身（`package.json` のルート）も数に含まれるためです。

### `13 packages are looking for funding` / `run npm fund for details`

インストールしたパッケージのうち13個の作者が、寄付やスポンサーを募集しているという**お知らせ**です。`npm fund` を実行すると寄付先の一覧が見られます。

動作やセキュリティには一切関係ないので、無視して問題ありません。表示を消したい場合は次の設定ができます。

```bash
npm config set fund false
```

### `2 vulnerabilities (1 moderate, 1 high)`

インストールしたパッケージの中に、**既知のセキュリティ脆弱性**が2件見つかったという意味です。npm は公開されている脆弱性データベースと照合してこれを検出しています。

深刻度は4段階あります。

| 深刻度 | 目安 |
|---|---|
| low | 影響は小さい |
| moderate | 中程度。条件次第で問題になりうる |
| high | 深刻。対応を推奨 |
| critical | 非常に深刻。早急に対応すべき |

今回は moderate が1件、high が1件です。

### `To address all issues, run: npm audit fix`

脆弱性を自動で修正するコマンドの案内です。`npm audit fix` は、`package.json` で許可されているバージョン範囲内で、脆弱性が修正済みのバージョンへパッケージを更新します。範囲内の更新なので、基本的に既存のコードが壊れにくい安全な修正です。

### `Run npm audit for details.`

どのパッケージに、どんな脆弱性があるのか詳しく知りたいときは `npm audit` を実行してください、という案内です。

---

## どう対応すればいいか

おすすめの手順は次のとおりです。

**1. まず詳細を確認する**

```bash
npm audit
```

どのパッケージが原因か、自分が直接入れたものか（依存の依存か）、修正版があるかが表示されます。

**2. 自動修正を試す**

```bash
npm audit fix
```

多くの場合これで解決します。実行後にもう一度 `npm audit` を実行し、残っているか確認します。

**3. それでも残る場合**

`npm audit fix` で直らないものは、メジャーバージョンアップ（互換性が壊れる可能性のある更新）が必要なケースです。次のコマンドで強制的に更新できますが、**アプリが動かなくなる可能性がある**ため注意が必要です。

```bash
npm audit fix --force
```

使う前に Git でコミットしておき、実行後にアプリが正常に動くか確認してください。

---

## 知っておくと役立つこと

**すべての脆弱性が実際に危険とは限りません。** たとえば開発時にしか使わないツール（ビルドツールやテストツールなど）の脆弱性は、本番環境のユーザーには影響しないことが多いです。本番で使うパッケージだけを確認したい場合は次のように実行します。

```bash
npm audit --omit=dev
```

**学習用・個人の練習プロジェクトなら、急いで対応しなくても大きな問題にならないことが多いです。** 一方、インターネットに公開するサービスや業務のプロジェクトであれば、high 以上は確認して対応しておくのが安全です。

**`npm audit fix` の結果は `package-lock.json` に反映されます。** チームで開発している場合は、この変更もコミットして共有しましょう。

---

## まとめ

| メッセージ | 意味 | 対応 |
|---|---|---|
| added / audited | インストールと監査が完了 | 不要（成功） |
| looking for funding | 作者が寄付を募集中 | 不要（無視してOK） |
| vulnerabilities | 既知の脆弱性が見つかった | `npm audit` で確認 → `npm audit fix` |