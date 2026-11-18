import AppKit
import ApplicationServices
import Vision

func fail(_ message: String) -> Never {
  FileHandle.standardError.write(Data((message + "\n").utf8))
  exit(1)
}

func chapterHeading(in url: URL) throws -> (number: Int, title: String)? {
  let request = VNRecognizeTextRequest()
  request.recognitionLevel = .accurate
  request.recognitionLanguages = ["ja-JP", "en-US"]
  request.regionOfInterest = CGRect(x: 0, y: 0.55, width: 1, height: 0.45)
  try VNImageRequestHandler(url: url).perform([request])

  let lines = (request.results ?? []).compactMap { observation -> (text: String, box: CGRect)? in
    guard let text = observation.topCandidates(1).first?.string else { return nil }
    let title = text.precomposedStringWithCompatibilityMapping
      .split(whereSeparator: \.isWhitespace).joined(separator: " ")
    return (title, observation.boundingBox)
  }

  let explicit = #/^(?:第\s*([0-9]{1,2})\s*章|(?i:chapter)\s+([0-9]{1,2})\b)/#
  let numbered = #/^([1-9][0-9]?)\.(?:\s+(?=\S)|(?=[^0-9\s.]))/#
  let section = #/^[0-9]+\.\s*[0-9]+(?:\.|\s|$)/#
  let leaders = #/(?:[.·…]{2,}|\.\s+\.)\s*[0-9]+$/#
  if lines.contains(where: { line in
    let text = line.text.replacingOccurrences(of: " ", with: "")
    return text == "目次" || text.lowercased() == "contents" ||
      line.text.firstMatch(of: leaders) != nil
  }) {
    return nil
  }

  let typicalHeights = lines.map { $0.box.height }.sorted()
  let typicalHeight = typicalHeights.isEmpty ? 0 : typicalHeights[typicalHeights.count / 2]
  let candidates = lines.compactMap { line -> (number: Int, title: String)? in
    if let match = line.text.firstMatch(of: explicit),
       let digits = match.1 ?? match.2, let number = Int(digits) {
      guard line.box.height >= 0.016 else { return nil }
      return (number, line.text)
    }
    guard let match = line.text.firstMatch(of: numbered),
          line.text.firstMatch(of: section) == nil,
          let number = Int(match.1),
          line.box.height >= max(0.020, typicalHeight * 1.25) ||
            (lines.count <= 3 && line.box.height >= 0.022) else { return nil }
    return (number, line.text)
  }
  return candidates.count == 1 ? candidates[0] : nil
}

let args = CommandLine.arguments
switch args.dropFirst().first {
case "front":
  guard AXIsProcessTrusted() else {
    fail("システム設定のアクセシビリティで、実行元のターミナルに操作を許可してください。")
  }
  guard let pid = NSWorkspace.shared.frontmostApplication?.processIdentifier else {
    fail("前面のアプリを確認できません。")
  }
  print(pid)
case "right":
  guard args.count == 3, let pid = pid_t(args[2]),
        NSWorkspace.shared.frontmostApplication?.processIdentifier == pid else {
    fail("撮影開始時と異なるアプリが前面にあるため停止しました。")
  }
  guard AXIsProcessTrusted(),
        let down = CGEvent(keyboardEventSource: nil, virtualKey: 124, keyDown: true),
        let up = CGEvent(keyboardEventSource: nil, virtualKey: 124, keyDown: false) else {
    fail("右矢印キーを送信できません。アクセシビリティの設定を確認してください。")
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
        if let heading = try chapterHeading(in: page) {
          print("\(offset + 1)\t\(heading.number)\t\(heading.title)")
        }
      } catch {
        let message = "\(offset + 1) 枚目の見出しを読み取れませんでした。 \(error)\n"
        FileHandle.standardError.write(Data(message.utf8))
      }
    }
  } catch {
    fail(error.localizedDescription)
  }
default:
  fail("実行する操作を指定してください。")
}
