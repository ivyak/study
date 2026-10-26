import numpy as np

from utils_math import descent_kadai4, newton_direction
from kadai3 import f_3, grad_f_3, hess_f_3
from utils_plot import save_txt


x, fx, k = descent_kadai4(
  f=f_3,
  grad_f=grad_f_3,
  x0=[1, 1],
  direction=lambda x, grad: np.linalg.solve(hess_f_3(x), -grad)
)

save_txt(x, fx, k, save_path="kadai4_b.txt")