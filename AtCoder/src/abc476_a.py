# https://atcoder.jp/contests/abc476/tasks/abc476_a

S = input()

if S[-1] == "e":
    T = S + "r"
else:
    T = S + "er"

print(T)
