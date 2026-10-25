from pathlib import Path

import utils_math
from utils_plot import plot_f
import numpy as np
import matplotlib.pyplot as plt

import time

matrix_sizes = [100, 200, 400, 800]
output_dir = Path(__file__).with_name("figures")

for n in matrix_sizes:
  residuals: list[float] = []
  errors: list[float] = []
  times: list[float] = []

  for i in range(100):
    A: list[list[float]] = utils_math.make_square_matrix(n)
    b: list[float] = utils_math.make_vector(n)

    start: float = time.perf_counter()
    x: list[float] = utils_math.Gaussian_elimination(A, b)
    times.append(time.perf_counter() - start)

    x_true = np.linalg.solve(np.asarray(A), np.asarray(b))
    residuals.append(utils_math.residual_norm_Gaussian(A, x, b))
    errors.append(utils_math.relative_error(x_true, x))
    print(f"{n}次行列, {i + 1}回目の試行")

  for metric, values, ylabel in (
      ("residual", residuals, "Residual Norm"),
      ("error", errors, "Relative Error"),
      ("time", times, "Execution Time (s)"),
  ):
    fig, _ = plot_f(
        range(1, len(values) + 1), values,
        title=f"n = {n}: {ylabel}",
        xlabel="trials",
        ylabel=ylabel,
        yscale="log",
        save_path=output_dir / f"kadai1_1_n{n}_{metric}.svg",
    )
    plt.close(fig)
