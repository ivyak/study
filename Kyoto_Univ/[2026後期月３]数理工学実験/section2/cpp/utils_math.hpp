#pragma once

#include <random>
#include <utility>
#include <vector>

using Matrix = std::vector<std::vector<double>>;
using QRResult = std::pair<std::vector<double>, int>;

Matrix make_square_matrix(int n, std::mt19937_64& rng);
Matrix multiply(const Matrix& A, const Matrix& B);
std::pair<Matrix, Matrix> modified_gram_schmidt(const Matrix& A);
QRResult QR_method(Matrix A, double epsilon = 1e-6, int max_iter = 10000);
QRResult QR_method_numpy(Matrix A, double epsilon = 1e-6, int max_iter = 10000);
QRResult QR_method_shift_deflation(Matrix A, double epsilon = 1e-6, int max_iter = 10000);
// 昇順の参照固有値と、対応する固有ベクトルを列に持つ行列。
std::pair<std::vector<double>, Matrix> eigh(const Matrix& A);
