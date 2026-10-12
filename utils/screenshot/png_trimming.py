from PIL import Image
import os

input_folder = "png_trimming_input"
output_folder = "png_trimming_output"

# 切り抜き範囲をピクセル単位で指定
# 「ペイント」で座標を確認しましょう
up = 8
down = 1230
left = 556
right = 1422
crop_box = (left, up, right, down)

# 出力先フォルダがなければ作成
os.makedirs(output_folder, exist_ok=True)

for filename in os.listdir(input_folder):
    if filename.lower().endswith(".png"):
        in_path = os.path.join(input_folder, filename)
        out_path = os.path.join(output_folder, filename)

        with Image.open(in_path) as img:
            cropped = img.crop(crop_box)
            cropped.save(out_path)

        print(f"切り抜き完了: {filename}")

print("✅ すべてのPNGを切り抜きました!")