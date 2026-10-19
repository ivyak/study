import utils_math
import numpy as np
import matplotlib.pyplot as plt

import time

for row, n in enumerate([50, 100, 200, 400]):
  residuals: list[float] = []
  eigenvalues_errors: list[float] = []
  eigenvectors_errors: list[float] = []
  times: list[float] = []
  iteration_num = []


  for _ in range(100):
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

  for col, (values, title) in enumerate([
    (residuals, "Residual Norm"),
    (eigenvalues_errors, "Relative Error (Eigenvalues)"),
    (eigenvectors_errors, "Relative Error (Eigenvectors)"),
    (times, "Execution Time"),
    (iteration_num, "Number of Iterations")
  ]):
      ax = plt.subplot(4, 5, row * 5 + col + 1)
      ax.plot(range(1, 101), values)
      ax.set_title(f"n = {n}: {title}")
      ax.set_xlabel("試行番号")

plt.tight_layout()
plt.show()