
def f(x):
  return x**3 + 2*x**2 - 5*x - 6


# 2分法
def bisection(f, a, b, epsilon=1e-12):

  # 2分法の前提条件チェック・step0
  if not (a < b and f(a) < 0 and f(b) >= 0 and epsilon > 0):
    raise ValueError("a < b, f(a) < 0, f(b) >= 0, epsilon > 0 を満たしていません")

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
    raise ValueError("epsilon > 0 を満たしていません")
  x = x0

  while True:
    # step1
    derivative = df(x)
    if derivative == 0:
      raise ZeroDivisionError("導関数が0です")
    delta_x = -f(x) / derivative

    # step2
    x = x + delta_x
    if abs(f(x)) <= epsilon:
      return x
    # step3: 更新したxでstep1へ
