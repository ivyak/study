"""C++の計算結果を、元の課題6・7と同じutils_plotで描く。"""

import argparse
import csv
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils_plot import plot_f


def plot_results(csv_path, task, output_dir):
    with Path(csv_path).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    methods = ["QR"] if task == "6_1" else ["Original QR", "Shift + Deflation"]
    for n in dict.fromkeys(int(row["n"]) for row in rows):
        for metric, ylabel in (
            ("residual", "Maximum Residual Norm"),
            ("error", "Maximum Relative Error (Eigenvalues)"),
            ("time", "Execution Time (s)"),
            ("iterations", "Number of Iterations"),
        ):
            save_path = output_dir / f"kadai{task}_n{n}_{metric}.svg"
            yscale = "linear" if metric == "iterations" else "log"
            if task == "6_1":
                data = [row for row in rows if int(row["n"]) == n]
                fig, _ = plot_f(
                    [int(row["trial"]) for row in data],
                    [float(row[metric]) for row in data],
                    title=f"n = {n}: {ylabel}", xlabel="trials", ylabel=ylabel,
                    yscale=yscale, save_path=save_path,
                )
            else:
                fig, ax = plt.subplots()
                for name in methods:
                    data = [row for row in rows
                            if int(row["n"]) == n and row["method"] == name]
                    plot_f(
                        [int(row["trial"]) for row in data],
                        [float(row[metric]) for row in data],
                        title=f"n = {n}: {ylabel}", xlabel="trials", ylabel=ylabel,
                        label=name, ax=ax, yscale=yscale,
                    )
                fig.savefig(save_path, bbox_inches="tight")
            plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=["6_1", "7"])
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "figures")
    args = parser.parse_args()
    plot_results(args.csv, args.task, args.output_dir)
