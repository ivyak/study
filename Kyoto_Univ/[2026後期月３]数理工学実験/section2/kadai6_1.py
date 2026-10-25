from pathlib import Path

import utils_math
from utils_plot import plot_f
import numpy as np
import matplotlib.pyplot as plt

import time

matrix_sizes = [10, 20, 40, 80]
output_dir = Path(__file__).with_name("figures")

for n in matrix_sizes:
  residuals: list[float] = []
  errors: list[float] = []
  times: list[float] = []
  iteration_num: list[int] = []

  for k in range(100):
    A: list[list[float]] = utils_math.make_square_matrix(n)
    # 実数のQR法で全固有値を求められるよう、対称行列を作る
    B = [[A[i][j] + A[j][i] for j in range(n)] for i in range(n)]

    start: float = time.perf_counter()
    eigenvalues, iter_num = utils_math.QR_method(B)
    times.append(time.perf_counter() - start)
    iteration_num.append(iter_num)

    B_array = np.asarray(B)
    true_values, true_vectors = np.linalg.eigh(B_array)
    # eighの固有値は昇順なので、QR法の結果も昇順に対応づける
    eigenvalues = np.sort(eigenvalues)
    residuals.append(float(max(
      np.linalg.norm(B_array @ true_vectors[:, i]
        - eigenvalues[i] * true_vectors[:, i], ord=np.inf)
      for i in range(n)
    )))
    errors.append(float(np.max(np.abs(true_values - eigenvalues) / np.abs(true_values))))
    print(f"{n}次行列, {k + 1}回目の試行")

  for metric, values, ylabel in (
      ("residual", residuals, "Maximum Residual Norm"),
      ("error", errors, "Maximum Relative Error (Eigenvalues)"),
      ("time", times, "Execution Time (s)"),
      ("iterations", iteration_num, "Number of Iterations"),
  ):
    fig, _ = plot_f(
        range(1, len(values) + 1), values,
        title=f"n = {n}: {ylabel}",
        xlabel="trials",
        ylabel=ylabel,
        yscale="linear" if metric == "iterations" else "log",
        save_path=output_dir / f"kadai6_1_n{n}_{metric}.svg",
    )
    plt.close(fig)
