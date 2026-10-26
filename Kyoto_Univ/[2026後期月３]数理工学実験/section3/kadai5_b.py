import numpy as np

from utils_math import descent_kadai4, f_5, grad_f_5, hess_f_5
from utils_plot import save_txt


x, fx, k = descent_kadai4(
  f=f_5,
  grad_f=grad_f_5,
  x0=[2, 0],
  direction=lambda x, grad: np.linalg.solve(hess_f_5(x), -grad)
)

save_txt(x, fx, k, save_path="kadai5_b.txt")