# `npm run dev` が動かない理由（ぜんぶ図で解説）

この課題（`2-6/kadai2-1`）で `npm run dev` が動かない理由を、順番に説明します。

**先に安心してほしいこと：あなたが書いた React のコードは壊れていません。**
原因は「コマンドを打つ場所」と「準備（ダウンロード）のし忘れ」の2つだけです。

---

## 1. 結論（いそいでいる人向け）

原因は2つあります。

```
┌─────────────────────────────────────────────────────────┐
│ 原因①  コマンドを打っている「場所」がちがう             │
│         → kadai2-1/ ではなく introduction/ で打つ       │
├─────────────────────────────────────────────────────────┤
│ 原因②  npm install をまだ実行していない                 │
│         → 部品（node_modules）がダウンロードされてない   │
└─────────────────────────────────────────────────────────┘
```

直し方は、ターミナルでこの3行です。

```bash
cd introduction     # ← ①の解決：正しいフォルダに移動する
npm install         # ← ②の解決：必要な部品をダウンロードする（初回だけ）
npm run dev         # ← これで動く
```

「なんでそうなるの？」が大事なので、ここから図で説明します。

---

## 2. 前提知識：`npm run dev` って、そもそも何をしているの？

### 2-1. レストランでたとえると

プログラムを動かすのは、料理を作るのにそっくりです。

```
      あなた                    キッチン（プロジェクトのフォルダ）
        │
        │ 「カレー作って！」
        │  = npm run dev
        ▼
   ┌─────────┐
   │   npm   │  ← 店長さん。自分では料理しない。
   │ （店長） │     「レシピ帳」を見て、コックさんに指示を出す人。
   └────┬────┘
        │
        │ ① まずレシピ帳をさがす
        ▼
   ┌───────────────────┐
   │  package.json     │ ← レシピ帳。
   │  （レシピ帳）      │    「dev と言われたら vite を呼べ」と書いてある。
   └────┬──────────────┘
        │
        │ ② レシピに書いてあるコックさんを呼ぶ
        ▼
   ┌───────────────────┐        ┌────────────────────────┐
   │  vite             │ ←──────│  node_modules/         │
   │  （コックさん）    │  ここに │  （倉庫）               │
   └────┬──────────────┘  住んで │  コックさんや調理器具が │
        │                  いる   │  ぜんぶ入っている       │
        │                         └────────────────────────┘
        │ ③ 料理完成！
        ▼
   http://localhost:5173  ← ブラウザで見られる自分のサイト
```

ここで覚えてほしい登場人物は4つです。

| 名前 | 正体 | たとえると |
|---|---|---|
| `package.json` | このプロジェクトの設定が書かれたファイル | **レシピ帳**（何が必要か・何を実行するか） |
| `package-lock.json` | 部品の「正確なバージョン」を記録したファイル | **買った物の型番まで書いた領収書** |
| `node_modules/` | 実際にダウンロードされた部品の置き場 | **倉庫**（コックさん＋調理器具） |
| `npm install` | 部品をダウンロードするコマンド | **買い出しに行く** |

### 2-2. `package.json` の中身を実際に見てみよう

`introduction/package.json` には、こう書いてあります（一部）。

```json
{
  "name": "introduction",
  "scripts": {
    "dev": "vite",            ← ★ここ！ npm run dev = vite を実行する、という意味
    "build": "tsc -b && vite build",
    "lint": "oxlint",
    "preview": "vite preview"
  },
  "dependencies": {           ← アプリを動かすのに必要な部品リスト
    "react": "^19.2.8",
    "react-dom": "^19.2.8"
  },
  "devDependencies": {        ← 開発するときだけ必要な部品リスト
    "vite": "^8.2.2",
    "typescript": "~6.0.2",
    ...
  }
}
```

つまり **`npm run dev` は「`package.json` の `scripts` の `dev` に書いてあるコマンドを実行して」という意味**です。
`npm` 自体は `dev` が何なのかを知りません。**`package.json` を読んで初めてわかる**のです。

### 2-3. `npm run dev` が中でやっていること（フローチャート）

```
              $ npm run dev
                   │
                   ▼
   ┌───────────────────────────────────────┐
   │ ① いま自分がいるフォルダに            │
   │    package.json はある？              │
   └───────────────┬───────────────────────┘
          ない ←───┴───→ ある
           │              │
           ▼              ▼
  ╔══════════════╗   ┌────────────────────────────┐
  ║ エラー!!     ║   │ ② scripts.dev を読む       │
  ║ code ENOENT  ║   │    → "vite" だとわかる     │
  ╚══════════════╝   └───────────┬────────────────┘
   ↑ 今回の原因①                 │
                                 ▼
                   ┌───────────────────────────────────────┐
                   │ ③ vite という道具を                   │
                   │    node_modules/.bin/ の中からさがす  │
                   └───────────────┬───────────────────────┘
                          ない ←───┴───→ ある
                           │              │
                           ▼              ▼
                  ╔════════════════════╗ ┌──────────────────────┐
                  ║ エラー!!           ║ │ ④ 開発サーバー起動   │
                  ║ vite: command      ║ │ localhost:5173 でOK  │
                  ║      not found     ║ └──────────────────────┘
                  ╚════════════════════╝
                   ↑ 今回の原因②
```

