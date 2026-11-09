import matplotlib.pyplot as plt
import numpy as np

from utils_math import x_A, x_B, x_A_M, x_B_M
from utils_plot import plot_fourier


if __name__ == "__main__":
  # Aは周期1、Bは周期2なので、どちらも複数周期が見える範囲を選ぶ。
  t = np.linspace(-2, 2, 4001)
  M_values = [1, 5, 50]

  plot_fourier(
    t,
    x_A,
    x_A_M,
    M_values=M_values,
    name="A",
    save_path="kadai1_b_A.png",
    break_at_integers=True,
  )
  plot_fourier(
    t,
    x_B,
    x_B_M,
    M_values=M_values,
    name="B",
    save_path="kadai1_b_B.png",
  )
  plt.show()
