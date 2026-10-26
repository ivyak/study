#include "utils_math.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

// LAPACKの倍精度・32 bit整数インターフェース。
// macOS付属のAccelerateにリンクする。
extern "C" {
void dgeqrf_(int*, int*, double*, int*, double*, double*, int*, int*);
void dorgqr_(int*, int*, int*, double*, int*, double*, double*, int*, int*);
void dsyev_(char*, char*, int*, double*, int*, double*, double*, int*, int*);
}

Matrix make_square_matrix(int n, std::mt19937_64& rng) {
  std::uniform_real_distribution<double> uniform(0.0, 1.0);
  Matrix A(n, std::vector<double>(n));
  for (auto& row : A)
    for (double& value : row) value = uniform(rng);
  return A;
}

Matrix multiply(const Matrix& A, const Matrix& B) {
  int n = static_cast<int>(A.size());
  Matrix C(n, std::vector<double>(n, 0.0));
  for (int i = 0; i < n; ++i)
    for (int j = 0; j < n; ++j)
      for (int k = 0; k < n; ++k) C[i][j] += A[i][k] * B[k][j];
  return C;
}

// ------------------------------
// 課題6用の関数
// ------------------------------

std::pair<Matrix, Matrix> modified_gram_schmidt(const Matrix& A) {
  int n = static_cast<int>(A.size());
  Matrix Q(n, std::vector<double>(n, 0.0)), R = Q;
  for (int j = 0; j < n; ++j) {
    std::vector<double> b(n);
    for (int k = 0; k < n; ++k) b[k] = A[k][j];
    for (int i = 0; i < j; ++i) {
      for (int k = 0; k < n; ++k) R[i][j] += Q[k][i] * b[k];
      for (int k = 0; k < n; ++k) b[k] -= R[i][j] * Q[k][i];
    }
    for (double x : b) R[j][j] += x * x;
    R[j][j] = std::sqrt(R[j][j]);
    if (R[j][j] == 0.0) throw std::runtime_error("QR分解でゼロ除算が発生しました");
    for (int k = 0; k < n; ++k) Q[k][j] = b[k] / R[j][j];
  }
  return {Q, R};
}

static bool converged(const Matrix& A, double epsilon) {
  for (int i = 0; i < static_cast<int>(A.size()); ++i)
    for (int j = 0; j < i; ++j)
      if (!(std::abs(A[i][j]) <= epsilon * std::abs(A[i][i]))) return false;
  return true;
}

static std::vector<double> diagonal(const Matrix& A) {
  std::vector<double> values(A.size());
  for (int i = 0; i < static_cast<int>(A.size()); ++i) values[i] = A[i][i];
  return values;
}

QRResult QR_method(Matrix A, double epsilon, int max_iter) {
  for (int iteration = 0; iteration <= max_iter; ++iteration) {
    if (converged(A, epsilon)) return {diagonal(A), iteration};
    if (iteration == max_iter) break;
    auto [Q, R] = modified_gram_schmidt(A);
    A = multiply(R, Q);
  }
  throw std::runtime_error("最大反復回数までにQR法が収束しませんでした");
}

// ------------------------------
// 課題7用の関数
// ------------------------------

// NumPyのlinalg.qrと同じくHouseholder法（LAPACK）でQR分解する。
static std::pair<Matrix, Matrix> lapack_qr(const Matrix& A) {
  int n = static_cast<int>(A.size()), info;
  int lwork = 64 * n;  // LAPACKが使う作業領域（必要な最小サイズ以上）。
  std::vector<double> a(n * n), tau(n), work(lwork);
  for (int i = 0; i < n; ++i)
    for (int j = 0; j < n; ++j) a[i + j * n] = A[i][j];
  dgeqrf_(&n, &n, a.data(), &n, tau.data(), work.data(), &lwork, &info);
  if (info != 0) throw std::runtime_error("dgeqrf failed");
  Matrix Q(n, std::vector<double>(n)), R(n, std::vector<double>(n, 0.0));
  for (int i = 0; i < n; ++i)
    for (int j = i; j < n; ++j) R[i][j] = a[i + j * n];
  dorgqr_(&n, &n, &n, a.data(), &n, tau.data(), work.data(), &lwork, &info);
  if (info != 0) throw std::runtime_error("dorgqr failed");
  for (int i = 0; i < n; ++i)
    for (int j = 0; j < n; ++j) Q[i][j] = a[i + j * n];
  return {Q, R};
}

QRResult QR_method_numpy(Matrix A, double epsilon, int max_iter) {
  for (int iteration = 0; iteration <= max_iter; ++iteration) {
    if (converged(A, epsilon)) return {diagonal(A), iteration};
    if (iteration == max_iter) break;
    auto [Q, R] = lapack_qr(A);
    A = multiply(R, Q);
  }
  throw std::runtime_error("最大反復回数までにQR法が収束しませんでした");
}

QRResult QR_method_shift_deflation(Matrix A, double epsilon, int max_iter) {
  std::vector<double> values;
  int iteration = 0;
  while (A.size() > 1) {
    int n = static_cast<int>(A.size());
    bool last_row_converged = true;
    for (int j = 0; j < n - 1; ++j)
      if (!(std::abs(A[n - 1][j]) <= epsilon * std::abs(A[n - 1][n - 1])))
        last_row_converged = false;
    // 式 (2.17) を満たしたら、右下成分を固有値として採用して減次する。
    if (last_row_converged) {
      values.push_back(A.back().back());
      A.pop_back();
      for (auto& row : A) row.pop_back();
      continue;
    }
    if (iteration >= max_iter)
      throw std::runtime_error("最大反復回数までにQR法が収束しませんでした");
    double sigma = A.back().back();
    for (int i = 0; i < n; ++i) A[i][i] -= sigma;
    auto [Q, R] = lapack_qr(A);
    A = multiply(R, Q);
    for (int i = 0; i < n; ++i) A[i][i] += sigma;
    ++iteration;
  }
  values.push_back(A[0][0]);
  return {values, iteration};
}

std::pair<std::vector<double>, Matrix> eigh(const Matrix& A) {
  int n = static_cast<int>(A.size()), info;
  int lwork = 64 * n;  // LAPACKが使う作業領域（必要な最小サイズ以上）。
  std::vector<double> a(n * n), values(n), work(lwork);
  for (int i = 0; i < n; ++i)
    for (int j = 0; j < n; ++j) a[i + j * n] = A[i][j];
  char jobz = 'V', uplo = 'L';
  dsyev_(&jobz, &uplo, &n, a.data(), &n, values.data(), work.data(), &lwork, &info);
  if (info != 0) throw std::runtime_error("参照固有値の計算に失敗しました");
  Matrix vectors(n, std::vector<double>(n));
  for (int i = 0; i < n; ++i)
    for (int j = 0; j < n; ++j) vectors[i][j] = a[i + j * n];
  return {values, vectors};
}
