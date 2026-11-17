from math import sqrt, log10

from utils_plot import save_txt

# Step 0
x: list[complex] = [1, 1, 1, 1, 0, 0, 0, 0]
X_abr: list[complex] = [0] * len(x)
X_ab: list[complex] = [0] * len(x)
X_a: list[complex] = [0] * len(x)
X: list[complex] = [0] * len(x)

for n in range(len(x)):
  # 数列xの添字を2進数に変換して、ビット反転
  bin_reverse = []
  bin_reverse.append(n % 2)
  bin_reverse.append((n // 2) % 2)
  bin_reverse.append(((n // 2) // 2) % 2)

  # ビット反転した2進数を10進数に戻して新しい数列Xのアドレスにする
  address = bin_reverse[0] * 4 + bin_reverse[1] * 2 + bin_reverse[2]
  # 対象のアドレスにx_nを代入
  X_abr[address] = x[n]

#step1
for n in range(0, len(X_abr), 2):
  X_ab[n] = X_abr[n] + X_abr[n + 1]
  X_ab[n + 1] = X_abr[n] - X_abr[n + 1]

#step2
for n in range(0, len(X_ab), 4):
  X_a[n] = X_ab[n] + X_ab[n + 2]
  X_a[n + 2] = X_ab[n] - X_ab[n + 2]
  X_a[n + 1] = X_ab[n + 1] + (-1j) * X_ab[n + 3]
  X_a[n + 3] = X_ab[n + 1] - (-1j) * X_ab[n + 3]

#step3
for n in range(0, len(X_a), 8):
  X[n] = X_a[n] + X_a[n + 4]
  X[n + 4] = X_a[n] - X_a[n + 4]
  X[n + 2] = X_a[n + 2] + (-1j) * X_a[n + 6]
  X[n + 6] = X_a[n + 2] - (-1j) * X_a[n + 6]
  X[n + 1] = X_a[n + 1] + ((1 - 1j) / (2 ** 0.5)) * X_a[n + 5]
  X[n + 5] = X_a[n + 1] - ((1 - 1j) / (2 ** 0.5)) * X_a[n + 5]
  X[n + 3] = X_a[n + 3] + ((-1 - 1j) / (2 ** 0.5)) * X_a[n + 7]
  X[n + 7] = X_a[n + 3] - ((-1 - 1j) / (2 ** 0.5)) * X_a[n + 7]

save_txt(X, save_path="kadai2_b_fourier_transform_output.txt")

# 最大誤差の評価
X_ideal = [
  4,
  1 - (sqrt(2) + 1) * 1j,
  0,
  1 - (sqrt(2) - 1) * 1j,
  0,
  1 + (sqrt(2) - 1) * 1j,
  0,
  1 + (sqrt(2) + 1) * 1j
]

maximum_error = max([abs(x - y) for x, y in zip(X, X_ideal)])
save_txt(maximum_error, save_path="kadai2_b_maximum_error.txt")

K = -log10(maximum_error)
save_txt(K, save_path="kadai2_b_range.txt")
