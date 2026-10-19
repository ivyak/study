import random

random.seed(0)  # 同じ行列で実験を再現する
n = 3

# ランダムな実行列
A = [[random.random() for j in range(n)] for i in range(n)]

# B = A + A^T：新しい行列として作る
B = [[A[i][j] + A[j][i] for j in range(n)] for i in range(n)]

for row in B:
    print([round(value, 3) for value in row])

print("対称か:", all(B[i][j] == B[j][i]
                      for i in range(n) for j in range(n)))
