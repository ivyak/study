from utils_math import f, bisection
from utils_plot import save_txt

solution = [
  bisection(f, -5.0, -2.5),
  bisection(f, -2.5, 0.0),
  bisection(f, 0.0, 2.5)
]

save_txt(*solution, save_path="Kyoto_Univ/[2026後期月３]数理工学実験/section3/kadai1_b.txt")