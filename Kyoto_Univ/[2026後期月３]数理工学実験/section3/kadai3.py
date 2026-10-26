import numpy as np

def f_3(x):
  x0, x1 = x
  return x0**2 + np.exp(x0) + x1**4 + x1**2 - 2*x0*x1 + 3

def grad_f_3(x):
  x0, x1 = x
  return np.array([2*x0 + np.exp(x0) - 2*x1, 4*x1**3 + 2*x1 - 2*x0])

def hess_f_3(x):
  x0, x1 = x
  f00 = 2 + np.exp(x0)
  f01 = -2
  f10 = -2
  f11 = 12*x1**2 + 2
  return np.array([[f00, f01], [f10, f11]])