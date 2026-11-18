import AppKit
import ApplicationServices
import Vision

func fail(_ message: String, code: Int32 = 1) -> Never {
  FileHandle.standardError.write(Data((message + "\n").utf8))
  exit(code)
}

func checkAccessibility() {
  guard AXIsProcessTrusted() else {
    fail("システム設定のアクセシビリティで、実行元のターミナルに操作を許可してください。", code: 2)
  }
}

struct TextLine: Encodable {
  let text: String
  let x: Double
  let y: Double
  let width: Double
  let height: Double
}

struct PageText: Encodable {
  let page: Int
  let lines: [TextLine]
}

func readPageText(_ url: URL) throws -> [TextLine] {
  let request = VNRecognizeTextRequest()
  request.recognitionLevel = .accurate
  request.recognitionLanguages = ["ja-JP", "en-US"]
  try VNImageRequestHandler(url: url).perform([request])

  return (request.results ?? []).compactMap { observation in
    guard let text = observation.topCandidates(1).first?.string else { return nil }
    let box = observation.boundingBox
    return TextLine(
      text: text.precomposedStringWithCompatibilityMapping,
      x: box.minX, y: 1 - box.maxY, width: box.width, height: box.height
    )
  }
}

let args = CommandLine.arguments
switch args.dropFirst().first {
case "check-accessibility":
  checkAccessibility()
case "front":
  checkAccessibility()
  guard let pid = NSWorkspace.shared.frontmostApplication?.processIdentifier else {
    fail("前面のアプリを確認できません。")
  }
  print(pid)
case "right":
  guard args.count == 3, let pid = pid_t(args[2]),
        NSWorkspace.shared.frontmostApplication?.processIdentifier == pid else {
    fail("撮影開始時と異なるアプリが前面にあるため停止しました。")
  }
  checkAccessibility()
  guard let down = CGEvent(keyboardEventSource: nil, virtualKey: 124, keyDown: true),
        let up = CGEvent(keyboardEventSource: nil, virtualKey: 124, keyDown: false) else {
    fail("右矢印キーの入力を作成できませんでした。")
  }
  down.flags = []
  up.flags = []
  down.postToPid(pid)
  up.postToPid(pid)
case "chapters":
  guard args.count == 3 else { fail("撮影画像のフォルダを指定してください。") }
  do {
    let folder = URL(fileURLWithPath: args[2], isDirectory: true)
    let pages = try FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)
      .filter { $0.pathExtension == "png" && $0.hasDirectoryPath == false }
      .sorted { $0.lastPathComponent < $1.lastPathComponent }
    for (offset, page) in pages.enumerated() {
      do {
        let pageText = PageText(page: offset + 1, lines: try readPageText(page))
        let data = try JSONEncoder().encode(pageText)
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([0x0A]))
      } catch {
        let message = "\(offset + 1) 枚目の見出しを読み取れませんでした。 \(error)\n"
        FileHandle.standardError.write(Data(message.utf8))
      }
      let processed = offset + 1
      if processed.isMultiple(of: 10) || processed == pages.count {
        let progress = "見出しの読み取りを \(processed)/\(pages.count) 枚終えました。\n"
        FileHandle.standardError.write(Data(progress.utf8))
      }
    }
  } catch {
    fail(error.localizedDescription)
  }
default:
  fail("実行する操作を指定してください。")
}
