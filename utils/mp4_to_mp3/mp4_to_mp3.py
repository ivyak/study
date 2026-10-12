from moviepy.editor import VideoFileClip

def convert_mp4_to_mp3(mp4_file, mp3_file):
    """
    MP4ファイルから音声を抽出してMP3ファイルとして保存する関数
    
    :param mp4_file: 入力するMP4ファイルのパス
    :param mp3_file: 出力するMP3ファイルのパス
    """
    try:
        # MP4ファイルを読み込む
        video_clip = VideoFileClip(mp4_file)
        
        # 動画クリップから音声部分を抽出
        audio_clip = video_clip.audio
        
        # 音声をMP3ファイルとして書き出す
        # codec='libmp3lame' は高品質なMP3エンコーダーを指定します
        audio_clip.write_audiofile(mp3_file, codec='libmp3lame')
        
        # クリップを閉じてリソースを解放
        audio_clip.close()
        video_clip.close()
        
        print(f"変換が完了しました: {mp3_file}")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")

# --- ここから実行 ---
if __name__ == "__main__":
    # 入力ファイルと出力ファイルを指定
    input_mp4 = "input.mp4"  # ここにあなたのMP4ファイル名を入力
    output_mp3 = "output.mp3" # 出力したいMP3ファイル名

    convert_mp4_to_mp3(input_mp4, output_mp3)