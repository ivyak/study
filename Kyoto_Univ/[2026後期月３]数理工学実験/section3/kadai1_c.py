from utils_math import f, df, newton
from utils_plot import save_txt

solution = [
  newton(f, df, -2.5),
  newton(f, df, 0.0),
  newton(f, df, 2.5)
]

save_txt(*solution, save_path="Kyoto_Univ/[2026後期月３]数理工学実験/section3/kadai1_c.txt")