# 課題6・7のC++版

課題6・7はC++版に移行しました。旧Python実行コードと専用計算関数は削除しています。
課題1〜5のPythonコードと、共通の描画関数は引き続き使用します。
元のPython版と同じ順序で読めるようにしています。

- `kadai6_1.cpp`：行列生成 → QR法 → 精度評価 → 結果保存。
- `kadai7.cpp`：行列生成 → 2つのQR法を比較 → 精度評価 → 結果保存。
- `utils_math.cpp` / `utils_math.hpp`：使用する計算関数。
- `plot_results.py`：保存したCSVを既存の `../utils_plot.py` で描画。
- `run.py`：ビルド・実行・描画を順に実行する短いスクリプト。

行列サイズと試行回数は、各 `kadai*.cpp` の冒頭で変更できます。
初期値はPython版と同じ `{10, 20, 40, 80}`、100試行です。
最大反復回数は冒頭の `max_iter = 10000`、許容値は `1e-6` です。
両課題とも最大反復回数までに収束しなければ、メッセージを表示して
その試行をCSVにNaNとして保存し、次の計算へ進みます。

## 実行方法（macOS）

リポジトリのルートで実行します。C++コンパイラと、Matplotlibを使えるPython環境が必要です。
QR分解と参照固有値計算にはmacOS付属のAccelerateを使います。

```sh
.venv/bin/python 'Kyoto_Univ/[2026後期月３]数理工学実験/section2/cpp/run.py' 6_1
.venv/bin/python 'Kyoto_Univ/[2026後期月３]数理工学実験/section2/cpp/run.py' 7
```

CSVと図は `cpp/figures/` に保存します。
自分でビルドする場合は、この `cpp` フォルダで次のように実行できます。

```sh
c++ -std=c++17 -O2 kadai7.cpp utils_math.cpp -framework Accelerate -o kadai7
./kadai7
python plot_results.py 7 figures/kadai7_results.csv
```

## 図と計算の対応

計算部分をC++に移し、描画は元のPython版と同じ設定を使っています。
課題6は修正Gram–Schmidt法、課題7はLAPACKのHouseholder QR分解です。
乱数生成器・丸め誤差・実行時間が異なるため、点の数値まで完全一致するものではありません。
乱数seedは7に固定しています。時間にはQR法の呼び出しだけを含めます。
