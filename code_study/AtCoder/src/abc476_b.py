# https://atcoder.jp/contests/abc476/tasks/abc476_b

N = int(input())
S = input()
T = input()

match = True

for i in range(N):
    if S[i] == T[i] or T[i] == "*":
        continue
    else:
        match = False

if match: 
    print("Yes")
else:
    print("No")
