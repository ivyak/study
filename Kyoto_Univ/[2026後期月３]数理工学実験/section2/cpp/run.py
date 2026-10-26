from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
if len(sys.argv) != 2 or sys.argv[1] not in ("6_1", "7"):
    raise SystemExit("使い方: python run.py 6_1 または python run.py 7")
task = sys.argv[1]

(root / "build").mkdir(exist_ok=True)
subprocess.run([
    "c++", "-std=c++17", "-O2", "-Wall", "-Wextra",
    f"kadai{task}.cpp", "utils_math.cpp",
    "-framework", "Accelerate", "-o", f"build/kadai{task}",
], cwd=root, check=True)
subprocess.run([str(root / f"build/kadai{task}")], cwd=root, check=True)
subprocess.run([
    sys.executable, "plot_results.py", task, f"figures/kadai{task}_results.csv",
], cwd=root, check=True)
print(f"保存先: {root / 'figures'}")
