from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from utils_math import x_A, x_B, x_A_M, x_B_M
from utils_plot import plot_f


if __name__ == "__main__":
  # Aは周期1、Bは周期2なので、どちらも複数周期が見える範囲を選ぶ。
  t = np.linspace(-2, 2, 4001)
  M_values = [1, 5, 50]

  for name, x, x_M in [("A", x_A, x_A_M), ("B", x_B, x_B_M)]:
    y = x(t)
    if name == "A":
      # 不連続点をまたぐ線を切り、縦線で結ばれることを防ぐ。
      y[1:][np.diff(np.floor(t)) != 0] = np.nan

    fig, ax = plot_f(
      t,
      y,
      xlim=(-2, 2),
      ylim=(-0.2, 1.2),
      xlabel="t",
      ylabel="x(t)",
      title=f"Fourier series: {name}",
      label=rf"$x_{{{name}}}(t)$",
      color="black",
      save_path=None,
    )

    # plot_fが返すaxに、3通りの部分和を重ねて描く。
    for M in M_values:
      ax.plot(t, x_M(t, M), label=rf"$x_{{{name},{M}}}(t)$", linewidth=1.5)

    ax.legend()
    fig.tight_layout()
    save_path = Path(__file__).with_name(f"kadai1_b_{name}.png")
    fig.savefig(save_path, dpi=300, bbox_inches="tight")

  plt.show()
