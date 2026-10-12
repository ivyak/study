import os
import img2pdf
from PIL import Image

if __name__ == '__main__':
    print("PNGファイルを取得中...")
    # 出力するPDFファイル名（スクリプトと同じフォルダに出力）
    pdf_FileName = "output.pdf"

    # PNGフォルダの相対パス（同じフォルダ内の「png」フォルダ）
    png_Folder = "png_trimming_output"

    extension = ".png"

    # フォルダが存在しない場合にエラーを表示
    if not os.path.exists(png_Folder):
        print(f"指定されたフォルダが見つかりません: {png_Folder}")
        exit(1)

    # フォルダ内のPNGファイルをリストアップしてソート
    png_files = sorted([
        Image.open(os.path.join(png_Folder, j)).filename
        for j in os.listdir(png_Folder)
        if j.lower().endswith(extension)
    ])

    print("PDFに変換中...")

    # PDFを生成
    with open(pdf_FileName, "wb") as f:
        f.write(img2pdf.convert(png_files))

    print("✅ 変換完了! PDFを出力しました：", os.path.abspath(pdf_FileName))
