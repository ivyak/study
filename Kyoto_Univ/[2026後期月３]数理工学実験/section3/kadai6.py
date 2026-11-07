import numpy as np

tolerance = 1e-10

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

    if max(primal, dual, stationarity, complementarity) <= tolerance:
      candidates.append((float(0.5 * x @ Q @ x + c @ x), x, lam))

  if not candidates:
    raise RuntimeError("KKT条件を満たす候補がない。")
  
  value, x, lam = min(candidates, key=lambda item: item[0])
  exact = np.zeros(2)
  error = float(np.linalg.norm(x - exact, np.inf))
  
  assert error <= tolerance
  return [
    x.tolist(), 
    lam.tolist(), 
    value, 
    error, 
    float(np.maximum(A @ x - b, 0).max()), 
    float(np.linalg.norm(Q @ x + c + A.T @ lam, np.inf))
  ]