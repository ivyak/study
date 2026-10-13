import random

# ------------------------------
# 課題1用の関数
# ------------------------------

# n次正方行列作成
def make_square_matrix(n: int):
  return [[random.random() for _ in range(n)] for _ in range(n)]

# n次元ベクトル作成
def make_vector(n: int):
  return [random.random() for _ in range(n)]

# 拡大行列の作成
def make_expansion_matrix(A: list[list[float]], b: list[float]):
  return [A[i] + [b[i]] for i in range(len(A))]

# 行列(正方行列に限らない)を行基本変形で階段行列にする
def make_ref(A: list[list[float]]):
  for i in range(len(A)): # len(A)は行数
    # ピボットの選択
    pivot_row: int = i

    # ピボットとして 0 に近いものを選ぶと，後の演算で桁落ちが起こったり
    # 情報落ちのため精度が悪化したりする可能性があるため，絶対値が最大のものを選ぶ
    # (同時にピボットが0になるのを回避)
    for j in range(i + 1, len(A)):
      if abs(A[j][i]) > abs(A[pivot_row][i]):
        # ピボット行を更新
        pivot_row = j

    # ピボット行を現在の行と入れ替える
    A[i], A[pivot_row] = A[pivot_row], A[i]

    # ピボット行を使って他の行を消去
    for j in range(i + 1, len(A)):
      if A[j][i] != 0:
        factor = A[j][i] / A[i][i]
        for k in range(i, len(A[0])):
          A[j][k] -= factor * A[i][k]
  return A

# 階段行列から漸化式で解を求める
# (Aは拡大行列であることを前提としている)
def back_substitution(A: list[list[float]]):
  n: int = len(A)
  x: list[float] = [0] * n

  for i in range(n - 1, -1, -1):
    sum_ax: float = sum(A[i][j] * x[j] for j in range(i + 1, n))
    x[i] = (A[i][-1] - sum_ax) / A[i][i]
  return x

def Gaussian_elimination(A: list[list[float]], b: list[float]):
  # 拡大行列を作成
  A_expanded: list[list[float]] = make_expansion_matrix(A, b)

  # 階段行列に変換
  A_ref: list[list[float]] = make_ref(A_expanded)

  # 後退代入で解を求める
  x: list[float] = back_substitution(A_ref)
  return x

# 無限大ノルムを求める
def infinity_norm(vector: list[float]):
  return max(abs(x) for x in vector)

# 相対誤差を求める
def relative_error(x_true, x_approx: list[float]):
  return infinity_norm([x_true[i] - x_approx[i] for i in range(len(x_true))]) / infinity_norm(x_true)

# 行列×ベクトルを求める
def matrix_vector_product(A: list[list[float]], x: list[float]):
  return [sum(A[i][j] * x[j] for j in range(len(x))) for i in range(len(A))]

# 残差ノルムを求める
def residual_norm(A: list[list[float]], x: list[float], b: list[float]):
  Ax: list[float] = matrix_vector_product(A, x)
  return infinity_norm([Ax[i] - b[i] for i in range(len(b))])

# ------------------------------
# 課題2用の関数
# ------------------------------

# 正方行列をLU分解
def LU_decomposition(A: list[list[float]]):
  n: int = len(A)
  U: list[list[float]] = [row[:] for row in A]
  L: list[list[float]] = [[1 if i == j else 0 for j in range(n)] for i in range(n)]
  P_pi: list[list[int]] = [[1 if i == j else 0 for j in range(n)] for i in range(n)]

  for i in range(n):
    pivot_row: int = i

    for j in range(i + 1, n):
      if abs(U[j][i]) > abs(U[pivot_row][i]):
        # ピボット行を更新
        pivot_row = j
    if pivot_row != i:
      U[i], U[pivot_row] = U[pivot_row], U[i]
      # Lでは計算済みの列だけを交換し、対角成分は動かさない
      L[i][:i], L[pivot_row][:i] = L[pivot_row][:i], L[i][:i]
      P_pi[i], P_pi[pivot_row] = P_pi[pivot_row], P_pi[i]

    for j in range(i + 1, n):
      factor: float = U[j][i] / U[i][i]
      L[j][i] = factor
      U[j][i] = 0
      for k in range(i + 1, n):
        U[j][k] -= factor * U[i][k]

  return L, U, P_pi

def forward_substitution_LU(L: list[list[float]], b: list[float]):
  n: int = len(L)
  y: list[float] = [0] * n

  for i in range(n):
    sum_ly: float = sum(L[i][j] * y[j] for j in range(i))
    y[i] = (b[i] - sum_ly) / L[i][i]
  return y