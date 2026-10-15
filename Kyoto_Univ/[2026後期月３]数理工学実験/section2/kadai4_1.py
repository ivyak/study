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

    start: float = time.perf_counter()
    eigenvalue, eigenvector = utils_math.power_method(A)
    times.append(time.perf_counter() - start)

    x_true = np.linalg.solve(np.asarray(A), np.asarray(b))
    residuals.append(utils_math.residual_norm_PowerMethod(eigenvalue, eigenvector, A))
    eigenvalues_errors.append(utils_math.relative_error_Gaussian(x_true, x))

  for col, (values, title) in enumerate([
      (residuals, "Residual Norm"),
      (errors, "Relative Error"),
      (times, "Execution Time"),
  ]):
      ax = plt.subplot(4, 3, row * 3 + col + 1)
      ax.plot(range(1, 101), values)
      ax.set_title(f"n = {n}: {title}")
      ax.set_xlabel("試行番号")

plt.tight_layout()
plt.show()