"""課題6-4と6-5の求解、およびKKT条件・有理数による検算。"""

from fractions import Fraction as F
import json
import platform

import numpy as np


TOL = 1e-10


def solve_qp():
  Q = np.diag([2.0, 1.0])
  c = -np.ones(2)
  A = np.array([[1.0, 1.0]])
  b = np.zeros(1)
  candidates = []
  # 制約が非活性の場合と活性の場合を全て調べる。
  for active in (False, True):
    if active:
      K = np.block([[Q, A.T], [A, np.zeros((1, 1))]])
      z = np.linalg.solve(K, np.concatenate([-c, b]))
      x, lam = z[:2], z[2:]
    else:
      x = np.linalg.solve(Q, -c)
      lam = np.zeros(1)
    primal = float(np.maximum(A @ x - b, 0).max())
    dual = float(np.maximum(-lam, 0).max())
    stationarity = float(np.linalg.norm(Q @ x + c + A.T @ lam, np.inf))
    complementarity = float(np.max(np.abs(lam * (A @ x - b))))
    if max(primal, dual, stationarity, complementarity) <= TOL:
      candidates.append((float(0.5 * x @ Q @ x + c @ x), x, lam))
  if not candidates:
    raise RuntimeError("KKT条件を満たす候補がない。")
  value, x, lam = min(candidates, key=lambda item: item[0])
  exact = np.zeros(2)
  error = float(np.linalg.norm(x - exact, np.inf))
  assert error <= TOL
  return {
    "x": x.tolist(), "lambda": lam.tolist(), "objective": value,
    "analytic_error_inf": error,
    "primal_violation": float(np.maximum(A @ x - b, 0).max()),
    "stationarity_inf": float(np.linalg.norm(Q @ x + c + A.T @ lam, np.inf)),
    "status": "KKT conditions satisfied",
  }


def exact_control():
  # u = M^T (M M^T)^(-1) dを有理数で独立に計算する。
  rows = [[F(21, 10), F(1), F(0)], [F(81, 100), F(9, 10), F(1)]]
  d = [F(-2061, 100), F(-729, 1000)]
  gram = [[sum(a * b for a, b in zip(r, s)) for s in rows] for r in rows]
  det = gram[0][0] * gram[1][1] - gram[0][1] * gram[1][0]
  w = [
    (gram[1][1] * d[0] - gram[0][1] * d[1]) / det,
    (-gram[1][0] * d[0] + gram[0][0] * d[1]) / det,
  ]
  u = [sum(rows[i][j] * w[i] for i in range(2)) for j in range(3)]
  assert [sum(a * b for a, b in zip(row, u)) for row in rows] == d
  assert sum(a * b for a, b in zip([F(1), F(-21, 10), F(27, 25)], u)) == 0
  return u, sum(v * v for v in u)


def solve_control():
  A = np.array([[1.2, 1.0], [0.0, 0.9]])
  B = np.array([0.0, 1.0])
  x0 = np.array([10.0, 1.0])
  M = np.column_stack([A @ A @ B, A @ B, B])
  d = -np.linalg.matrix_power(A, 3) @ x0
  # 等式制約付き凸二次計画のKKT系を直接解く。
  K = np.block([[2 * np.eye(3), M.T], [M, np.zeros((2, 2))]])
  z = np.linalg.solve(K, np.concatenate([np.zeros(3), d]))
  u, nu = z[:3], z[3:]
  states = [x0]
  for value in u:
    states.append(A @ states[-1] + B * value)
  u_exact, value_exact = exact_control()
  error = float(np.linalg.norm(u - np.array(list(map(float, u_exact))), np.inf))
  terminal = float(np.linalg.norm(states[-1], np.inf))
  stationarity = float(np.linalg.norm(2 * u + M.T @ nu, np.inf))
  assert max(error, terminal, stationarity) <= TOL
  return {
    "M": M.tolist(), "d": d.tolist(), "u": u.tolist(),
    "u_exact": list(map(str, u_exact)), "objective": float(u @ u),
    "objective_exact": str(value_exact),
    "states": [x.tolist() for x in states], "nu": nu.tolist(),
    "analytic_error_inf": error, "terminal_error_inf": terminal,
    "equality_residual_inf": float(np.linalg.norm(M @ u - d, np.inf)),
    "stationarity_inf": stationarity, "status": "KKT conditions satisfied",
  }


if __name__ == "__main__":
  results = {
    "python": platform.python_version(), "numpy": np.__version__,
    "dtype": "float64", "tolerance": TOL,
    "qp": solve_qp(), "control": solve_control(),
  }
  print(json.dumps(results, ensure_ascii=False, indent=2))
