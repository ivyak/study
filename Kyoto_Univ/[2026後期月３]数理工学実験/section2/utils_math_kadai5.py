"""課題5専用。課題2・4の関数を変更せずに比較実験を行う。"""

import random
import numpy as np

from utils_math import matrix_vector_product, infinity_norm, residual_norm_PowerMethod

def LU_decomposition(A: list[list[float]]):
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

def forward_substitution_LU(L, P_pi, b: list[float]):
  n: int = len(L)
  L = np.asarray(L)
  # 置換行列との積は、bの成分の並べ替えで求められる
  Pb = np.asarray(b)[np.argmax(P_pi, axis=1)]
  y = np.zeros(n)

  for i in range(n):
    sum_ly = L[i, :i] @ y[:i]
    y[i] = Pb[i] - sum_ly
  return y.tolist()

def back_substitution_LU(U, y: list[float]):
  n: int = len(U)
  U = np.asarray(U)
  x = np.zeros(n)

  for i in range(n - 1, -1, -1):
    sum_ux = U[i, i + 1:] @ x[i + 1:]
    x[i] = (y[i] - sum_ux) / U[i][i]
  return x.tolist()

def power_method(A: list[list[float]], tol: float = 1e-6, x0=None, residual_tol=None):
  """residual_tolを指定すると、固有値の変化に加えて残差も確認する。"""
  x: list[float] = list(x0) if x0 is not None else [random.random() for _ in range(len(A))]
  mu: float = 0.0
  iteration_num: int = 0
  while True:
    y: list[float] = matrix_vector_product(A, x)
    iteration_num += 1

    mu_prev: float = mu
    i = max(range(len(x)), key=lambda j: abs(x[j]))
    mu: float = y[i] / x[i]

    if abs(mu - mu_prev) < tol * abs(mu):
      if residual_tol is None or residual_norm_PowerMethod(mu, x, A) <= residual_tol:
        break

    y_norm = infinity_norm(y)
    x: list[float] = [y[i] / y_norm for i in range(len(y))]
  return mu, x, iteration_num

def inverse_iteration(A: list[list[float]], sigma: float, x0=None, residual_tol=None):
  n: int = len(A)
  x: list[float] = list(x0) if x0 is not None else [random.random() for _ in range(n)]
  B = [[A[i][j] - (sigma if i == j else 0) for j in range(n)] for i in range(n)]
  L, U, P_pi = LU_decomposition(B)
  L, U, P_pi = np.asarray(L), np.asarray(U), np.asarray(P_pi)
  mu: float = 0.0
  iteration_num: int = 0

  while True:
    # (1) (A - sigma I)y = x を、計算済みのLU分解で解く
    z = forward_substitution_LU(L, P_pi, x)
    y = back_substitution_LU(U, z)
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
