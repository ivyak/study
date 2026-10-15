import utils_math

for n in [100, 200, 400, 800]:
  solutions: list[list[float]] = []

  for _ in range(100):
    A: list[list[float]] = utils_math.make_square_matrix(n)
    b: list[float] = utils_math.make_vector(n)

    x: list[float] = utils_math.Gaussian_elimination(A, b)
    solutions.append(x)
