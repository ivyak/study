import Foundation
import PDFKit
import AppKit

enum RenderFailure: Error { case invalidInput, missingPage, encoding }
let args = CommandLine.arguments
guard args.count >= 4 else {
  throw RenderFailure.invalidInput
}
let url = URL(fileURLWithPath: args[1])
let pdf = PDFDocument(url: url)
let raster = ["png", "jpg", "jpeg"].contains(url.pathExtension.lowercased())
  ? NSImage(contentsOf: url) : nil
guard pdf != nil || raster != nil else { throw RenderFailure.invalidInput }
let folder = URL(fileURLWithPath: args[2], isDirectory: true)
try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
for value in args.dropFirst(3) {
  guard let number = Int(value), number > 0 else {
    throw RenderFailure.missingPage
  }
  let image: NSImage
  if let pdf = pdf, let page = pdf.page(at: number - 1) {
    image = page.thumbnail(of: NSSize(width: 1200, height: 2000), for: .mediaBox)
  } else if number == 1, let raster = raster {
    image = raster
  } else {
    throw RenderFailure.missingPage
  }
  guard let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let data = bitmap.representation(using: .png, properties: [:]) else {
    throw RenderFailure.encoding
  }
  try data.write(to: folder.appendingPathComponent("\(number).png"), options: .atomic)
}
