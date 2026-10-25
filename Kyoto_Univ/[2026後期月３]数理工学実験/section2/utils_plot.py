from pathlib import Path

import matplotlib.pyplot as plt


def save_txt(*values, save_path):
  path = Path(save_path)

  # parents=True：途中のフォルダもまとめて作る
  path.parent.mkdir(parents=True, exist_ok=True)

  path.write_text("\n".join(str(value) for value in values), encoding="utf-8")

  return path

def plot_f(
    x,
    y,
    *,
    xlim=None,
    ylim=None,
    xlabel="x",
    ylabel="y",
    title=None,
    label=None,
    color=None,
    linewidth=1.5,
    linestyle="None",
    marker=".",
    markersize=3,
    xscale="linear",
    yscale="linear",
    figsize=(6.4, 4.8),
    ax=None,
    grid=True,
    grid_which="both",
    grid_color="gray",
    grid_alpha=0.4,
    legend=True,
    show_axes=False,
    save_path=None,
    dpi=300,
):
  """データを描画・保存し、(fig, ax) を返す。

  ax を渡すと既存の描画領域に描く。省略すると新しい図を作る。
  初期設定は点のみの描画。xlim / ylim が None なら表示範囲は自動。
  yscale="log" で縦軸、xscale="log" で横軸を対数にできる。
  linestyle="-", marker=None なら点を線で結んだグラフになる。
  markersize は点の大きさ（ポイント単位）。
  grid_which は "major"（主目盛）、"minor"（補助目盛）、"both"。
  show_axes=True で原点を通る軸を表示する（対数軸には描かない）。
  label を指定すると凡例を表示する。legend=False で非表示。
  save_path=None なら保存しない。拡張子で保存形式を選ぶ。
  dpi は PNG などの画像の解像度を指定する。
  """

  # plt.subplots(): 図全体を表す fig ・実際にグラフを描く領域 ax
  if ax is None:
    fig, ax = plt.subplots(figsize=figsize)
  else:
    fig = ax.figure

  # linestyle と marker で線・点の描画方法を指定する
  # label は凡例に表示する文字列。r"..." はバックスラッシュをそのまま扱う表記
  # $...$ は数式として表示
  ax.plot(
      x, y, label=label, color=color, linewidth=linewidth,
      linestyle=linestyle, marker=marker, markersize=markersize,
  )

  ax.set_xscale(xscale)
  ax.set_yscale(yscale)

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
  if show_axes and yscale != "log":
    ax.axhline(0, color="black", linewidth=0.8)
  if show_axes and xscale != "log":
    # ax.axvline(x): 指定した x の位置に垂直線を引く
    ax.axvline(0, color="black", linewidth=0.8)

  # ax.grid(True): 目盛りに沿って格子線を表示
  ax.set_axisbelow(True)
  if grid:
    if grid_which in ("minor", "both"):
      ax.minorticks_on()
    ax.grid(True, which=grid_which, color=grid_color, alpha=grid_alpha)
  else:
    ax.grid(False, which="both")

  # ax.legend(): plot() の label に指定した内容を凡例として表示
  if legend and label:
    ax.legend()

  # fig.tight_layout(): 軸の名前などが図の外にはみ出さないように余白を調整
  fig.tight_layout()

  # 図をファイルに保存
  if save_path is not None:
    path = Path(save_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")

  # 呼び出し元でもタイトルの変更や追加の保存などができるように返す。
  return fig, ax
