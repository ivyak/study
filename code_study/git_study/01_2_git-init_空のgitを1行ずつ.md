# 01_2. `git init` — できたての `.git` を 1 ファイルずつ（前編）

← 目次 [01_0 全体像と読む順番](./01_0_Git_全体像と読む順番.md)

← 前 [Git の世界観 — 4種類のオブジェクト](./01_1_Gitの世界観_4種類のオブジェクト.md)　／　次 → [git init 後編 — hooks と bare](./01_3_git-init_hooksとbareと例外.md)

> **このページは分冊です。** 全体像は [01_0](./01_0_Git_全体像と読む順番.md)。
> 対象日 2026-09-17 / git 2.50.1 (Apple Git-155) / macOS。
> **`git init` が作るファイルは Git のバージョンと OS で変わります。** 数が合わなくても慌てないでください。
> 前編では `git init` の挙動と、`HEAD` / `config` を読みます。
> `hooks` / `--bare` / `.git` がファイルになる例外は [後編](./01_3_git-init_hooksとbareと例外.md)（§2.5〜§2.9）です。
---

## 2.1 `git init` は「フォルダを 1 個作るだけ」のコマンド

```console
$ mkdir myapp && cd myapp
$ git init
Initialized empty Git repository in .../lab/myapp/.git/
```

やっていることは、カレントディレクトリに `.git` を作り、雛形を展開することだけです。
**ネットワークにも、親ディレクトリにも、既存ファイルにも一切触りません。**
作業ツリーのファイルは 1 個も追跡対象になりません（`git status` で確認できます）。

### 何度実行しても壊れない

```console
$ git init .../lab/t2
Reinitialized existing Git repository in .../lab/t2/.git/
```

`Initialized` ではなく `Reinitialized` になります。
既存の `.git` があるときは、**足りない雛形を補うだけで、objects も refs も config も消しません**。
「うっかり 2 回 `git init` した」で履歴が飛ぶことはないので安心してください。

ただし例外があります。`git init --initial-branch=xxx` を既存リポジトリで実行すると
`HEAD` が書き換わります。コミット済みのリポジトリでは付けないでください。

---

## 2.2 できたての `.git` の全ファイル

`git init` 直後の実物です。**これで全部**です。

```
# myapp/.git（find .git | sort の実物）
.git
.git/HEAD
.git/config
.git/description
.git/hooks
.git/hooks/applypatch-msg.sample
.git/hooks/commit-msg.sample
.git/hooks/fsmonitor-watchman.sample
.git/hooks/post-update.sample
.git/hooks/pre-applypatch.sample
.git/hooks/pre-commit.sample
.git/hooks/pre-merge-commit.sample
.git/hooks/pre-push.sample
.git/hooks/pre-rebase.sample
.git/hooks/pre-receive.sample
.git/hooks/prepare-commit-msg.sample
.git/hooks/push-to-checkout.sample
.git/hooks/sendemail-validate.sample
.git/hooks/update.sample
.git/info
.git/info/exclude
.git/objects
.git/objects/info
.git/objects/pack
.git/refs
.git/refs/heads
.git/refs/tags
```

役割で分けると 4 つです。

```
  ┌─ 本体（この3つが Git の全部）──────────────────────────┐
  │  HEAD                 今どこにいるか（1行のテキスト）      │
  │  objects/             データ本体（今は空）                │
  │  refs/heads  refs/tags  名札置き場（今は空）              │
  └──────────────────────────────────────────────────┘
  ┌─ 設定 ────────────────────────────────────────────┐
  │  config               このリポジトリ限定の設定            │
  │  info/exclude         共有しない .gitignore             │
  └──────────────────────────────────────────────────┘
  ┌─ 拡張ポイント ─────────────────────────────────────┐
  │  hooks/*.sample       全部サンプル。そのままでは動かない    │
  └──────────────────────────────────────────────────┘
  ┌─ ほぼ使わない ─────────────────────────────────────┐
  │  description          GitWeb 用の 1 行説明              │
  └──────────────────────────────────────────────────┘
```

**`.git/index` はまだ存在しません。**

```console
$ ls -la .git/index
ls: .git/index: No such file or directory
```

これが「まだ一度も `git add` していない」ことの機械的な判定条件です。

---

## 2.3 `.git/HEAD` — 存在しないブランチを指している

```console
$ cat .git/HEAD
ref: refs/heads/main
$ wc -c .git/HEAD
      21 .git/HEAD
```

21 バイトのテキスト 1 行です。`ref: ` で始まるものを **symbolic ref** と呼び、
「`refs/heads/main` というファイルを見に行け」という転送指示になります。

`HEAD` には**ハッシュが入っていない**点に注意してください。
40 桁のハッシュを直接持つのはブランチ側（`refs/heads/main`、41 バイト）です。
`HEAD` がハッシュを直接持つのは detached HEAD のときだけで、
それが「detached（切り離された）」と呼ばれる理由です（[01_5 §5.5](./01_5_git-branch_refsはただのテキスト.md)）。

### ここが `git init` 最大の引っかかりどころ

`.git/refs/heads/main` は**まだ存在しません**（§2.2 の find 出力を見てください）。
つまり `HEAD` は**壊れたリンク**を指している状態です。これは異常ではなく、正常な初期状態です。

Git はこれを「unborn branch（まだ生まれていないブランチ）」として特別扱いします。

```console
$ git status
On branch main

No commits yet

nothing to commit (create/copy files and use "git add" to track)

$ git branch
（何も出力されない）

$ git symbolic-ref HEAD
refs/heads/main

$ git rev-parse HEAD
fatal: ambiguous argument 'HEAD': unknown revision or path not in the working tree.
```

