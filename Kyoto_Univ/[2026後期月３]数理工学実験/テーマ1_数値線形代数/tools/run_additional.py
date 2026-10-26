"""本文で用いる追加実験。既存の実験・図は上書きしない。"""
from pathlib import Path
import csv
import json
import platform
import random
import sys
import time

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
SECTION = ROOT.parent / 'section2'
sys.path.insert(0, str(SECTION))
import utils_math as math


def paired():
    # 課題3の比較だけを補う。課題1・2の各100試行は既存図を用いる。
    random.seed(20261026)
    with (ROOT / 'data/paired_solvers.csv').open('w', newline='') as f:
        out = csv.writer(f)
        out.writerow(['n', 'trial', 'method', 'residual', 'error', 'time'])
        for n in [100, 200, 400, 800]:
            for trial in range(1, 4):
                A, b = math.make_square_matrix(n), math.make_vector(n)
                ref = np.linalg.solve(np.asarray(A), np.asarray(b))
                methods = [('Gaussian', math.Gaussian_elimination), ('LU', math.LU_solve)]
                for name, method in methods[::1 if trial % 2 else -1]:
                    start = time.perf_counter()
                    x = method(A, b)
                    elapsed = time.perf_counter() - start
                    out.writerow([n, trial, name, math.residual_norm_Gaussian(A, x, b), math.relative_error(ref, x), elapsed])
                    f.flush()
                print(f'paired n={n}, trial={trial}', flush=True)


def eigen():
    random.seed(20261027)
    with (ROOT / 'data/power.csv').open('w', newline='') as f:
        out = csv.writer(f)
        out.writerow(['n', 'trial', 'method', 'residual', 'eigenvalue_error', 'eigenvector_error', 'time', 'iterations', 'spectral_ratio'])
        for n in [50, 100, 200, 400]:
            for trial in range(1, 101):
                A = math.make_square_matrix(n)
                B = [[A[i][j] + A[j][i] for j in range(n)] for i in range(n)]
                start = time.perf_counter()
                value, vector, steps = math.power_method(B)
                elapsed = time.perf_counter() - start
                ref, vectors = np.linalg.eigh(np.asarray(B))
                order = np.argsort(np.abs(ref))
                i = order[-1]
                out.writerow([n, trial, 'Power method', math.residual_norm_PowerMethod(value, vector, B), math.eigenvalue_error(ref[i], value), math.eigenvector_error(vectors[:, i], vector), elapsed, steps, abs(ref[order[-2]] / ref[i])])
                f.flush()
            print(f'power n={n}: 100 trials', flush=True)
    random.seed(20261028)
    n = 100
    with (ROOT / 'data/power_inverse.csv').open('w', newline='') as f:
        out = csv.writer(f)
        out.writerow(['n', 'trial', 'method', 'residual', 'eigenvalue_error', 'eigenvector_error', 'time', 'iterations'])
        for trial in range(1, 101):
            A = np.array(math.make_square_matrix(n))
            B = A + A.T
            x0 = np.array(math.make_vector(n))
            ref, vectors = np.linalg.eigh(B)
            i = np.argmax(np.abs(ref))
            methods = [('Power method', math.power_method_numpy), ('Power + inverse', math.power_inverse_numpy)]
            for name, method in methods[::1 if trial % 2 else -1]:
                start = time.perf_counter()
                if name == 'Power + inverse':
                    value, vector, steps = method(B, x0=x0, power_iterations=4, residual_tol=1e-12)
                else:
                    value, vector, steps = method(B, x0=x0, residual_tol=1e-12)
                elapsed = time.perf_counter() - start
                out.writerow([n, trial, name, np.max(np.abs(B @ vector - value * vector)), math.eigenvalue_error(ref[i], value), math.eigenvector_error(vectors[:, i], vector), elapsed, steps])
                f.flush()
        print('power + inverse: 100 paired trials', flush=True)


if __name__ == '__main__':
    (ROOT / 'data').mkdir(exist_ok=True)
    (ROOT / 'data/environment.json').write_text(json.dumps({
        'platform': platform.platform(), 'machine': platform.machine(),
        'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__,
        'seeds': {'paired': 20261026, 'power': 20261027, 'power_inverse': 20261028},
        'clock': 'time.perf_counter', 'dtype': 'IEEE 754 binary64',
    }, indent=2, ensure_ascii=False))
    if sys.argv[1] == 'paired': paired()
    elif sys.argv[1] == 'eigen': eigen()
    else: raise SystemExit('paired または eigen を指定してください')