**あなたは①と③の2か所で止まっていました。** 順番に見ていきます。

---

## 3. 原因①：コマンドを打つ「場所」がちがう

### 3-1. フォルダの形を見てみよう

このリポジトリはこうなっています。

```
kadai2-1/                      ← ❌ ここで npm run dev をしてもダメ
│                                   （package.json がないから）
│   ※ このフォルダの中には introduction しか入っていない
│
└── introduction/              ← ✅ ここが本当のプロジェクト！
    ├── package.json           ← ★ レシピ帳はここにある
    ├── package-lock.json
    ├── index.html
    ├── vite.config.ts
    ├── tsconfig.json
    ├── public/
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── TodoList.tsx
        └── TodoItem.tsx
```

`npm` は、**「今いるフォルダ」の `package.json` しか見ません。**
一つ下の階層まで探しに行ってはくれません。

```
    【あなたが立っていた場所】          【レシピ帳がある場所】

        kadai2-1/                        kadai2-1/introduction/
      ┌──────────┐                      ┌──────────────────┐
      │   🧍     │   「レシピ帳は？」    │  📕 package.json │
      │          │   ──────✗──────→     │                  │
      │ (空っぽ) │   npm は下の階層を    │                  │
      └──────────┘    探しに行かない      └──────────────────┘
```

### 3-2. 実際に出るエラーと、その読み方

`kadai2-1/` で `npm run dev` を打つと、こう出ます。

```
npm error code ENOENT
npm error syscall open
npm error path /..../Base-React/2-6/kadai2-1/package.json
npm error errno -2
npm error enoent Could not read package.json: Error: ENOENT: no such file or directory,
                 open '/..../Base-React/2-6/kadai2-1/package.json'
```

英語が長くて読む気がなくなりますが、**大事なのは2か所だけ**です。

```
   npm error code ENOENT
                  └─┬──┘
                    └─→ Error NO ENTry（＝そんなファイル、無いよ）の略。
                        「ファイルが見つからない」ときの合言葉。

   npm error path /..../kadai2-1/package.json
                  └────────────┬─────────────┘
                               └─→ 「このパスを探したけど無かった」
                                   ＝ここに package.json が無い、と言っている
```

エラーは**あなたを責めているのではなく、「どこを探して、何が無かったか」を教えてくれている**だけです。
英語を全部読まなくていいので、`code` と `path` の2行だけ見るクセをつけてください。

### 3-3. 予防法：打つ前に `ls` する

```bash
ls        # 今いるフォルダの中身を一覧表示するコマンド
```

この結果に **`package.json` が見えていればOK**、見えていなければ場所が違う、と判断できます。

```
$ ls                         $ cd introduction
introduction                 $ ls
   ↑                         index.html   package.json   src   vite.config.ts  ...
   package.json が                            ↑
   見当たらない → ❌                        見えた！ → ✅
```

---

## 4. 原因②：`npm install` をまだしていない

場所を直して `introduction/` で `npm run dev` を打つと、今度はこう出ます。

```
> introduction@0.0.0 dev
> vite

sh: vite: command not found
```

### 4-1. エラーの読み方

```
   sh:  vite: command not found
   │     │         │
   │     │         └─→ 「そんなコマンド（道具）、見つからないよ」
   │     └───────────→ 探した道具の名前（レシピ帳に書いてあったコック）
   └─────────────────→ sh = シェル。コマンドを実行する人
```

上の2行（`> introduction@0.0.0 dev` / `> vite`）は、
**「レシピ帳は読めました。`dev` は `vite` のことですね。じゃあ `vite` を呼びます」**という報告です。
つまり**原因①はクリアできている**証拠です。ここまでは前進しています。

### 4-2. なぜ `vite` がいないのか

`vite` は、`node_modules/` という倉庫の中に住んでいます。
そして今、`introduction/` に **`node_modules/` フォルダがありません**。

```
     【いまの状態】                    【npm install したあと】

  introduction/                      introduction/
  ├── package.json  📕               ├── package.json  📕
  ├── package-lock.json              ├── package-lock.json
  ├── index.html                     ├── index.html
  ├── src/                           ├── src/
  └──                                └── node_modules/   ★これが生える！
        ↑                                ├── react/
   倉庫が無い！                          ├── react-dom/
   だから vite もいない                  ├── vite/
   → command not found                   ├── typescript/
                                         ├── ...（数百〜数千個）
                                         └── .bin/
                                             └── vite  ★コックさん、着任
```

`npm install` は、レシピ帳（`package.json`）と領収書（`package-lock.json`）を見ながら、
**インターネットから必要な部品を全部ダウンロードして `node_modules/` を作るコマンド**です。

```
   $ npm install
   ┌──────────────┐          ┌─────────────────┐          ┌───────────────┐
   │ package.json │ ──読む──→│  npm（店長）    │──買い出し→│  インターネット│
   │ package-lock │          │                 │←─────────│  (npmレジストリ)│
   └──────────────┘          └────────┬────────┘  部品     └───────────────┘
                                      │
                                      ▼
                             node_modules/ が完成 🎉
```

