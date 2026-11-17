from pathlib import Path

import matplotlib.pyplot as plt


def save_txt(*values, save_path):
  path = Path(__file__).with_name(save_path)

  # parents=True：途中のフォルダもまとめて作る
  path.parent.mkdir(parents=True, exist_ok=True)

  path.write_text("\n".join(str(value) for value in values), encoding="utf-8")
  
  return path

def plot_f(
    x,
    y,
    *,
    xlim=(-10, 10),
    ylim=(-10, 10),
    xlabel="x",
    ylabel="y",
    title=None,
    label=r"$f(x) = x^3 + 2x^2 - 5x - 6$",
    color=None,
    linewidth=1.5,
    linestyle="-",
    marker=None,
    figsize=(6.4, 4.8),
    grid=True,
    legend=True,
    show_axes=True,
    save_path="graph.svg",
    dpi=300,
):
  # * は、それ以降の引数は、名前を付けて指定するという区切り
  # title: 図のタイトル
  # label: 曲線の凡例
  # color: 曲線の色（例: "red"）
  # linewidth: 曲線の太さ。
  # linestyle: 線の種類（"-": 実線、"--": 破線、":": 点線）。
  # marker: 各点の記号（例: "o"）。None で記号なし。
  # figsize: 図の幅と高さをインチで指定。
  # grid, legend, show_axes: 格子線・凡例・原点を通る軸を表示するか。
  # save_path: 保存先。拡張子で形式を選ぶ（例: "graph.svg"）。None で保存しない。
  # dpi: PNGなどの画像の解像度。SVGの線や図形の鮮明さには影響しない。

  # plt.subplots(): 図全体を表す fig ・実際にグラフを描く領域 ax
  fig, ax = plt.subplots(figsize=figsize)

  # ax.plot(x, y): 各 (x, y) を線で結ぶ
  # label は凡例に表示する文字列。r"..." はバックスラッシュをそのまま扱う表記
  # $...$ は数式として表示
  ax.plot(
      x, y, label=label, color=color, linewidth=linewidth,
      linestyle=linestyle, marker=marker,
  )

  # ax.set_xlim(最小値, 最大値): x軸の表示範囲を指定
  if xlim is not None:
    ax.set_xlim(*xlim)  # * で (最小値, 最大値) を2つの引数に展開する。

  # ax.set_ylim(最小値, 最大値): y軸の表示範囲を指定
  if ylim is not None:
    ax.set_ylim(*ylim)

  # ax.set_xlabel / ax.set_ylabel: 各軸の名前を設定
  ax.set_xlabel(xlabel)
  ax.set_ylabel(ylabel)
  if title is not None:
    ax.set_title(title)

  # ax.axhline(y): 指定した y の位置に水平線を引く
  # color は線の色、linewidth は線の太さを指定する。
  if show_axes:
    ax.axhline(0, color="black", linewidth=0.8)
    # ax.axvline(x): 指定した x の位置に垂直線を引く
    ax.axvline(0, color="black", linewidth=0.8)

  # ax.grid(True): 目盛りに沿って格子線を表示
  ax.grid(grid)

  # ax.legend(): plot() の label に指定した内容を凡例として表示
  if legend and label:
    ax.legend()

  # fig.tight_layout(): 軸の名前などが図の外にはみ出さないように余白を調整
  fig.tight_layout()

  # 図をファイルに保存
  if save_path is not None:
    path = Path(__file__).with_name(save_path)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")

  # 呼び出し元でもタイトルの変更や追加の保存などができるように返す。
  return fig, ax
