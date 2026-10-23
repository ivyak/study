from utils_math import descent, grad_f_2, newton_direction, hess_f_2
from utils_plot import save_txt

solution = descent(
  grad_f=grad_f_2,
  x0=5.0,
  t_k=lambda k: 1.0,
  direction=lambda x, grad: newton_direction(x, grad, hess_f_2)
)

save_txt(solution, save_path="Kyoto_Univ/[2026後期月３]数理工学実験/section3/kadai2_b.txt")