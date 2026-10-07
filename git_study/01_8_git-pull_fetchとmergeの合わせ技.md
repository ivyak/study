# 01_8. `git pull` — fetch と merge の合わせ技

← 目次 [01_0 全体像と読む順番](./01_0_Git_全体像と読む順番.md)

← 前 [git fetch — 取ってくるだけ](./01_7_git-fetch_取ってくるだけ.md)　／　次 → [困ったときの早見表](./01_9_困ったときの早見表.md)

> **このページは分冊です。** 全体像は [01_0](./01_0_Git_全体像と読む順番.md)。対象日 2026-09-17 / git 2.50.1。
> [01_7](./01_7_git-fetch_取ってくるだけ.md) の続きで、`refs/heads/main` を動かす側の話。
> 読むと、コンフリクト中の `.git` に何が置かれているかが分かります。出力はすべて実物です。

---

## 8.1 `git pull` の正体

```
   git pull  ＝  git fetch            （= 01_7 で見たもの。安全）
              +  git merge FETCH_HEAD （または git rebase。ここから危険）
```

前半は `.git/objects` と `refs/remotes/` しか触らず、**後半で初めて
`refs/heads/*`・`index`・作業ツリーが書き換わります**。「pull は危険で fetch は安全」はこの差です。

### 分岐していると、最近の Git は止まる

```console
$ git pull            # 検証環境: git 2.50.1
From ../server
   e704b40..41cd24c  main       -> origin/main
hint: You have divergent branches and need to specify how to reconcile them.
hint:   git config pull.rebase false  # merge
hint:   ...（rebase / ff only の案内。§8.7 で扱います）
fatal: Need to specify how to reconcile divergent branches.
```

**`fatal` で終わっていますが、fetch はすでに完了しています。**

```console
$ cat .git/refs/heads/main
9e1cb9c4c7b2f211eb14479a5ad691050cba41e5   ← 自分のまま
$ cat .git/refs/remotes/origin/main
41cd24c1b8973f8ede26fbac2839eefd32e7bdcf   ← 更新されている（fetch は済んでいる）
```

つまり**この `fatal` の直後は「fetch だけ済んだ状態」**です。慌てる必要はなく、
`git log main..origin/main` で中身を見てから merge か rebase を選べば済みます。

---

## 8.2 パターン①：fast-forward（自分が何もしていない場合）

自分に新しいコミットが無ければ、マージコミットは作られません。

```console
$ git merge origin/main
Updating aef822d..e704b40
Fast-forward
 hello.txt | 1 +
 memo.txt  | 1 +
 2 files changed, 2 insertions(+)   ...（create mode 100644 memo.txt）

$ cat .git/refs/heads/main
e704b40790420d4afc62dfcb3d144100444e9bba   ← origin/main と同じ値になった
$ cat .git/ORIG_HEAD
aef822d7070fcc3133b890df8beee1272a784c9b   ← 直前の位置が保存された
```

fast-forward は **`refs/heads/main` の中身を書き換えて作業ツリーを合わせるだけ**で、
新しいオブジェクトは 1 個も作られません。

```
   merge 前:  main ─▶ aef822d      origin/main ─▶ e704b40
   merge 後:  main ──────────────────────────▶ e704b40   （41 バイトを書き換えただけ）
```

`.git/ORIG_HEAD` はこのとき書かれます。**危険な操作の直前の HEAD を 1 つだけ覚えておく**ファイルで、
`merge` `rebase` `reset` `pull` が更新します。やり直すなら `git reset --hard ORIG_HEAD`。

---

## 8.3 パターン②：枝分かれ → マージコミット

自分も相手もコミットしている状態で `--no-rebase` を指定します。

```console
$ git pull --no-rebase
Merge made by the 'ort' strategy.
 memo.txt | 1 +   ...（1 file changed, 1 insertion(+)）
$ git cat-file -p $(cat .git/refs/heads/main)
tree ad88191629224996b1a21251e8193cac4e27ebcc
parent 9e1cb9c4c7b2f211eb14479a5ad691050cba41e5
parent 41cd24c1b8973f8ede26fbac2839eefd32e7bdcf
author Akito <akito@example.com> 1789624800 +0900
committer ...

Merge branch 'main' of ../server
```

**`parent` が 2 行あります。** これがマージコミットの正体で、他は普通のコミットと同じです。
1 行目が自分側（`9e1cb9c`）、2 行目が相手側（`41cd24c`）。この順序が
「`HEAD^` は自分側、`HEAD^2` は相手側」に対応します。

