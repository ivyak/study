# https://atcoder.jp/contests/abc401/tasks/abc401_b

N = int(input())

S = [input() for _ in range(N)]

status = "logout"

error_count = 0

for s in S:
    if s == "login":
        status = s
    if s == "logout":
            status = s
    if s == "private":
        if status == "logout":
            error_count += 1

print(error_count)
