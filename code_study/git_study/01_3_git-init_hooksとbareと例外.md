# 01_3. `git init` 後編 — hooks・`--bare`・`.git` がファイルのとき

← 目次 [01_0 全体像と読む順番](./01_0_Git_全体像と読む順番.md)

← 前 [git init 前編](./01_2_git-init_空のgitを1行ずつ.md)　／　次 → [git add / git commit](./01_4_add-commit_indexとオブジェクトの増え方.md)

> **このページは分冊です。** 全体像は [01_0](./01_0_Git_全体像と読む順番.md)。
> 対象日 2026-09-17 / git 2.50.1 (Apple Git-155) / macOS。
> [前編](./01_2_git-init_空のgitを1行ずつ.md)（§2.1〜§2.4）の続きです。節番号は通しで §2.5 から始まります。
> ここでは「使わないファイル」「共有されない仕組み」「`.git` の例外形」を扱います。

## 2.5 `.git/description` — 見なくていい 1 行

```console
$ cat .git/description
Unnamed repository; edit this file 'description' to name the repository.
```

GitWeb（Git 付属の古い Web ビューア）がリポジトリ一覧に出す説明文です。
GitHub も GitLab もこのファイルを読みません。**実質的に死んでいるファイル**です。

---

## 2.6 `.git/hooks/` — 14 個すべてサンプル

```console
$ ls -l .git/hooks/pre-commit.sample
-rwxr-xr-x@ 1 akito_inoue  wheel  1649 Sep 17 13:37 .git/hooks/pre-commit.sample

$ head -6 .git/hooks/pre-commit.sample
#!/bin/sh
#
# An example hook script to verify what is about to be committed.
# Called by "git commit" with no arguments.  The hook should
# exit with non-zero status after issuing an appropriate message if
# it wants to stop the commit.
```

実行ビットは立っていますが、**Git は `.sample` が付いたファイルを呼びません**。
有効にするには拡張子を外します。

```bash
mv .git/hooks/pre-commit.sample .git/hooks/pre-commit
```

「デフォルトで無効にするために別名にしておく」という素朴な仕組みです。

### 設計上の重要な性質：hooks は共有されない

`.git/` の中にあるので、**`git push` しても相手に届きません**。
チームで共有したいなら `core.hooksPath` でリポジトリ内のディレクトリを指すか、
husky / lefthook のようなツールを使って `git init` 後にインストールさせます。

これはセキュリティ上の設計です。もし hooks が clone で降ってきたら、
**`git clone` しただけで任意コードが実行される**ことになります。

---

## 2.7 `.git/info/exclude` — 共有しない `.gitignore`

```
# myapp/.git/info/exclude（実物）
# git ls-files --others --exclude-from=.git/info/exclude
# Lines that start with '#' are comments.
# For a project mostly in C, the following would be a good set of
# exclude patterns (uncomment them if you want to use them):
# *.[oa]
# *~
```

書式は `.gitignore` と同じですが、**このファイル自体が追跡対象外**なので共有されません。

使い分けはこうです。

| 置き場所 | 共有 | 何を書くか |
|---|---|---|
| `.gitignore`（作業ツリー） | される | `node_modules/`、ビルド成果物。チーム全員に関係あるもの |
| `.git/info/exclude` | されない | **自分だけ**が置いている作業メモ、エディタの一時ファイル |
| `~/.config/git/ignore` | されない | `.DS_Store` など、全プロジェクト共通の自分の事情 |

`.DS_Store` を各プロジェクトの `.gitignore` に書いて回るのは、本来はグローバル ignore の仕事です。

---

## 2.8 `git init --bare` — 作業ツリーを持たないリポジトリ

GitHub 側に相当するリポジトリはこれです。

```console
$ git init --bare server.git
Initialized empty Git repository in .../lab/server.git/

$ find server.git -maxdepth 1 | sort
server.git
server.git/HEAD
server.git/config
server.git/description
server.git/hooks
server.git/info
server.git/objects
server.git/refs
```

**`.git` というディレクトリが無く、その中身が直接置かれています。** config も 1 箇所違います。

