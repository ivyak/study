# https://atcoder.jp/contests/abc476/tasks/abc476_c

N = int(input())
A = list(map(int, input().split()))
T = input()

match = True

for i in range(N):
    if S[i] == T[i] or T[i] == r"*":
        continue
    else:
        match = False

if match: 
    print("Yes")
else:
    print("No")
