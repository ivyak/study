#include "utils_math.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

int main() {
  std::vector<int> matrix_sizes = {10, 20, 40, 80};
  int trial_num = 100;
  int max_iter = 10000;
  std::mt19937_64 rng(7);
  std::filesystem::create_directories("figures");
  std::ofstream out("figures/kadai7_results.csv");
  if (!out) throw std::runtime_error("CSVファイルを開けませんでした");
  out << std::setprecision(17);
  out << "n,trial,method,residual,error,time,iterations\n";

  using Method = QRResult (*)(Matrix, double, int);
  std::vector<std::pair<std::string, Method>> methods = {
      {"Original QR", QR_method_numpy},
      {"Shift + Deflation", QR_method_shift_deflation},
  };

  for (int n : matrix_sizes) {
    for (int k = 0; k < trial_num; ++k) {
      Matrix A = make_square_matrix(n, rng);
      Matrix B = A;
      for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j) B[i][j] = A[i][j] + A[j][i];
      auto [true_values, true_vectors] = eigh(B);

      // 同じ対称行列・同じ収束許容値で両方法を比較する。
      for (auto [name, method] : methods) {
        QRResult result;
        auto start = std::chrono::steady_clock::now();
        try {
          result = method(B, 1e-6, max_iter);
        } catch (const std::runtime_error& error) {
          // 未収束の試行は欠測値にして、次の方法・試行へ進む。
          out << n << ',' << k + 1 << ',' << name << ",nan,nan,nan,nan\n";
          std::cout << n << "次行列, " << k + 1 << "回目: " << name
                    << ": " << error.what() << std::endl;
          continue;
        }
        double elapsed = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - start).count();
        auto [eigenvalues, iter_num] = result;
        std::sort(eigenvalues.begin(), eigenvalues.end());
        // 参照固有ベクトルを使った最大残差と、固有値の最大相対誤差。
        double residual = 0.0;
        double error = 0.0;
        for (int i = 0; i < n; ++i) {
          for (int row = 0; row < n; ++row) {
            double Av = 0.0;
            for (int j = 0; j < n; ++j) Av += B[row][j] * true_vectors[j][i];
            residual = std::max(residual,
                std::abs(Av - eigenvalues[i] * true_vectors[row][i]));
          }
          double relative_error = std::abs(true_values[i] - eigenvalues[i])
                                / std::abs(true_values[i]);
          if (std::isnan(relative_error)) error = relative_error;
          else if (!std::isnan(error)) error = std::max(error, relative_error);
        }
        out << n << ',' << k + 1 << ',' << name << ',' << residual << ','
            << error << ',' << elapsed << ',' << iter_num << '\n';
      }
      std::cout << n << "次行列, " << k + 1 << "回目の試行" << std::endl;
    }
  }
  if (!out) throw std::runtime_error("CSVの書き込みに失敗しました");
}
