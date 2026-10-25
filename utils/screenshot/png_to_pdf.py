"""Convert a folder's PNG files into PDF pages in filename order."""

import argparse
from pathlib import Path

import img2pdf


def main():
    parser = argparse.ArgumentParser(description="フォルダ直下のPNGを名前順に1画像1ページのPDFに変換")
    parser.add_argument("folder", nargs="?", type=Path, help="PNGフォルダ（省略時: png_trimming_output）")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("-o", "--output", type=Path, help="出力PDFのパス")
    destination.add_argument("-n", "--name", help="入力フォルダ内に保存するPDF名（.pdfは省略可）")
    parser.add_argument("--overwrite", action="store_true", help="既存の出力PDFを上書きする")
    args = parser.parse_args()

    folder = args.folder if args.folder is not None else Path("png_trimming_output")
    if args.name is not None:
        if not args.name.strip() or args.name in {".", ".."} or "/" in args.name or "\\" in args.name:
            parser.error("--nameにはフォルダを含まないファイル名を指定してください（パス指定は --output）")
        name = args.name if args.name.lower().endswith(".pdf") else args.name + ".pdf"
        args.output = folder / name
    output = args.output if args.output is not None else (
        folder / "output.pdf" if args.folder is not None else Path("output.pdf")
    )
    if not folder.is_dir():
        parser.error(f"指定されたフォルダが見つかりません: {folder}")
    png_files = sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".png"),
        key=lambda p: p.name,
    )
    if not png_files:
        parser.error(f"PNGファイルがありません: {folder}")
    if output.exists() and not args.overwrite:
        parser.error(f"出力先が既に存在します: {output}（上書きする場合は --overwrite）")
    if not output.parent.is_dir():
        parser.error(f"出力先の親フォルダが見つかりません: {output.parent}")
    if output.resolve() in {p.resolve() for p in png_files}:
        parser.error("入力PNGと同じパスには出力できません")

    print(f"PNG {len(png_files)}枚を名前順にPDFへ変換中...")
    # Convert before opening the destination so conversion failures leave it untouched.
    pdf = img2pdf.convert([str(p) for p in png_files])
    with output.open("wb" if args.overwrite else "xb") as stream:
        stream.write(pdf)
    print(f"✅ 変換完了! PDFを出力しました: {output.resolve()}")


if __name__ == "__main__":
    main()
