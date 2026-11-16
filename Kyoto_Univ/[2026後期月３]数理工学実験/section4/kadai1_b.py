from pathlib import Path

import numpy as np

from utils_plot import plot_f

def x_A(t):
  return t - np.floor(t)


def x_B(t):
  return np.abs(np.cos(np.pi * t / 2))


def x_A_M(t, M):
  result = 1 / 2
  for k in range(1, M + 1):
    result -= np.sin(2 * np.pi * k * t) / (np.pi * k)
  return result


def x_B_M(t, M):
  result = 2 / np.pi
  for k in range(1, M + 1):
    a_k = 4 * (-1) ** (k + 1) / (np.pi * (4 * k**2 - 1))
    result += a_k * np.cos(np.pi * k * t)
  return result

# Aは周期1、Bは周期2なので、どちらも複数周期が見える範囲を選ぶ。
t = np.linspace(-2, 2, 4000)
M_values = [1, 5, 50]

for name, x, x_M in [("A", x_A, x_A_M), ("B", x_B, x_B_M)]:
  y = x(t)
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
    linewidth=1.0,
    save_path=None,
  )

  for M in M_values:
    ax.plot(t, x_M(t, M), label=rf"$x_{{{name},{M}}}(t)$", linewidth=1.0)

  ax.legend()
  fig.tight_layout()
  save_path = Path(__file__).with_name(f"kadai1_b_{name}.png")
  fig.savefig(save_path, dpi=300, bbox_inches="tight")
