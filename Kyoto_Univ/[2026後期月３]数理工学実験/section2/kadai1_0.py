import utils_math
import numpy as np

n: list[int] = [100, 200, 400, 800]

for i in n:
  A_list: list[list[list[float]]] = [utils_math.make_square_matrix(n[i]) for _ in range(100)]
  b_list: list[list[float]] = [utils_math.make_vector(n[i]) for _ in range(100)]

  x_list: list[list[float]] = [utils_math.Gaussian_elimination(A_list[j], b_list[j]) for j in range(100)]
