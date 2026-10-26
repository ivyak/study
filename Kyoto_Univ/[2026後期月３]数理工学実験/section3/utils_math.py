import numpy as np

# ------------------------------
# 課題1用の関数
# ------------------------------

def f(x):
  return x**3 + 2*x**2 - 5*x - 6

def df(x):
  return 3*x**2 + 4*x - 5

# 2分法
def bisection(f, a, b, epsilon=1e-12):

  # 負の値を取る端点をaにする
  if f(a) > 0:
    a, b = b, a

  # 2分法の前提条件チェック・step0
  if not (f(a) < 0 and f(b) >= 0 and epsilon > 0):
    raise ValueError("f(a) >= 0 or f(b) <= 0 or ε <= 0")

  while True:
    # step1
    c = (a + b) / 2
    fc = f(c)
    if abs(fc) <= epsilon:
      return c
    # step2
    if fc < 0:
      a = c
    else:
      b = c


# 方程式f(x)=0を解くニュートン法
def newton(f, df, x0, epsilon=1e-12):
  # step0
  if not epsilon > 0:
    raise ValueError("ε <= 0")
  x = x0

  while True:
    # step1
    derivative = df(x)
    if derivative == 0:
      raise ZeroDivisionError("df=0")
    delta_x = -f(x) / derivative

    # step2
    x = x + delta_x
    if abs(f(x)) <= epsilon:
      return x
    # step3: 更新したxでstep1へ

# ------------------------------
# 課題2用の関数
# ------------------------------

def f_2(x):
  return (x**3)/3 - x**2 - 3*x + 5/3

def grad_f_2(x):
  return x**2 - 2*x - 3

def hess_f_2(x):
  return 2*x - 2

# step2で使う最急降下方向
def steepest_direction(x, grad):
  # xは共通の呼び出し形式に合わせて受け取る
  return -grad


# step2で使うニュートン方向
def newton_direction(x, grad, hess_f):
  hess = hess_f(x)
  return -grad / hess


# 降下法
def descent(
    grad_f,
    x0,
    t_k,
    direction=steepest_direction,
    epsilon=1e-6,
    max_iter=10000
  ):
  # step0:
  if epsilon <= 0:
    raise ValueError("ε <= 0")
  if max_iter <= 0:
    raise ValueError("最大反復回数が0以下です")

  x = float(x0)

  for k in range(max_iter + 1):

    # step1
    grad: float = grad_f(x)
    if abs(grad) <= epsilon:
      return x
    if k == max_iter:
      break

    # step2
    d = direction(x, grad)

    # step3
    t = t_k(k)

    # step4
    x = x + t * d

  raise RuntimeError("最大反復回数の更新で収束しませんでした")

# ------------------------------
# 課題4用の関数
# ------------------------------

def backtracking_line_search(f, grad_f, d, x: list[float], t0: float, xi: float, rho: float):
  # Step 0: ξ ∈ (0, 1)，ρ ∈ (0, 1)，初期ステップサイズ t0 > 0 を選ぶ．t = t0とする．
  t = t0
  # Step 1: 次式を満たすまで t ← ρ t とする．
  while f(x + t * d) > f(x) + xi * t * np.dot(grad_f(x), d):
    t *= rho
  # Step 2: tk = t として終了
  return t

def norm_2(x):
  return np.sqrt(np.sum(np.array(x)**2))

# 降下法
def descent_kadai4(
    f,
    grad_f,
    x0,
    direction=steepest_direction,
    epsilon=1e-6,
    max_iter=10000
  ):
  # step0:
  if epsilon <= 0:
    raise ValueError("ε <= 0")
  if max_iter <= 0:
    raise ValueError("最大反復回数が0以下です")

  x = x0
  for k in range(max_iter + 1):

    # step1
    grad: list[float] = grad_f(x)
    if norm_2(grad) <= epsilon:
      return x, f(x), k
    if k == max_iter:
      break

    # step2
    d = direction(x, grad)

    # step3
    t = backtracking_line_search(f, grad_f, d, x, t0=1.0, xi=1e-4, rho=0.5)

    # step4
    x = x + t * d

  raise RuntimeError("最大反復回数の更新で収束しませんでした")


# ------------------------------
# 課題5用の関数
# ------------------------------

def f_5(x):
  a, b = x
  f0 = 1.5 - a * (1 - b)
  f1 = 2.25 - a * (1 - b**2)
  f2 = 2.625 - a * (1 - b**3)
  return f0**2 + f1**2 + f2**2


def grad_f_5(x):
  a, b = x
  f0 = 1.5 - a * (1 - b)
  f1 = 2.25 - a * (1 - b**2)
  f2 = 2.625 - a * (1 - b**3)
  return np.array([
    2 * (f0 * (b - 1) + f1 * (b**2 - 1) + f2 * (b**3 - 1)),
    2 * (f0 * a + f1 * 2 * a * b + f2 * 3 * a * b**2),
  ])


def hess_f_5(x):
  a, b = x
  f0 = 1.5 - a * (1 - b)
  f1 = 2.25 - a * (1 - b**2)
  f2 = 2.625 - a * (1 - b**3)

  h00 = 2 * ((b - 1)**2 + (b**2 - 1)**2 + (b**3 - 1)**2)
  h01 = 2 * (
    f0 + a * (b - 1)
    + 2 * b * f1 + 2 * a * b * (b**2 - 1)
    + 3 * b**2 * f2 + 3 * a * b**2 * (b**3 - 1)
  )
  h11 = 2 * (a**2 + 2 * a * f1 + (2 * a * b)**2
             + 6 * a * b * f2 + (3 * a * b**2)**2)
  return np.array([[h00, h01], [h01, h11]])
