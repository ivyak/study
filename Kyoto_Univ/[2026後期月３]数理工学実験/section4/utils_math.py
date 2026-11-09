import numpy as np


def x_A(t):
  t = np.array(t, dtype=float)
  return t - np.floor(t)


def x_B(t):
  t = np.array(t, dtype=float)
  return np.abs(np.cos(np.pi * t / 2))


def x_A_M(t, M):
  t = np.array(t, dtype=float)
  result = np.full_like(t, 1 / 2)
  for k in range(1, M + 1):
    result -= np.sin(2 * np.pi * k * t) / (np.pi * k)
  return result


def x_B_M(t, M):
  t = np.array(t, dtype=float)
  result = np.full_like(t, 2 / np.pi)
  for k in range(1, M + 1):
    a_k = 4 * (-1) ** (k + 1) / (np.pi * (4 * k**2 - 1))
    result += a_k * np.cos(np.pi * k * t)
  return result
