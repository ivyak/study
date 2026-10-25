from pathlib import Path

import utils_math
from utils_plot import plot_f
import numpy as np
import matplotlib.pyplot as plt

import time

matrix_sizes = [50, 100, 200, 400]
output_dir = Path(__file__).with_name("figures")

for n in matrix_sizes:
  residuals: list[float] = []
  eigenvalues_errors: list[float] = []
  eigenvectors_errors: list[float] = []
  times: list[float] = []
  iteration_num = []


  for k in range(100):
    A: list[list[float]] = utils_math.make_square_matrix(n)
    B = [[A[i][j] + A[j][i] for j in range(n)] for i in range(n)]

    start: float = time.perf_counter()
    eigenvalue, eigenvector, iter_num = utils_math.power_method(B)
    times.append(time.perf_counter() - start)
    iteration_num.append(iter_num)

    true_values, true_vectors = np.linalg.eig(np.array(B))
    i = np.argmax(np.abs(true_values))  # 第1固有値のインデックスを取得

    residuals.append(utils_math.residual_norm_PowerMethod(eigenvalue, eigenvector, B))
    eigenvalues_errors.append(utils_math.eigenvalue_error(true_values[i], eigenvalue))
    eigenvectors_errors.append(utils_math.eigenvector_error(true_vectors[:, i], eigenvector))
    print(f"{n}次行列, {k + 1}回目の試行")

  for metric, values, ylabel in (
      ("residual", residuals, "Residual Norm"),
      ("eigenvalue_error", eigenvalues_errors, "Relative Error (Eigenvalues)"),
      ("eigenvector_error", eigenvectors_errors, "Relative Error (Eigenvectors)"),
      ("time", times, "Execution Time (s)"),
      ("iterations", iteration_num, "Number of Iterations"),
  ):
    fig, _ = plot_f(
        range(1, len(values) + 1), values,
        title=f"n = {n}: {ylabel}",
        xlabel="trials",
        ylabel=ylabel,
        yscale="linear" if metric == "iterations" else "log",
        save_path=output_dir / f"kadai4_1_n{n}_{metric}.svg",
    )
    plt.close(fig)
