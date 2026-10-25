from pathlib import Path

import utils_math
import utils_math_kadai5
from utils_plot import plot_f
import numpy as np
import matplotlib.pyplot as plt

import time

n = 100
residual_tol = 1e-8  # 両手法を同じ精度（残差ノルム）まで計算する
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
  A: list[list[float]] = utils_math.make_square_matrix(n)
  B = [[A[i][j] + A[j][i] for j in range(n)] for i in range(n)]
  x0 = utils_math.make_vector(n)

  true_values, true_vectors = np.linalg.eigh(np.array(B))
  i = np.argmax(np.abs(true_values))

  # 同じ行列・初期ベクトルで比較し、実行順序も交互にする
  for method in methods[::1 if k % 2 == 0 else -1]:
    start: float = time.perf_counter()
    if method == "Power method":
      eigenvalue, eigenvector, iter_num = utils_math_kadai5.power_method(B, x0=x0, residual_tol=residual_tol)
    else:
      # べき乗法は粗い精度で止め、その結果から逆反復法を始める
      sigma, x, power_iter = utils_math_kadai5.power_method(B, tol=1e-2, x0=x0)
      eigenvalue, eigenvector, inverse_iter = utils_math_kadai5.inverse_iteration(B, sigma, x0=x, residual_tol=residual_tol)
      iter_num = power_iter + inverse_iter
    elapsed = time.perf_counter() - start

    result = results[method]
    result["time"].append(elapsed)
    result["iterations"].append(iter_num)
    result["residual"].append(utils_math.residual_norm_PowerMethod(eigenvalue, eigenvector, B))
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

for method in methods:
  print(f"\n{method}")
  for metric, ylabel in metrics:
    print(f"  {ylabel}: mean = {np.mean(results[method][metric]):.3e}")
print("\n平均時間の比（べき乗法 / 組み合わせ）:",
      np.mean(results[methods[0]]["time"]) / np.mean(results[methods[1]]["time"]))
