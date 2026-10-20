
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


# ニュートン法
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
