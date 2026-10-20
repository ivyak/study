import numpy as np

from utils_math import f
from utils_plot import plot_f


# np.linspace(開始値, 終了値, 点数): 両端を含めて等間隔に並ぶ数値の配列
x = np.linspace(-10, 10, 1000)

plot_f(
  x, 
  f(x),
  title="Graph of $f(x) = x^3 + 2x^2 - 5x - 6$",
  save_path="Kyoto_Univ/[2026後期月３]数理工学実験/section3/kadai1_a.svg"
)
