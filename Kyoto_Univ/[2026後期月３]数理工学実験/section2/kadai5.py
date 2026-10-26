from pathlib import Path

import utils_math
from utils_plot import plot_f
import numpy as np
import matplotlib.pyplot as plt

import time
import random

n = 100
residual_tol = 1e-12
power_iterations = 4

output_dir = Path(__file__).with_name("figures")
output_dir.mkdir(parents=True, exist_ok=True)

methods = ("Power method", "Power + inverse")

metrics = (
    ("residual", "Residual Norm"),
    ("eigenvalue_error", "Relative Error (Eigenvalues)"),
    ("eigenvector_error", "Relative Error (Eigenvectors)"),
    ("time", "Execution Time (s)"),
    ("iterations", "Number of Iterations"),
)
results = {method: {metric: [] for metric, _ in metrics} for method in methods}

for k in range(100):
  A = np.array(utils_math.make_square_matrix(n))
  B = A + A.T
  x0 = np.array(utils_math.make_vector(n))

  true_values, true_vectors = np.linalg.eigh(B)
  i = np.argmax(np.abs(true_values))

  for method in methods[::1 if k % 2 == 0 else -1]:
    start: float = time.perf_counter()
    if method == "Power method":
      eigenvalue, eigenvector, iter_num = utils_math.power_method_numpy(B, x0=x0, residual_tol=residual_tol)
    else:
      eigenvalue, eigenvector, iter_num = utils_math.power_inverse_numpy(B, x0=x0, power_iterations=power_iterations, residual_tol=residual_tol)
    elapsed = time.perf_counter() - start

    result = results[method]
    result["time"].append(elapsed)
    result["iterations"].append(iter_num)
    result["residual"].append(np.max(np.abs(B @ eigenvector - eigenvalue * eigenvector)))
    result["eigenvalue_error"].append(utils_math.eigenvalue_error(true_values[i], eigenvalue))
    result["eigenvector_error"].append(utils_math.eigenvector_error(true_vectors[:, i], eigenvector))
  print(f"{n}次行列, {k + 1}回目の試行")

for metric, ylabel in metrics:
  fig, ax = plt.subplots()
  for method in methods:
    values = results[method][metric]
    plot_f(
        range(1, len(values) + 1), values,
        ax=ax,
        label=method,
        title=f"n = {n}: {ylabel}",
        xlabel="trials",
        ylabel=ylabel,
        yscale="linear" if metric == "iterations" else "log",
    )
  fig.savefig(output_dir / f"kadai5_n{n}_{metric}.svg", bbox_inches="tight")
  plt.close(fig)