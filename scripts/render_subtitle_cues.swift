import AppKit
import Foundation

struct Cue: Decodable {
    let start: Double
    let end: Double
    let text: String
}

let args = CommandLine.arguments
guard args.count >= 3 else {
    fputs("usage: swift render_subtitle_cues.swift cues.json out_dir [width] [height] [font-size] [bottom-margin] [outline-radius]\n", stderr)
    exit(2)
}

let cuesURL = URL(fileURLWithPath: args[1])
let outDir = URL(fileURLWithPath: args[2], isDirectory: true)
let width = args.count > 3 ? (Int(args[3]) ?? 1280) : 1280
let height = args.count > 4 ? (Int(args[4]) ?? 720) : 720
let fontSize = args.count > 5 ? (Double(args[5]).map { CGFloat($0) } ?? 51.0) : 51.0
let bottomMargin = args.count > 6 ? (Double(args[6]).map { CGFloat($0) } ?? 28.0) : 28.0
let outlineRadius = args.count > 7 ? (Double(args[7]).map { CGFloat($0) } ?? 8.0) : 8.0

try FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
let cues = try JSONDecoder().decode([Cue].self, from: Data(contentsOf: cuesURL))

for (index, cue) in cues.enumerated() {
    if cue.text.contains("—") || cue.text.contains("–") {
        fputs("cue \(index + 1): long dash forbidden\n", stderr)
        exit(1)
    }
}

let font = NSFont(name: "Arial-BoldMT", size: fontSize) ?? NSFont.boldSystemFont(ofSize: fontSize)
let maxTextWidth = CGFloat(width) * 0.92

for (index, cue) in cues.enumerated() {
    guard let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: width,
        pixelsHigh: height,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ) else {
        fputs("cannot create bitmap for cue \(index + 1)\n", stderr)
        exit(1)
    }

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

    NSColor.clear.setFill()
    NSRect(x: 0, y: 0, width: CGFloat(width), height: CGFloat(height)).fill()

    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center
    paragraph.lineBreakMode = .byWordWrapping
    paragraph.lineSpacing = fontSize * 0.06

    let baseAttributes: [NSAttributedString.Key: Any] = [
        .font: font,
        .paragraphStyle: paragraph
    ]
    var outlineAttributes = baseAttributes
    outlineAttributes[.foregroundColor] = NSColor.black.withAlphaComponent(0.94)
    var fillAttributes = baseAttributes
    fillAttributes[.foregroundColor] = NSColor.white

    let outlineText = NSAttributedString(string: cue.text, attributes: outlineAttributes)
    let fillText = NSAttributedString(string: cue.text, attributes: fillAttributes)
    let bounds = outlineText.boundingRect(
        with: NSSize(width: maxTextWidth, height: CGFloat.greatestFiniteMagnitude),
        options: [.usesLineFragmentOrigin, .usesFontLeading]
    )
    let drawRect = NSRect(
        x: (CGFloat(width) - bounds.width) / 2,
        y: bottomMargin,
        width: bounds.width,
        height: bounds.height
    )

    for angle in stride(from: 0.0, through: 348.75, by: 11.25) {
        let radians = CGFloat(angle * .pi / 180.0)
        let offsetRect = drawRect.offsetBy(
            dx: cos(radians) * outlineRadius,
            dy: sin(radians) * outlineRadius
        )
        outlineText.draw(with: offsetRect, options: [.usesLineFragmentOrigin, .usesFontLeading])
    }
    fillText.draw(with: drawRect, options: [.usesLineFragmentOrigin, .usesFontLeading])

    NSGraphicsContext.restoreGraphicsState()

    guard let png = rep.representation(using: .png, properties: [:]) else {
        fputs("cannot encode PNG for cue \(index + 1)\n", stderr)
        exit(1)
    }
    let filename = String(format: "cue_%02d.png", index + 1)
    try png.write(to: outDir.appendingPathComponent(filename))
}

print("rendered \(cues.count) cues to \(outDir.path)")
