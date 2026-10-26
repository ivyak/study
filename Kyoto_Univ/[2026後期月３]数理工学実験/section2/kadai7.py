from pathlib import Path

import utils_math
from utils_plot import plot_f
import numpy as np
import matplotlib.pyplot as plt

import time

matrix_sizes = [10, 20, 40, 80]
trial_num = 100
output_dir = Path(__file__).with_name("figures")
output_dir.mkdir(exist_ok=True)
methods = {"Original QR": utils_math.QR_method_numpy,
  "Shift + Deflation": utils_math.QR_method_shift_deflation}

for n in matrix_sizes:
  results = {name: {metric: [] for metric in
    ("residual", "error", "time", "iterations")}
    for name in methods}

  for k in range(trial_num):
    A = np.array(utils_math.make_square_matrix(n))
    B = A + A.T
    true_values, true_vectors = np.linalg.eigh(B)

    # 同じ対称行列・同じ収束許容値で両方法を比較する。
    for name, method in methods.items():

      start = time.perf_counter()
      try:
        eigenvalues, iter_num = method(B)
      except RuntimeError:
        # 最大反復回数に達した試行は欠測値にして、次の計算へ進む。
        for values in results[name].values():
          values.append(np.nan)
        print(f"{n}次行列, {k + 1}回目: {name} は収束しませんでした")
        continue
      elapsed = time.perf_counter() - start

      eigenvalues = np.sort(eigenvalues)

      results[name]["time"].append(elapsed)
      results[name]["iterations"].append(iter_num)

      # 参照固有ベクトルを使った最大残差と、固有値の最大相対誤差。
      results[name]["residual"].append(max(
        np.linalg.norm(B @ true_vectors[:, i]
          - eigenvalues[i] * true_vectors[:, i], ord=np.inf)
        for i in range(n)
      ))
      results[name]["error"].append(
        np.max(np.abs(true_values - eigenvalues) / np.abs(true_values)))

    print(f"{n}次行列, {k + 1}回目の試行")

  for metric, ylabel in (
    ("residual", "Maximum Residual Norm"),
    ("error", "Maximum Relative Error (Eigenvalues)"),
    ("time", "Execution Time (s)"),
    ("iterations", "Number of Iterations"),
  ):
    fig, ax = plt.subplots()
    for name in methods:
      plot_f(
        range(1, trial_num + 1), results[name][metric],
        title=f"n = {n}: {ylabel}",
        xlabel="trials", ylabel=ylabel, label=name, ax=ax,
        yscale="linear" if metric == "iterations" else "log",
      )
    fig.savefig(output_dir / f"kadai7_n{n}_{metric}.svg",
      bbox_inches="tight")
    plt.close(fig)
