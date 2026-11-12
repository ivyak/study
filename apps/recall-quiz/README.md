# ひとつ想起 / Recall Garden

Scriptableで動く個人用の短い想起クイズ。初版は微分積分学続論IIの第1回、15問です。頭の中で答え、すぐ解答を見て自己判定します。3問で一区切り、1問でも終了できます。どちらの自己判定でも1コインを得て、小さな庭に植物を置けます。

解答の下にある「原典を見る」をトグルで開くと、その場にPDFページ画像を表示します。画面は切り替えません。＋・−ボタンとスライダーで50〜300%に拡大縮小でき、「全体」で100%に戻ります。拡大後は画像内を上下左右にスクロールできます。画像もQuiz.jsに同梱するため、機内モードでも参照できます。

## iPhoneで始める

1. [Scriptable](https://apps.apple.com/jp/app/scriptable/id1405459188)をインストールする。
2. Macの `apps/recall-quiz/output/Quiz.js` をiPhoneへ渡す。iCloud DriveのScriptableフォルダへコピーするとスクリプトとして扱えます。iCloudを使わない場合は、Scriptableで新規スクリプトを作り、Quiz.jsの全文を貼り付けて `Quiz` と命名する。
3. Scriptableで `Quiz` を一度実行する。クイズ画面が開く。
4. 右上の「設定」で通知する昼の時刻を選び、「昼の通知」をONにして保存する。初期値はOFF、時刻欄は12:30。通知許可が求められたら許可する。
5. 「1分後の通知をテスト」を押し、アプリを閉じて通知を確認する。タップしてクイズへ戻る。

毎日の利用にMacの起動やSSH接続は不要です。画面・問題・数式は配布ファイルに含まれ、クイズ中のネット接続は使いません。通知はiOSへ予約します。集中モード・通知要約・通知許可の設定によって表示時刻は変わります。

同じスクリプトを複数同時に開かず、更新するときは画面を閉じてから同じ `Quiz` を置き換えてください。保存先の名前はスクリプト名に依存しません。

## 記録と教材

- Scriptableのローカルdocuments領域の `RecallQuiz/state.json` が記録の正本です。履歴、復習状態、コイン、庭、設定、途中の問題を保存します。
- 1問ごとに保存し、保存の応答後に次へ進みます。保存途中のデータと前回のバックアップも保持し、壊れた記録を黙って初期化しません。
- 「学習記録を書き出す」でJSONを書き出せます。「学習記録を復元する」は確認後に履歴を置き換えます。通知設定はこの端末の設定を維持します。
- iCloudバックアップは設定でONにできます。本体保存後、iCloud DriveのScriptable領域にある `RecallQuizBackup/state.json` へコピーします。同期完了の保証や複数端末での同時編集には使いません。
- 教材だけ追加・更新するときは、ビルドで作った `.compiled.json` をiPhoneへ渡し、「教材を読み込む」で選択します。初版は1教材を選んで使います。別教材へ切り替えても回答履歴と庭は残ります。
- アプリ削除や端末故障に備え、必要な記録は書き出しまたはバックアップを取ってください。

## 復習の初期ルール

初回の正解は翌日、別の日にも正解すると3・7・14・30日へ進みます。同じ日の正解だけで間隔を延ばしません。誤答は翌日と、少なくとも他の2問を挟んだ当日の再確認候補にします。当日の再確認は各問題1回までです。3問で止めれば、再確認のために続ける義務はありません。

これは試作用の単純な間隔です。FSRSではなく、試験日から逆算する機能もありません。試験全体の習得率は表示しません。

## Macで作成・検証する

Node.js 18以上を使用します。KaTeXはビルド時の数式変換、PlaywrightはPCでの画面検証に使います。iPhoneではnpmを使いません。

PCでUIを編集する場合は、リポジトリルートで次を実行します。

```bash
npm run dev --prefix apps/recall-quiz
```

`http://localhost:8766/` を開き、`src/index.html`、`src/style.css`、`src/app.js` を編集してください。保存すると再ビルドし、ブラウザを自動更新します。庭・設定の表示中はその画面を保ちます。ビルドエラーは画面に表示し、修正後に回復します。停止はCtrl+Cです。

- 見た目：`src/style.css`。
- 共通の外枠：`src/index.html`。
- 問題・解答・庭・設定の画面構成：`src/app.js`。

`src/index.html` はビルド前のテンプレートです。直接開かず、プレビューを使います。`output/` は生成物なので直接修正しません。開発用の自動更新処理は配布する `Quiz.js` には入りません。スマホ幅の確認はブラウザの開発者ツールの端末表示を使えます。

庭だけを開く場合は `http://localhost:8766/?screen=garden`、設定は `?screen=settings`。ポートを変える場合は `RECALL_QUIZ_PORT=8770 npm run dev --prefix apps/recall-quiz` のように指定します。

UIの修正後は、生成された `output/Quiz.js` をiPhoneの同じスクリプトへ取り込み直します。PCでの見た目の変更が、既に取り込み済みのiPhoneへ自動配信される仕組みではありません。

通常のビルドとロジック検証：

```bash
npm ci --prefix apps/recall-quiz
npm run build --prefix apps/recall-quiz -- --verify-sources
npm test --prefix apps/recall-quiz
open apps/recall-quiz/output/preview.html
```

ChromeがインストールされているPCでは、`npm run test:browser --prefix apps/recall-quiz` でスマホ幅の操作も検証できます。一時プロファイルを使い、外部HTTP通信は遮断します。

`--verify-sources` は原PDFのハッシュを検証します。原典画像は参照ページだけをMacのPDFKitで生成し、`.source-cache/<sha256>/` に保存して再利用します。初回生成にはMacのSwiftと原PDFが必要です。生成物と画像キャッシュはGit管理しません。原PDFが変わった場合は、古い画像のままビルドせず再照合を求めます。

別の環境に原PDFがなくてもキャッシュがあれば、`--verify-sources` を外して既存画像を再利用できます。原PDFもキャッシュもない場合は、明示的に `--without-source-images` を指定すると画像なしのプレビューを作れます。この場合は原資料の再照合や原典画像の同梱を実施したと扱いません。

別教材をビルドする場合：

```bash
npm run build --prefix apps/recall-quiz -- apps/recall-quiz/decks/<deck-id>.json --verify-sources
```

出力は `output/Quiz.js`、`output/<deck-id>.compiled.json`、`output/preview.html` です。outputは生成物としてGit管理しません。プレビューの履歴はブラウザ内の別領域で、iPhoneの履歴と同期しません。

画面用ソースは `src/index.html`、`style.css`、`app.js`。出題・報酬・履歴のルールは `core.js`、復旧を含むファイル保存は `storage.js`、iOSの通知・WebViewとの橋渡しは `scriptable.js` です。

## iPhoneで残る実機確認

- ロック中の通知と、タップでの直接起動。
- 初期設定を繰り返しても通知が重複しないこと、時刻変更、通知OFF。
- 3問、1問終了、答え表示後の中断・復帰。
- 回答直後の終了、連打、画面の開き直しで履歴とコインが整合すること。
- 機内モードで数式・庭まで表示できること。
- ファイル選択、教材更新、記録の書き出し・復元、必要ならiCloudバックアップ。

PCのテストはロジックと模擬APIの検証です。iPhoneのScriptable実機を操作した結果ではありません。
