# 02. Python の `lambda` 式 — 関数をその場で作る

← [目次](./00_はじめに-読む順番.md)

## 基本形

```python
lambda 引数: 戻り値となる式
```

`lambda` は、名前を付けずに関数を作る書き方です。例えば次の 2 つはほぼ同じです。

```python
double = lambda x: x * 2

def double(x):
    return x * 2
```

どちらも `double(3)` を呼ぶと `6` を返します。`lambda` の本体には式を 1 つだけ書けます。複数の文を実行したいときは `def` を使います。

## 今回のエラーとの関係

`get_execution_time` は関数を受け取り、その関数を内部で呼び出します。

```python
def get_execution_time(func):
    start_time = time.perf_counter()
    func()
    return time.perf_counter() - start_time
```

次の書き方では、`Gaussian_elimination(...)` が **渡す前に実行**されます。戻り値は解のリストなので、内部の `func()` が「リストを関数として呼ぶ」ことになり、`TypeError: 'list' object is not callable` が出ます。

```python
get_execution_time(utils_math.Gaussian_elimination(A_list[j], b_list[j]))
```

`lambda` で包むと、**呼ばれたときに計算する関数**を渡せます。

```python
get_execution_time(
    lambda: utils_math.Gaussian_elimination(A_list[j], b_list[j])
)
```

この時点では `lambda` の中身は実行されません。`get_execution_time` 内の `func()` で実行され、その時間が測られます。

## `lambda j=j:` は何のため？

```python
lambda j=j: utils_math.Gaussian_elimination(A_list[j], b_list[j])
```

`j=j` は、関数を**作った時点の `j` の値**をデフォルト引数として保存します。ループで関数をいくつも作り、後から呼ぶ場合に役立ちます。

```python
funcs = [lambda j=j: j for j in range(3)]
print([func() for func in funcs])  # [0, 1, 2]
```

今回の `get_execution_time` は受け取った関数をすぐ呼ぶので、`lambda:` だけでも動きます。

## 確認

1. `get_execution_time(f())` と `get_execution_time(lambda: f())` では、`f` が実行されるのはそれぞれいつでしょうか？
2. `lambda x: x * 2` は、どんな引数を受け取り、何を返しますか？
3. ループ中に作った `lambda` を後から呼ぶ場合、`lambda j=j:` と書く理由は何でしょうか？
