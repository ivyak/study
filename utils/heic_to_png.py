"""HEIC 画像を PNG に変換する。

準備: python3 -m pip install Pillow pillow-heif
使用例: python3 utils/heic_to_png.py photo.heic
        python3 utils/heic_to_png.py photo.heic converted.png
"""

import argparse
from pathlib import Path


def convert_heic_to_png(source: Path, destination: Path) -> None:
    try:
        from PIL import Image
        from pillow_heif import register_heif_opener
    except ImportError as exc:
        raise SystemExit(
            "Pillow と pillow-heif が必要です。"
            " python3 -m pip install Pillow pillow-heif でインストールしてください。"
        ) from exc

    register_heif_opener()
    with Image.open(source) as image:
        image.save(destination, format="PNG")


def main() -> None:
    parser = argparse.ArgumentParser(description="HEIC 画像を PNG に変換します。")
    parser.add_argument("source", type=Path, help="変換する HEIC ファイル")
    parser.add_argument(
        "destination", nargs="?", type=Path, help="出力先（省略時は元画像と同じ場所に .png）"
    )
    args = parser.parse_args()

    source = args.source
    if not source.is_file():
        parser.error(f"入力ファイルが見つかりません: {source}")
    if source.suffix.lower() != ".heic":
        parser.error(f"HEIC ファイルを指定してください: {source}")

    destination = args.destination or source.with_suffix(".png")
    if destination.exists():
        parser.error(f"出力先が既に存在します: {destination}")

    try:
        convert_heic_to_png(source, destination)
    except OSError as exc:
        parser.exit(1, f"変換に失敗しました: {exc}\n")

    print(f"変換しました: {destination}")


if __name__ == "__main__":
    main()
