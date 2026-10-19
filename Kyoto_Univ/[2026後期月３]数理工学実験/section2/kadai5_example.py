"""課題5：べき乗法 → 固定シフト逆反復法（utils_math.py と同じ場所で実行）。"""
import random
from statistics import median
from time import perf_counter
import utils_math as um


def normalize(x):
    size = um.infinity_norm(x)
    return [v / size for v in x]


def estimate(A, x, scale):
    Ax = um.matrix_vector_product(A, x)
    # レイリー商：負の固有値の符号も保てる
    lam = sum(x[i] * Ax[i] for i in range(len(x))) / sum(v * v for v in x)
    residual = um.infinity_norm([Ax[i] - lam * x[i] for i in range(len(x))])
    eta = residual / (scale + abs(lam))  # ||x||_inf = 1
    return lam, eta, Ax


def power(A, x0, tol=1e-10, max_iter=100000):
    scale = max(sum(abs(v) for v in row) for row in A)
    x = normalize(x0)
    for k in range(max_iter + 1):
        lam, eta, Ax = estimate(A, x, scale)
        if eta < tol:
            return lam, x, k, 0
        x = normalize(Ax)
    raise RuntimeError("べき乗法が収束しません")


def hybrid(A, x0, tol=1e-10, switch_tol=1e-3, max_iter=100000):
    scale = max(sum(abs(v) for v in row) for row in A)
    x = normalize(x0)
    # 第1段階：べき乗法で粗い固有値・固有ベクトルを得る
    for p in range(max_iter + 1):
        lam, eta, Ax = estimate(A, x, scale)
        if eta < tol:
            return lam, x, p, 0
        if eta < switch_tol:
            break
        x = normalize(Ax)
    else:
        raise RuntimeError("切替条件に達しません")

    # 第2段階：シフトを固定し、LU分解を1回だけ行う
    sigma = lam
    n = len(A)
    B = [[A[i][j] - (sigma if i == j else 0.0)
          for j in range(n)] for i in range(n)]
    L, U, P = um.LU_decomposition(B)
    for q in range(1, max_iter + 1):
        z = um.forward_substitution_LU(L, P, x)
        y = um.back_substitution_LU(U, z)
        x = normalize(y)
        lam, eta, _ = estimate(A, x, scale)
        if eta < tol:
            return lam, x, p, q
    raise RuntimeError("逆反復法が収束しません")


def measure(method, A, x0):
    times = []
    for _ in range(5):
        start = perf_counter()
        result = method(A, x0)
        times.append(perf_counter() - start)
    return result, median(times)


if __name__ == "__main__":
    random.seed(0)
    n = 50
    R = [[random.random() for _ in range(n)] for _ in range(n)]
    A = [[R[i][j] + R[j][i] for j in range(n)] for i in range(n)]
    x0 = [random.random() for _ in range(n)]

    # 2手法に同じ行列・初期ベクトル・最終許容誤差を使う
    for name, method in [("power", power), ("hybrid", hybrid)]:
        (lam, x, p, q), seconds = measure(method, A, x0)
        residual = um.residual_norm_PowerMethod(lam, x, A)
        print(f"{name}: lambda={lam:.12g}, residual={residual:.3e}, "
              f"time={seconds:.6f}s, power={p}, inverse={q}")