```ini
# server.git/config（実物）
[core]
	repositoryformatversion = 0
	filemode = true
	bare = true
	ignorecase = true
	precomposeunicode = true
```

`bare = true` と、`logallrefupdates` が無い点が違います。

### なぜ共有リポジトリは bare でなければならないか

非 bare リポジトリに push すると、**`refs/heads/main` だけが進んで作業ツリーが取り残されます**。
サーバ上で `git status` すると、誰も消していないファイルが「全部削除された」ように見える状態です。
この事故を防ぐため、Git は既定でチェックアウト中のブランチへの push を拒否します。

bare には作業ツリーが無いので、そもそもこの矛盾が起きません。
「共有用は bare」は運用の慣習ではなく、**データモデル上の必然**です。

---

## 2.9 `.git` はディレクトリとは限らない

最後に例外を 1 つ。`.git` が**ファイル**のこともあります。

```console
$ git worktree add ../wt-signin feature/signin
$ ls -la ../wt-signin/.git
-rw-r--r--@ 1 akito_inoue  wheel  156 Sep 17 13:20 ../wt-signin/.git

$ cat ../wt-signin/.git
gitdir: .../lab/myapp/.git/worktrees/wt-signin
```

`git worktree` とサブモジュールで使われる形式です。詳しくは
[01_9 §9.4](./01_9_困ったときの早見表.md) を見てください。

`.git` がディレクトリでなくても Git が動くのは、Git が常に
「`.git` を読んで `GIT_DIR` を決める」という間接参照を経由しているからです。
環境変数で直接指定することもできます。

```console
$ GIT_DIR=.../mygitdir GIT_WORK_TREE=.../work git init
$ ls -1 .../mygitdir
HEAD
config
description
hooks
info
objects
refs
```

---

## 理解度チェック

<details>
<summary><b>Q1.</b> チーム全員に <code>pre-commit</code> を強制したい。<code>.git/hooks/pre-commit</code> をコミットすればよい？</summary>

**A.** できない。`.git/` の中は追跡対象外なので push されない。
これは意図的な設計で、そうでなければ `git clone` しただけで任意コードが実行されてしまう。
リポジトリ内にスクリプトを置いて `core.hooksPath` を指すか、husky / lefthook のような導入ツールを使う。 → §2.6
</details>

<details>
<summary><b>Q2.</b> 共有用リポジトリを <code>--bare</code> なしで作って push したらどうなる？</summary>

**A.** サーバ側の `refs/heads/main` だけが進み、作業ツリーが取り残される。
サーバで `git status` すると「全ファイルが削除された」ように見える。
この矛盾を避けるため Git は既定でチェックアウト中のブランチへの push を拒否する。
共有用が bare なのは慣習ではなくデータモデル上の必然。 → §2.8
</details>

<details>
<summary><b>Q3.</b> <code>.DS_Store</code> を無視したい。どこに書くのが正しい？</summary>

**A.** `~/.config/git/ignore`（グローバル ignore）。
`.gitignore` はチーム全員に関係するものを書く場所で、
自分の OS やエディタの事情はグローバル、または `.git/info/exclude` に書く。 → §2.7
</details>

---

## 次にどこを読むか

| 知りたいこと | 行き先 |
|---|---|
| `refs/heads/main` はいつ作られるのか | [01_4 §4.3](./01_4_add-commit_indexとオブジェクトの増え方.md) |
| `.git/index` の中身 | [01_4 §3.2](./01_4_add-commit_indexとオブジェクトの増え方.md) |
| `HEAD` が symbolic ref でなくなるとき | [01_5 §5.5](./01_5_git-branch_refsはただのテキスト.md) |
| bare リポジトリへ push する話 | [01_6 §6.3](./01_6_git-remote-add_originという別名.md) |
| worktree をもっと詳しく | [01_9 §9.4](./01_9_困ったときの早見表.md) |

---

← 前 [git init 前編](./01_2_git-init_空のgitを1行ずつ.md)　／　次 → [git add / git commit](./01_4_add-commit_indexとオブジェクトの増え方.md)

← 目次 [01_0 全体像と読む順番](./01_0_Git_全体像と読む順番.md)
