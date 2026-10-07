# 01_6. D 問題その 2 — グラフ（BFS・DFS・Union-Find）

← 目次 [01_0 全体像と読む順番](./01_0_AtCoder攻略_全体像と読む順番.md)

← 前 [§5 DP](./01_5_D問題その1_DP.md)　／　次 → [§7 数学](./01_7_D問題その3_数学_約数と素数とmod.md)

> **このページは分冊です。** 全体像は [01_0](./01_0_AtCoder攻略_全体像と読む順番.md)。
> 対象日: **2026-09-17 時点**。コードは書き下ろしのサンプルで、そのまま提出できる形です。
> ここのコードは**ほぼ変更なしで使い回せる型**です。写経して手元に置いておいてください。

---

## 6.1 グラフとは「点と線」。問題文での見え方

**グラフ**は、点（**頂点 / vertex**）と、それをつなぐ線（**辺 / edge**）だけでできた構造です。
問題文ではこういう言葉で出てきます。

| 問題文の言い回し | グラフとしての意味 |
|---|---|
| 「N 個の都市と M 本の道路」 | 頂点 N 個、辺 M 本 |
| 「友達関係」「同じグループ」 | 無向グラフ。つながっているかを調べる |
| 「最短で何回の移動で行けるか」 | **BFS**（§6.3） |
| 「迷路を抜けられるか」 | グリッドの BFS / DFS（§6.5） |
| 「いくつのグループに分かれるか」 | 連結成分の数（§6.4 / §6.6） |

**「辺の重みが全部 1（重みなし）の最短距離」は BFS で解けます。** 重みがバラバラなときは
ダイクストラ法が必要ですが、それは D より上の帯の話が多いです。

---

## 6.2 グラフの持ち方 — 隣接リスト

入力はたいてい「M 行にわたって辺の両端」で来ます（§1.4 パターン 5）。

```
入力例
4 3          ← 頂点 4 個、辺 3 本
1 2
2 3
1 4
```

これを **隣接リスト**（各頂点から行ける先のリスト）に変換します。**この 6 行は丸暗記**です。

```python
N, M = map(int, input().split())
g = [[] for _ in range(N + 1)]      # 1-indexed なので N+1 個作る
for _ in range(M):
    a, b = map(int, input().split())
    g[a].append(b)
    g[b].append(a)                  # 無向グラフなので両方向。有向ならこの行を消す
```

```
   g = [ [], [2,4], [1,3], [2], [1] ]
          ↑    ↑ 頂点 1 からは 2 と 4 へ行ける
        使わない
```

- **頂点番号が 1 から始まる問題が多い**ので `range(N + 1)` で 1 個多く作る。`g[0]` は捨てます
- `g[b].append(a)` を書き忘れるのが最頻出バグ。**「無向か有向か」を問題文で必ず確認**
- **`[[]] * (N+1)` と書いてはいけません**（全部同じリストになる。§5.3 と同じ罠）

---

## 6.3 BFS（幅優先探索）— 最短距離の型

**BFS（Breadth-First Search）** は、スタートから近い順に波が広がるように探索します。
だから **最初にたどり着いたときが最短**になります。

```
        S ── a ── c          距離: S=0, a=1, b=1, c=2, d=2, e=3
        │    │
        b ── d ── e          1 歩で行ける所を全部 → 2 歩で行ける所を全部 → …
```

```python
from collections import deque

N, M = map(int, input().split())
g = [[] for _ in range(N + 1)]
for _ in range(M):
    a, b = map(int, input().split())
    g[a].append(b)
    g[b].append(a)

start = 1
dist = [-1] * (N + 1)       # -1 は「まだ来ていない」
dist[start] = 0
q = deque([start])
while q:
    v = q.popleft()                  # 左から取り出す ＝ 先に入れたものから
    for u in g[v]:
        if dist[u] != -1:            # もう来ている（＝もっと短い経路で来ている）
            continue
        dist[u] = dist[v] + 1
        q.append(u)
print(dist)
```

