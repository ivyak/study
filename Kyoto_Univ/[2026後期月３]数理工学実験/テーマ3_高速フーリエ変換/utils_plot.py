from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def plot_fourier(t, x, x_M, *, M_values, name, save_path, break_at_integers=False):
  # それぞれのMについて、元の関数と部分和を横に並べて比較する。
  fig, axes = plt.subplots(
    1, len(M_values), figsize=(5 * len(M_values), 4), sharey=True,
    squeeze=False,
  )
  y = x(t)
  if break_at_integers:
    # 不連続点をまたぐ線を切り、縦線で結ばれることを防ぐ。
    y = y.copy()
    y[1:][np.diff(np.floor(t)) != 0] = np.nan

  for ax, M in zip(axes[0], M_values):
    ax.plot(t, y, color="black", label=rf"$x_{{{name}}}(t)$")
    ax.plot(t, x_M(t, M), label=rf"$x_{{{name},{M}}}(t)$", linewidth=1.5)
    ax.set_xlim(t[0], t[-1])
    ax.set_ylim(-0.2, 1.2)
    ax.set_xlabel("t")
    ax.set_title(f"{name}: M = {M}")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.grid(True)
    ax.legend()

  axes[0, 0].set_ylabel("x(t)")
  fig.tight_layout()
  if save_path is not None:
    path = Path(__file__).with_name(save_path)
    fig.savefig(path, dpi=300, bbox_inches="tight")
  return fig, axes
