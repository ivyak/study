from utils_math import descent, grad_f_2
from utils_plot import save_txt

solution = descent(
  grad_f=grad_f_2,
  x0=0.5,
  t_k=lambda k: 1.0 / (k + 1)
)

save_txt(solution, save_path="kadai2_a.txt")