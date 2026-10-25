import random
import numpy as np

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
def residual_norm_Gaussian(A: list[list[float]], x: list[float], b: list[float]):
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
  P_pi: list[list[float]] = [[1 if i == j else 0 for j in range(n)] for i in range(n)]

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

def forward_substitution_LU(L: list[list[float]], P_pi: list[list[float]], b: list[float]):
  n: int = len(L)
  Pb: list[float] = matrix_vector_product(P_pi, b)
  y: list[float] = [0] * n

  for i in range(n):
    sum_ly: float = sum(L[i][j] * y[j] for j in range(i))
    y[i] = Pb[i] - sum_ly
  return y

def back_substitution_LU(U: list[list[float]], y: list[float]):
  n: int = len(U)
  x: list[float] = [0] * n

  for i in range(n - 1, -1, -1):
    sum_ux: float = sum(U[i][j] * x[j] for j in range(i + 1, n))
    x[i] = (y[i] - sum_ux) / U[i][i]
  return x

#LU分解を用いて連立一次方程式を解く全体の関数
def LU_solve(A: list[list[float]], b: list[float]):
  L, U, P_pi = LU_decomposition(A)
  y: list[float] = forward_substitution_LU(L, P_pi, b)
  x: list[float] = back_substitution_LU(U, y)
  return x

# ------------------------------
# 課題4用の関数
# ------------------------------

def power_method(A: list[list[float]], tol: float = 1e-6, x0=None, residual_tol=None):
  """既定では従来どおり。必要に応じて許容誤差・初期値・残差条件を指定する。"""
  x: list[float] = list(x0) if x0 is not None else [random.random() for _ in range(len(A))]
  mu: float = 0.0
  iteration_num: int = 0
  while True:
    y: list[float] = matrix_vector_product(A, x)
    iteration_num += 1

    mu_prev: float = mu
    i = max(range(len(x)), key=lambda j: abs(x[j]))
    mu: float = y[i] / x[i]

    if abs(mu - mu_prev) / abs(mu) < tol:
      if residual_tol is None or residual_norm_PowerMethod(mu, x, A) <= residual_tol:
        break

    y_norm = infinity_norm(y)
    x: list[float] = [y[i] / y_norm for i in range(len(y))]
  return mu, x, iteration_num


# 残差ノルムを求める
def residual_norm_PowerMethod(eigenvalue: float, eigenvector: list[float], A: list[list[float]]):
  Av: list[float] = matrix_vector_product(A, eigenvector)
  return infinity_norm([eigenvalue * eigenvector[i] - Av[i] for i in range(len(eigenvector))])

def eigenvalue_error(true_value: float, computed_value: float):
  return abs(true_value - computed_value) / abs(true_value)

def eigenvector_error(true_vector, eigenvector: list[float]):
    # 条件(1): 両方の最大値ノルムを1にする
    true_vector_normalized: list[float] = [x / infinity_norm(true_vector) for x in true_vector]
    eigenvector_normalized: list[float] = [x / infinity_norm(eigenvector) for x in eigenvector]

    # 条件(2): 両方でゼロでない成分番号kを選ぶ
    for k in range(len(true_vector)):
        if true_vector_normalized[k] != 0 and eigenvector_normalized[k] != 0:
            break
    else:
        raise ValueError("共通の非零成分がありません")

    # それぞれの第k成分が正になるように、ベクトル全体を反転する
    if true_vector_normalized[k] < 0:
        true_vector_normalized = [-x for x in true_vector_normalized]
    if eigenvector_normalized[k] < 0:
        eigenvector_normalized = [-x for x in eigenvector_normalized]

    return relative_error(true_vector_normalized, eigenvector_normalized)

# ------------------------------
# 課題5用の関数
# ------------------------------


def LU_decomposition_kadai5(A: list[list[float]]):
  n: int = len(A)
  U = np.array(A, dtype=float, copy=True)
  L = np.eye(n)
  P_pi = np.eye(n)

  for i in range(n):
    pivot_row = i + int(np.argmax(np.abs(U[i:, i])))
    if U[pivot_row, i] == 0:
      raise ValueError("特異行列のためLU分解で一意に解けません")
    if pivot_row != i:
      U[[i, pivot_row]] = U[[pivot_row, i]]
      # Lでは計算済みの列だけを交換し、対角成分は動かさない
      L[[i, pivot_row], :i] = L[[pivot_row, i], :i]
      P_pi[[i, pivot_row]] = P_pi[[pivot_row, i]]

    # 各行の消去係数を求め、右下の成分をまとめて更新する
    factors = U[i + 1:, i] / U[i, i]
    L[i + 1:, i] = factors
    U[i + 1:, i] = 0
    U[i + 1:, i + 1:] -= factors[:, None] * U[i, i + 1:]

  return L.tolist(), U.tolist(), P_pi.tolist()