```console
$ git log --oneline --graph
*   2d0bd6e Merge branch 'main' of ../server
|\
| * 41cd24c bob: memo を追記
* | 9e1cb9c 自分: mine.txt を追加
|/
* e704b40 bob: memo.txt を追加
```

`ort` は既定のマージ戦略の名前です（"ostensibly recursive's twin" の略）。

---

## 8.4 コンフリクト中の `.git` には 4 つのファイルが増える

同じ行を両方が直した状態で pull します。

```console
$ git pull --no-rebase
Auto-merging hello.txt
CONFLICT (content): Merge conflict in hello.txt
Automatic merge failed; fix conflicts and then commit the result.

$ ls -1 .git
AUTO_MERGE      ← 増えた
COMMIT_EDITMSG  FETCH_HEAD  HEAD  ORIG_HEAD  config  index  logs  objects  refs
MERGE_HEAD      ← 増えた
MERGE_MODE      ← 増えた
MERGE_MSG       ← 増えた
```

| ファイル | 中身 | 役目 |
|---|---|---|
| `MERGE_HEAD` | `2ba462a4a5f4...` | **相手側のコミット**。あると Git は「マージ中」と判断する |
| `MERGE_MSG` | `Merge branch 'main' of ../server` + 競合ファイル一覧 | 解決後の `git commit` が使うメッセージ |
| `MERGE_MODE` | 空ファイル | fast-forward を許さない指定などのフラグ置き場 |
| `AUTO_MERGE` | `b2b874abb9b4...` | 自動生成された「競合マーカー入り」の tree |

`git status` が「You have unmerged paths」と言えるのは、**`.git/MERGE_HEAD` があるから**です。

### index が 1 パス 3 エントリになる

[01_4 §3.3](./01_4_add-commit_indexとオブジェクトの増え方.md) の「index が必要な理由 ②」の実物です。

```console
$ git ls-files -u
100644 52a29dc2505d120dda77cca65bfc5ec2452d250f 1	hello.txt
100644 5a2a193390a4280c2273bf21730d3101835f94c2 2	hello.txt
100644 7d73a8d25d1664983d00c083d1d518388c8a0686 3	hello.txt
```

ステージ番号 1 / 2 / 3 が、それぞれ**共通の祖先 / 自分 / 相手**です。中身も取り出せます。

```console
$ git cat-file -p 52a29dc...      # stage 1 = 祖先 → "hello / from bob"
$ git cat-file -p 5a2a193...      # stage 2 = 自分 → "hello / from bob（自分が直した）"
$ git cat-file -p 7d73a8d...      # stage 3 = 相手 → "hello / from bob（bobが直した）"
```

作業ツリーのファイルは、この 3 つを合成したものです。

```console
$ cat hello.txt
hello
<<<<<<< HEAD
from bob（自分が直した）
=======
from bob（bobが直した）
>>>>>>> 2ba462a4a5f41d55f3bac8905039740fea7f146a
```

**3 つの版がすべて index に残っている**ので、`git merge --abort` は
「`MERGE_HEAD` を消して `ORIG_HEAD` に戻す」だけで確実に元へ戻せます。
競合マーカーごと `git add` してしまっても `git checkout -m hello.txt` で作り直せます。

---

## 8.5 解決すると 3 段が 1 段に戻る

```console
$ printf 'hello\nfrom bob（2人で相談して直した）\n' > hello.txt
$ git add hello.txt
$ git ls-files -u
（出力なし = 未解決が無い）
$ git ls-files -s | grep hello
100644 f68a9d268bec8a70ea300c9f52be98d13e36c8c8 0	hello.txt   ← ステージ 0
```

`git add` の役目が「解決済みの印を付ける」と説明されるのは、
**3 エントリを消してステージ 0 の 1 つに置き換える**というこの動きのことです。

```console
$ git commit --no-edit
[main 0f928c3] Merge branch 'main' of ../server

$ ls .git/MERGE_HEAD .git/MERGE_MSG .git/AUTO_MERGE
ls: .git/AUTO_MERGE: No such file or directory
ls: .git/MERGE_HEAD: No such file or directory      （MERGE_MSG も同様）
```

コミットが成功すると 4 つの一時ファイルは削除されます。
**`.git/MERGE_HEAD` が残っている ＝ マージが終わっていない**と覚えておけば、状態判断に迷いません。

---

## 8.6 `--rebase` — 自分のコミットが作り直される

