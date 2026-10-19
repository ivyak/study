import utils_math

for n in [50, 100, 200, 400]:
  eigenvalues: list[float] = []
  eigenvectors: list[list[float]] = []

  for _ in range(100):
    A: list[list[float]] = utils_math.make_square_matrix(n)
    B = [[A[i][j] + A[j][i] for j in range(n)] for i in range(n)]


    eigenvalue, eigenvector, _ = utils_math.power_method(B)
    eigenvalues.append(eigenvalue)
    eigenvectors.append(eigenvector)