def forward_substitution_LU_kadai5(L, P_pi, b: list[float]):
  n: int = len(L)
  L = np.asarray(L)
  # 置換行列との積は、bの成分の並べ替えで求められる
  Pb = np.asarray(b)[np.argmax(P_pi, axis=1)]
  y = np.zeros(n)

  for i in range(n):
    sum_ly = L[i, :i] @ y[:i]
    y[i] = Pb[i] - sum_ly
  return y.tolist()

def back_substitution_LU_kadai5(U, y: list[float]):
  n: int = len(U)
  U = np.asarray(U)
  x = np.zeros(n)

  for i in range(n - 1, -1, -1):
    sum_ux = U[i, i + 1:] @ x[i + 1:]
    x[i] = (y[i] - sum_ux) / U[i][i]
  return x.tolist()

def inverse_iteration(A: list[list[float]], sigma: float, x0=None, residual_tol=None):
  n: int = len(A)
  x: list[float] = list(x0) if x0 is not None else [random.random() for _ in range(n)]
  B = [[A[i][j] - (sigma if i == j else 0) for j in range(n)] for i in range(n)]
  L, U, P_pi = LU_decomposition_kadai5(B)
  L, U, P_pi = np.asarray(L), np.asarray(U), np.asarray(P_pi)
  mu: float = 0.0
  iteration_num: int = 0

  while True:
    # (1) (A - sigma I)y = x を、計算済みのLU分解で解く
    z = forward_substitution_LU_kadai5(L, P_pi, x)
    y = back_substitution_LU_kadai5(U, z)
    iteration_num += 1

    # (2) xの絶対値最大の成分を選び、muを求める
    mu_prev = mu
    i = max(range(n), key=lambda j: abs(x[j]))
    mu = y[i] / x[i]

    # (3) muが十分収束したら終了する
    if abs(mu - mu_prev) < 1e-6 * abs(mu):
      if residual_tol is None or residual_norm_PowerMethod(1 / mu + sigma, x, A) <= residual_tol:
        break

    # (4) 次の反復のベクトルを最大値ノルムで正規化する
    y_norm = infinity_norm(y)
    x = [y[i] / y_norm for i in range(n)]

  return 1 / mu + sigma, x, iteration_num

# ------------------------------
# 課題6用の関数
# ------------------------------

def modified_gram_schmidt(A):
  n = len(A)

  Q = [[0 for _ in range(n)] for _ in range(n)]
  R = [[0 for _ in range(n)] for _ in range(n)]

  for j in range(n):
    b = [A[k][j] for k in range(n)]
    # (1) 残りのベクトルbから、q_i方向の成分を順に取り除く
    for i in range(j):
      R[i][j] = sum(Q[k][i] * b[k] for k in range(n))
      b = [b[k] - R[i][j] * Q[k][i] for k in range(n)]

    # (2) r_jj = ||b||_2、q_j = b / r_jj
    R[j][j] = sum(abs(x)**2 for x in b)**0.5
    for k in range(n):
      Q[k][j] = b[k] / R[j][j]

  return Q, R


def QR_method(A, epsilon=1e-6, max_iter=10000):
  n = len(A)

  Ak = [row[:] for row in A]

  for iteration_num in range(max_iter + 1):

    # (1) 全ての狭義下三角成分を、同じ行の対角成分と比較する
    if all(abs(Ak[i][j]) <= epsilon * abs(Ak[i][i])
        for i in range(n) for j in range(i)):
      return [Ak[i][i] for i in range(n)], iteration_num
    if iteration_num == max_iter:
      break

    # (2) Ak = Qk Rk
    Q, R = modified_gram_schmidt(Ak)
    # (3) A_{k+1} = Rk Qk
    Ak = [[sum(R[i][k] * Q[k][j] for k in range(n))
      for j in range(n)] for i in range(n)]

  raise RuntimeError("最大反復回数までにQR法が収束しませんでした")