### 4-3. 「え、なんで最初から入ってないの？」

GitHub から落としてきたのに `node_modules/` が無いのは、**わざと入れていない**からです。
`introduction/.gitignore` にこう書いてあります。

```
node_modules      ← 「このフォルダは Git に登録しないでね」という指定
dist
*.local
```

理由は2つ。

```
  理由1：とにかく重い
     node_modules は、ファイルが数万個・数百MBになることもある。
     これを毎回 GitHub に上げ下ろしするのは、現実的じゃない。

  理由2：無くても復元できる
     package.json（何が必要か）と package-lock.json（どのバージョンか）
     さえあれば、npm install で誰でも「まったく同じ倉庫」を作り直せる。

     📕レシピ帳 + 🧾領収書  ──npm install──→  📦倉庫（node_modules）
     ↑ これだけ Git で共有すれば十分！
```

だから、**GitHub からクローンしてきたプロジェクトは、まず `npm install` する**。
これは React に限らず、世界中のほぼ全部の JavaScript プロジェクトで共通のお作法です。

> 💡 補足：`package-lock.json` がある場合は `npm install` のかわりに `npm ci` も使えます。
> `npm ci` は「領収書どおりにきっちり同じ物を入れる」コマンドで、より確実・高速です。
> どちらでも今回は動きます。迷ったら `npm install` でOK。

---

## 5. やってみよう

ターミナルで、上から順に実行してください。

```bash
# ① 課題のフォルダへ移動（kadai2-1 にいる状態から）
cd introduction

# ② 本当にここで合っているか確認（package.json が見えればOK）
ls

# ③ 必要な部品をダウンロード（初回だけ。1〜3分くらいかかります）
npm install

# ④ 開発サーバーを起動
npm run dev
```

成功すると、こんな表示が出ます。

```
> introduction@0.0.0 dev
> vite

  VITE v8.2.2  ready in 1096 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

この `http://localhost:5173/` を **Ctrl（Mac は ⌘）を押しながらクリック**するか、
ブラウザのアドレス欄にコピペすると、自分の TodoList が表示されます。

```
   ┌────────────────────────┐
   │ TodoList               │
   │ ☐  おべんきょ          │
   │ ☑  ~~りょうり~~        │  ← done: true なので打ち消し線＆グレー
   │ ☐  そうじ              │
   └────────────────────────┘
```

**止めるとき**：ターミナルで `Ctrl + C`（Mac でも Control キー。⌘ ではありません）。

**次回から**：`npm install` は毎回やる必要はありません。`cd introduction` → `npm run dev` だけでOKです。
（`package.json` に新しい部品が追加されたときだけ、また `npm install` します。）

---

## 6. 困ったときの早見表

| ターミナルに出た文字 | 意味 | どうする |
|---|---|---|
| `code ENOENT` / `Could not read package.json` | そのフォルダに `package.json` が無い | `cd` で正しいフォルダへ。`ls` で確認 |
| `sh: vite: command not found` | `node_modules` に道具が無い | そのフォルダで `npm install` |
| `Cannot find module 'react'` など | 部品が足りない／壊れている | `npm install` をやり直す |
| `Port 5173 is in use, trying another one...` | 5173番の入口を別のアプリが使用中。Vite が自動で 5174 などにずらして起動する | エラーではないので、表示された方の URL を開けばOK。気になるなら前のサーバーを `Ctrl + C` で止める |
| `npm ERR! code EACCES` | 権限（書き込みの許可）が足りない | そのフォルダの場所・権限を確認。`sudo` で無理やり入れるのは基本NG |
| `Unsupported engine` / 動作が変 | Node.js のバージョンが古い | `node -v` で確認。古ければ Node を更新 |

バージョンの確認コマンド：

```bash
node -v   # 例: v26.0.0
npm -v    # 例: 11.12.1
```

（この課題は Node v26.0.0 / npm 11.12.1 で動作確認しています。）

---

## 7. おまけ：あなたのコードは正しく書けています

念のため、`src/` の中身も全部確認しました。

```
  src/main.tsx      ✅ createRoot で App を描画。問題なし
  src/App.tsx       ✅ useState で items を管理し、handleToggle で
                       done を反転。immutable な更新（...item のスプレッド）も正しい
  src/TodoList.tsx  ✅ items が空のときの表示分岐あり。map の key も item.id で適切
  src/TodoItem.tsx  ✅ checked / onChange の組み合わせが正しい（制御コンポーネント）
  vite.config.ts    ✅ 問題なし
  tsconfig*.json    ✅ 問題なし
```

**エラーの原因は、コードではなく「環境の準備」でした。**
プログラミングでは、「コードが悪い」より「環境の準備が終わっていない」でつまずくことのほうが実は多いです。
エラーが出たら、まず

1. **今どこにいる？**（`pwd` / `ls`）
2. **準備は済んでる？**（`node_modules` はある？）
3. **エラーの最初の1〜2行だけ読む**（`code` と `path`）

この3ステップを思い出してください。これだけで、たいていの「動かない！」は自分で解決できます。
