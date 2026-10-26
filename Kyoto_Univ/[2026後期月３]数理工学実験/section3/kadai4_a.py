from utils_math import descent_kadai4
from kadai3 import f_3, grad_f_3
from utils_plot import save_txt

x, fx, k = descent_kadai4(
  f=f_3,
  grad_f=grad_f_3,
  x0=[1, 1],
)

save_txt(x, fx, k, save_path="kadai4_a.txt")