`git status` は「On branch main」と言うのに `git branch` には 1 行も出ない。
この食い違いは、**`git branch` が `refs/heads/` のファイルを列挙している**のに対し、
**`git status` は `HEAD` のテキストを読んでいる**ためです。実装の違いがそのまま出ています。

`refs/heads/main` は、最初の `git commit` のときに初めて作られます（§4.3）。

ブランチ名を変えたいなら init 時に指定できます。

```console
$ git init --initial-branch=develop .../lab/t2
Initialized empty Git repository in .../lab/t2/.git/
$ cat .git/HEAD
ref: refs/heads/develop
```

既定値は `init.defaultBranch` 設定で決まります。設定していないと Git が警告を出します。

```console
$ git config --list --show-scope | head -4
unknown	credential.helper=osxkeychain
unknown	init.defaultbranch=main
global	user.name=...
global	user.email=...
```

`unknown` スコープは、Xcode Command Line Tools 版 Git が持っているシステム設定です
（`/Applications/Xcode.app/...` 配下など、`git config --show-origin` で実体が見えます）。

---

## 2.4 `.git/config` — 1 行ずつ意味がある

```ini
# myapp/.git/config（git init 直後の実物）
[core]
	repositoryformatversion = 0
	filemode = true
	bare = false
	logallrefupdates = true
	ignorecase = true
	precomposeunicode = true
```

| キー | 意味 | 変えるとどうなるか |
|---|---|---|
| `repositoryformatversion` | `.git` のフォーマット世代。`0` が通常、`1` は拡張機能あり | 手で触らない。SHA-256 リポジトリなどで `1` になる |
| `filemode` | 実行ビット（`100755`）の変化を差分として扱うか | `false` にすると chmod が無視される。Windows 共有や Docker マウントで `true` のままだと**全ファイルが変更扱い**になる事故が起きる |
| `bare` | 作業ツリーを持たないか | §2.8 |
| `logallrefupdates` | reflog（`.git/logs/`）を書くか | `false` にすると `git reflog` で復旧できなくなる。**絶対に切らない** |
| `ignorecase` | ファイル名の大小を区別しないファイルシステムか | macOS / Windows で `true`。`README.md` → `Readme.md` のリネームが認識されない原因 |
| `precomposeunicode` | macOS の NFD 正規化（濁点分解）を NFC に戻すか | macOS 専用。`false` だと「が」が「か + ゛」として記録され、Linux 側で別ファイルに見える |

`ignorecase` と `precomposeunicode` は**環境を見て自動で決まった値**です。
Linux で `git init` すればどちらも出てきません。ここが `.git/config` の面白いところで、
**リポジトリを作った環境の性質が固定値として焼き付きます**。

### 設定は 4 段重ねで、下が勝つ

```
  system   （git が入っている場所。全ユーザー共通）
     ↓
  global   （~/.gitconfig。あなた個人）
     ↓
  local    （.git/config。このリポジトリだけ）   ← git init が作るのはここ
     ↓
  worktree （.git/config.worktree。使うことは稀）
```

どこで決まっているか分からなくなったら `--show-origin` で追えます。

```console
$ git config --show-origin --get core.ignorecase
file:.git/config	true
```

なお `user.name` / `user.email` は `git init` では**書かれません**。
global にも無いと最初の `git commit` で止まります。

---

## 理解度チェック（前編）

<details>
<summary><b>Q1.</b> <code>git init</code> 直後、<code>git status</code> は "On branch main" と言うのに <code>git branch</code> は何も出さない。どちらが正しい？</summary>

**A.** どちらも正しい。`.git/HEAD` には `ref: refs/heads/main` と書かれている（status はこれを読む）が、
`.git/refs/heads/main` というファイルはまだ存在しない（branch はこれを列挙する）。
最初の `git commit` で実体が作られる。 → §2.3
</details>

<details>
<summary><b>Q2.</b> Docker でマウントしたリポジトリで、何も触っていないのに全ファイルが変更扱いになった。どこを見る？</summary>

**A.** `.git/config` の `core.filemode`。ホストとコンテナで実行ビットの見え方が違うと、
`100644` ↔ `100755` の変化として全ファイルが差分になる。`git config core.filemode false` で止まる。 → §2.4
</details>

<details>
<summary><b>Q3.</b> 既存のリポジトリでうっかり <code>git init</code> をもう一度実行してしまった。履歴は消えた？</summary>

**A.** 消えない。`Reinitialized existing Git repository` と出て、足りない雛形を補うだけ。
ただし `--initial-branch=xxx` を付けると `HEAD` が書き換わるので、コミット済みリポジトリでは付けないこと。 → §2.1
</details>

---

## 次にどこを読むか

| 知りたいこと | 行き先 |
|---|---|
| hooks / `--bare` / `.git` がファイルの場合 | [01_3 §2.5〜§2.9](./01_3_git-init_hooksとbareと例外.md) |
| `refs/heads/main` はいつ作られるのか | [01_4 §4.3](./01_4_add-commit_indexとオブジェクトの増え方.md) |
| `.git/index` の中身 | [01_4 §3.2](./01_4_add-commit_indexとオブジェクトの増え方.md) |
| `HEAD` が symbolic ref でなくなるとき | [01_5 §5.5](./01_5_git-branch_refsはただのテキスト.md) |

---

← 前 [Git の世界観 — 4種類のオブジェクト](./01_1_Gitの世界観_4種類のオブジェクト.md)　／　次 → [git init 後編 — hooks と bare](./01_3_git-init_hooksとbareと例外.md)

← 目次 [01_0 全体像と読む順番](./01_0_Git_全体像と読む順番.md)
