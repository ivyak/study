from utils_math import descent_kadai4, f_5, grad_f_5
from utils_plot import save_txt


x, fx, k = descent_kadai4(
  f=f_5,
  grad_f=grad_f_5,
  x0=[2, 0],
)

save_txt(x, fx, k, save_path="kadai5_a.txt")