import utils_math, utils_others
import numpy as np
import matplotlib.pyplot as plt

n: list[int] = [100, 200, 400, 800]

for i in n:
  A_list: list[list[list[float]]] = [utils_math.make_square_matrix(i) for _ in range(100)]
  b_list: list[list[float]] = [utils_math.make_vector(i) for _ in range(100)]

  A_list_true = np.array(A_list)
  b_list_true = np.array(b_list)

  execution_times = [utils_others.get_execution_time(lambda: utils_math.Gaussian_elimination(A_list[j], b_list[j])) for j in range(100)]

  x_list: list[list[float]] = [utils_math.Gaussian_elimination(A_list[j], b_list[j]) for j in range(100)]
  x_list_true = [np.linalg.solve(A_list_true[j], b_list_true[j]) for j in range(100)]

  for j in range(100):
    plt.subplot(1, 3, 1)
    plt.plot(i, utils_math.residual_norm(A_list[j], x_list[j], b_list[j]), label='Residual Norm')
    plt.subplot(1, 3, 2)
    plt.plot(i, utils_math.relative_error(x_list[j], x_list_true[j]), label='Error Norm')
    plt.subplot(1, 3, 3)
    plt.plot(i, execution_times[j], label='Execution Time')

plt.show()