```console
$ git rev-parse HEAD
6018b1930e3c164efe6cb228e63e33a068e50b82
$ git pull --rebase
From ../server
   0f928c3..14cdc05  main       -> origin/main
Rebasing (1/1)Successfully rebased and updated refs/heads/main.

$ git rev-parse HEAD
47c402e76780186c8f4ddd926f92b7ebae98b9c7   ← 変わった
```

**同じ変更内容なのにハッシュが違います。** [01_1 §1.5](./01_1_Gitの世界観_4種類のオブジェクト.md) のとおり、
コミットは `parent` を中身に含むので、親が変われば別のオブジェクトになります。

`git log --oneline --graph` も `* 47c402e`（作り直された自分のコミット）→ `* 14cdc05`（相手）と
**枝分かれのない一直線**になります。手順は reflog にそのまま残っています。

```console
$ tail -3 .git/logs/HEAD
6018b19... 14cdc05... 1789632600 +0900	pull --rebase (start): checkout 14cdc05...
14cdc05... 47c402e... 1789632600 +0900	pull --rebase (pick): 自分: myfile 追加
47c402e... 47c402e... 1789632600 +0900	pull --rebase (finish): returning to refs/heads/main
```

**`start` → `pick` → `finish`** の 3 段階です。相手の先端へ移動し（`checkout`）、
自分のコミットを順に載せ直し（`pick`）、最後にブランチをそこへ向け直しています。
元のコミット `6018b19` は reflog から復旧できます。

---

## 8.7 どれを既定にするか

```bash
git config --global pull.rebase false   # 常に merge（マージコミットが増える）
git config --global pull.rebase true    # 常に rebase（履歴は一直線、ハッシュが変わる）
git config --global pull.ff only        # ff できないときは止める（最も安全）
```

判断材料は「**そのブランチを他人が見ているか**」です。

| 状況 | 推奨 | 理由 |
|---|---|---|
| 個人の作業ブランチ | `rebase` | 履歴が読みやすく、ハッシュが変わっても困る人がいない |
| 共有ブランチ（main など） | `merge` | rebase は push 済みコミットのハッシュを変え、全員の履歴と食い違う |
| よく分からない | `ff only` | 分岐していたら止まるので、その場で考えられる |

`ff only` を入れておくと `git pull` が事故を起こさないコマンドになります。
止まったら中身を見て、merge か rebase を自分で選べば済みます。

---

## 理解度チェック

<details>
<summary><b>Q1.</b> <code>git pull</code> が "fatal: Need to specify how to reconcile divergent branches" で終わった。今どういう状態？</summary>

**A.** **fetch は完了している**（`refs/remotes/origin/main` も `FETCH_HEAD` も更新済み）。
止まったのは後半の merge/rebase だけなので、中身を見てから `--no-rebase` / `--rebase` を選ぶ。 → §8.1
</details>

<details>
<summary><b>Q2.</b> マージの途中かどうかを機械的に判定するには？</summary>

**A.** `.git/MERGE_HEAD` の有無。`git status` もこれを見ている。解決して `git commit` が通ると
`MERGE_HEAD` / `MERGE_MSG` / `MERGE_MODE` / `AUTO_MERGE` の 4 つが削除される。 → §8.4 §8.5
</details>

<details>
<summary><b>Q3.</b> コンフリクトを解決したが、間違えて反対側の内容で <code>git add</code> してしまった。</summary>

**A.** commit 前なら `git checkout -m hello.txt` で競合状態に戻せる
（index が祖先・自分・相手の 3 エントリを保持しているため）。
commit 済みなら `git reset --hard ORIG_HEAD` でマージ開始前に戻す。 → §8.4 §8.2
</details>

---

## 次にどこを読むか

| 知りたいこと | 行き先 |
|---|---|
| 壊したときの復旧手順・`.git` ファイル早見表 | [01_9 §9.1 §9.2](./01_9_困ったときの早見表.md) |
| fetch だけ安全な理由 | [01_7 §7.1](./01_7_git-fetch_取ってくるだけ.md) |
| なぜ rebase でハッシュが変わるか | [01_1 §1.5](./01_1_Gitの世界観_4種類のオブジェクト.md) |

---

← 前 [git fetch — 取ってくるだけ](./01_7_git-fetch_取ってくるだけ.md)　／　次 → [困ったときの早見表](./01_9_困ったときの早見表.md)

← 目次 [01_0 全体像と読む順番](./01_0_Git_全体像と読む順番.md)
