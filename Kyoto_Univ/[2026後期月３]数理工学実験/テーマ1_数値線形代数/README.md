# テーマ1：数値線形代数レポート

- `report_template_preview.pdf`：本文・考察を記入したレポート。
- `report_template.tex`：編集用LaTeX原稿。
- `tables.tex`：集計表。実験環境は本文の箇条書きと `data/environment.json` に記載。
- `figures/`：本文に掲載した20枚のPDF図。課題5は5指標を1枚にまとめた。
- `data/`：結果CSV、集計、原図・元CSVのハッシュ、組版ログ、検証記録。
- `report_review.md`：設問への対応、実施した検証、残る確認事項。

課題1・2の数値は既存SVGの目盛と点の座標から復元した近似値です。
元の入力行列・右辺・シードが残っていない点を本文でも明記しています。
課題3は各次数3組の同一入力による追加比較、課題4・5は各100試行の再実験です。
課題6・7は既存C++版CSVを固定しました。未収束例もNaNとして保持しています。

## 再実験・図表の再生成

このフォルダで、リポジトリの仮想環境を用いて次を順に実行します。
追加実験は2026年10月26日に実施しました。

```sh
../../../.venv/bin/python tools/run_additional.py paired
../../../.venv/bin/python tools/run_additional.py eigen
../../../.venv/bin/python tools/prepare_assets.py
```

PythonのNumPy、SciPy、Matplotlibを使います。
元の計算関数は `../section2/utils_math.py` にあります。
課題6・7の再実験は `../section2/cpp/README.md` を参照してください。
`prepare_assets.py` は元の `section2/figures/` のSVGと
`section2/cpp/figures/` のCSVを読むので、これらも保管してください。
データを再生成した場合、本文中に直接記載した代表値・時間比も照合し直してください。

## PDFの組版

XeLaTeX互換のTectonicと、macOSのHiraginoフォントを使用します。
この作業ではTectonic 0.15.0を一時フォルダに取得して組版しました。
Tectonicが使える環境では、このフォルダで次を実行します。

```sh
tectonic --keep-logs report_template.tex
mv report_template.pdf report_template_preview.pdf
```

数値や入力条件を変えた場合は再点検し、PDFも再生成してください。
現在のPDFには氏名・学籍番号・学年・実験日・提出日を反映済みです。
実験場所は依頼者の指定により掲載していません。
通常QR法の未収束133件と、本人による内容の理解・最終確認は残る事項です。
