# pyautogui ... マウスやキーボードを自動で操作するためのライブラリ
# 画像処理のためにpillowも必要なので pip install pyautogui pillow でダウンロード
import pyautogui 
import time
import datetime
import os

# 保存先フォルダを作成
save_dir = "png_trimming_input" #保存ファイル名 
os.makedirs(save_dir, exist_ok=True)

INTERVAL = int(input("スクリーンショット間隔(秒)："))
REPEAT = int(input("ページの枚数(0なら無限ループ)："))

print("15秒後に開始します。ウィンドウを整えてください。")
time.sleep(15)

for i in range(REPEAT if REPEAT > 0 else 9999999):
    # スクリーンショットを取得
    screenshot = pyautogui.screenshot()
    filename = os.path.join(
        save_dir, f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    )
    screenshot.save(filename)
    print(f"[{i+1}] スクリーンショットを保存しました → {filename}")

    # →を押す
    pyautogui.press('right')

    # 次のループまで待機
    time.sleep(INTERVAL)

print("✅ 撮影が完了しました")