**要点は 3 つです。**
1. `deque` を使う。`popleft()` が **O(1)**。ふつうのリストの `pop(0)` は **O(N)** で TLE します
2. `dist[u] != -1` を **`q.append` する前に**チェックする。後だとキューが爆発します
3. `dist` は「距離」と「訪問済みフラグ」を兼ねています。`-1` が「未訪問」

計算量は **O(N + M)**。頂点も辺も 1 回ずつしか見ないので 10^5 規模でも通ります。
到達できない頂点の `dist` は `-1` のまま残るので、「行けるか？」の判定にもそのまま使えます。

---

## 6.4 DFS（深さ優先探索）— 行けるところまで行く

**DFS（Depth-First Search）** は、行き止まりまで進んでから戻る探索です。
「最短」は求まりませんが、**連結判定・全部たどる**用途で使います。

Python で書くときは、**再帰ではなくスタックで書くのを強くおすすめします**。
```python
# スタックを使った DFS（再帰を使わない）
seen = [False] * (N + 1)
stack = [1]
seen[1] = True
while stack:
    v = stack.pop()                  # 右から取り出す ＝ 後に入れたものから
    for u in g[v]:
        if seen[u]:
            continue
        seen[u] = True
        stack.append(u)
```

**BFS との違いは `popleft()` か `pop()` かだけ**です。それだけで挙動が変わります。
```
   deque + popleft() → 先入れ先出し（キュー）  → BFS → 最短距離が求まる
   list  + pop()     → 後入れ先出し（スタック）→ DFS → 最短にはならない
```

### 再帰で書きたい場合

```python
import sys
sys.setrecursionlimit(10 ** 6)       # 必須。書かないと RE する

def dfs(v):
    seen[v] = True
    for u in g[v]:
        if not seen[u]:
            dfs(u)
```

Python の再帰の深さ上限は既定で 1000 程度しかなく、**N = 10^5 の一本道グラフだと即 RE します**
（→ [§8.2 再帰の深さ](./01_8_Python落とし穴と提出前チェックリスト.md)）。上限を上げても、PyPy では再帰が
遅いうえに深いとクラッシュすることがあります。**迷ったらスタック版**を使ってください。

---

## 6.5 グリッドの探索 — 迷路問題の型

`H×W` のマス目を探索するときも、やることは BFS/DFS と同じです。
**マス `(i, j)` を頂点だと思う**だけ。隣接リストを作る代わりに、上下左右を計算します。

```python
from collections import deque

H, W = map(int, input().split())
S = [input() for _ in range(H)]

dist = [[-1] * W for _ in range(H)]
dist[0][0] = 0
q = deque([(0, 0)])
while q:
    i, j = q.popleft()
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):   # 下・上・右・左
        ni, nj = i + di, j + dj
        if not (0 <= ni < H and 0 <= nj < W):   # 盤の外
            continue
        if S[ni][nj] == "#":                    # 壁
            continue
        if dist[ni][nj] != -1:                  # 訪問済み
            continue
        dist[ni][nj] = dist[i][j] + 1
        q.append((ni, nj))
print(dist[H - 1][W - 1])
```

`((1,0), (-1,0), (0,1), (0,-1))` は**移動方向のテーブル**で、4 方向を 1 つのループで書く定番です。
斜めも含む 8 方向なら 8 個並べます。
```
        (-1,0)
           ↑              i が行（下が +）、j が列（右が +）
 (0,-1) ← (i,j) → (0,1)
           ↓
        ( 1,0)
```

**チェックの順番が大事です。** 「盤の外」を先に弾かないと、`S[ni][nj]` で
**Python の負の添字が反対側の端を読んでしまい、壁をすり抜けます**（エラーが出ないので最悪）。

---

## 6.6 Union-Find — 「同じグループか」を高速に判定する

「A と B は同じグループか」「グループはいくつあるか」を**ほぼ O(1)** で扱えるデータ構造です。
D 帯でそのまま出ます。**このクラスは丸暗記で貼り付けてください。**

