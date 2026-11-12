import Foundation
import PDFKit
import AppKit

enum RenderFailure: Error { case invalidInput, missingPage, encoding }
let args = CommandLine.arguments
guard args.count >= 4, let pdf = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
  throw RenderFailure.invalidInput
}
let folder = URL(fileURLWithPath: args[2], isDirectory: true)
try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
for value in args.dropFirst(3) {
  guard let number = Int(value), number > 0, let page = pdf.page(at: number - 1) else {
    throw RenderFailure.missingPage
  }
  let image = page.thumbnail(of: NSSize(width: 1200, height: 2000), for: .mediaBox)
  guard let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let data = bitmap.representation(using: .png, properties: [:]) else {
    throw RenderFailure.encoding
  }
  try data.write(to: folder.appendingPathComponent("\(number).png"), options: .atomic)
}
