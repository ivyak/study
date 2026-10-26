import numpy as np

from utils_math import descent_kadai4, f_5, grad_f_5, hess_f_5
from utils_plot import save_txt

def modified_newton_direction(x, grad):
  H = hess_f_5(x)
  # np.linalg.eigvalsh: 固有値を昇順で返す。Hは対称行列なのでeigvalshを使用
  lambda_min = np.linalg.eigvalsh(H)[0]

  # lambda_min > 0 ⇔ Hは正定値行列
  tau = 0.0 if lambda_min > 0 else -lambda_min + 1e-2

  # np.eye(H.shape[0]): 単位行列を作る。H.shape[0]はHの行数
  # (∇^2 f(x_k) + τ I)d_k = −∇f(x_k) をd_kについて解く
  return np.linalg.solve(H + tau * np.eye(H.shape[0]), -grad)


x, fx, k = descent_kadai4(
  f=f_5,
  grad_f=grad_f_5,
  x0=[2, 0],
  direction=lambda x, grad: modified_newton_direction(x, grad)
)

save_txt(x, fx, k, save_path="kadai5_b.txt")