```python
class UnionFind:
    def __init__(self, n):
        self.par = list(range(n))     # 親。最初は自分自身が親
        self.size = [1] * n           # そのグループの大きさ

    def find(self, x):                # x の代表（根）を返す
        while self.par[x] != x:
            self.par[x] = self.par[self.par[x]]   # 経路圧縮
            x = self.par[x]
        return x

    def union(self, x, y):            # x と y を同じグループにする
        x, y = self.find(x), self.find(y)
        if x == y:
            return False              # すでに同じ
        if self.size[x] < self.size[y]:
            x, y = y, x               # 大きいほうに小さいほうをぶら下げる
        self.par[y] = x
        self.size[x] += self.size[y]
        return True

    def same(self, x, y):             # 同じグループか
        return self.find(x) == self.find(y)

    def group_size(self, x):          # x の属するグループの大きさ
        return self.size[self.find(x)]
```

使い方はこれだけです。
```python
uf = UnionFind(N + 1)          # 1-indexed なら N+1 個作る
for _ in range(M):
    a, b = map(int, input().split())
    uf.union(a, b)

print(uf.same(1, 5))                                  # 1 と 5 は同じグループ？
print(len({uf.find(v) for v in range(1, N + 1)}))     # グループの個数
```

```
   union(1,2), union(3,4), union(2,3) のあと
   1 ─ 2 ─ 3 ─ 4     全部同じ代表を指す。find(4) == find(1) → True
```

**BFS でも連結判定はできます**が、Union-Find が強いのは
**「辺が 1 本ずつ追加されていく途中経過」を聞かれる問題**です。BFS だと毎回やり直しで
O(M(N+M)) ですが、Union-Find なら全体でほぼ O(M) です。

`find` の中の `self.par[x] = self.par[self.par[x]]` は**経路圧縮**といって、
根を探すついでに木を平らにしています。これが無いと木が細長くなって遅くなります。

---

## 理解度チェック

<details>
<summary><b>Q1.</b> BFS のコードで `deque` の `popleft()` をリストの `pop(0)` に置き換えると何が起きる？</summary>

**A.** `pop(0)` は先頭を消して残りを全部ずらすので **O(N)**。BFS 全体が O(N²) になり、
N = 10^5 で TLE する。`collections.deque` の `popleft()` は O(1)。
**BFS には必ず deque** と覚える。→ §6.3 / §2.6
</details>

<details>
<summary><b>Q2.</b> グリッド BFS で「盤の外か」のチェックを、壁判定 `S[ni][nj] == "#"` より後に書くと何が起きる？</summary>

**A.** `ni` や `nj` が **-1** のとき、Python は例外を出さず**反対側の端の要素**を読む。
その結果、盤の左端から右端へワープするような移動が発生して、答えが小さくなる WA。
例外が出ないぶん原因が分かりにくい。**範囲チェックを必ず最初に**書く。→ §6.5
</details>

<details>
<summary><b>Q3.</b> 連結判定は BFS でもできる。それでも Union-Find を使うのはどんなとき？</summary>

**A.** **辺が 1 本ずつ追加されていく途中で、そのつど「同じグループか」を聞かれる**とき。
BFS だと辺を足すたびに探索し直して O(M(N+M)) になるが、Union-Find は
全体でほぼ O(M) で済む。「i 本目の道路ができた時点でのグループ数を出力せよ」型が典型。→ §6.6
</details>

---

## 次にどこを読むか

| 知りたいこと | 行き先 |
|---|---|
| 約数・素数・mod の問題 | [§7 数学](./01_7_D問題その3_数学_約数と素数とmod.md) |
| 再帰で RE する／深さ上限 | [§8.2 再帰の深さ](./01_8_Python落とし穴と提出前チェックリスト.md) |
| DP に戻りたい | [§5 DP](./01_5_D問題その1_DP.md) |
| `[[]] * N` の罠の説明 | [§8.6 2 次元配列の罠](./01_8_Python落とし穴と提出前チェックリスト.md) |

---

← 前 [§5 DP](./01_5_D問題その1_DP.md)　／　次 → [§7 数学](./01_7_D問題その3_数学_約数と素数とmod.md)

← 目次 [01_0 全体像と読む順番](./01_0_AtCoder攻略_全体像と読む順番.md)
