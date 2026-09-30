// tsinput — minimal macOS mouse/synthetic-input tool for the tablet screen back-channel.
//
// Usage:
//   tsinput move x y          — move pointer (x,y in screen global pixels)
//   tsinput click x y         — left click at x,y
//   tsinput rmbclick x y      — right click
//   tsinput down x y / up x y — press/release at coords (drag between down and up)
//   tsinput scroll dy         — scroll (positive = down), at current pointer position
//
// Requires the Accessibility grant for synthetic events
// (System Settings → Privacy & Security → Accessibility). Screen pixels are in
// captured-image space; the caller divides by the Retina scale factor.
import Foundation
import CoreGraphics

func mouse(_ type: CGEventType, x: Double, y: Double, button: CGMouseButton) {
    let loc = CGPoint(x: x, y: y)
    let ev = CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: loc, mouseButton: button)
    ev?.post(tap: .cghidEventTap)
}

let a = CommandLine.arguments
if a.count >= 2 && a[1] == "dims" {
    let main = CGMainDisplayID()
    let px = Double(CGDisplayPixelsWide(main)), py = Double(CGDisplayPixelsHigh(main))
    if let mode = CGDisplayCopyDisplayMode(main) {
        let pw = Double(mode.width)              // points
        let ph = Double(mode.height)             // points
        let mpw = Double(mode.pixelWidth)        // pixels
        let mpy = Double(mode.pixelHeight)       // pixels
        if pw > 0, ph > 0, mpw > 0, mpy > 0 {
            // pixels / points = scale; points = pixels / scale
            print("\(px * pw / mpw) \(py * ph / mpy) \(px) \(py)")
            exit(0)
        }
    }
    print("\(px / 2) \(py / 2) \(px) \(py)")
    exit(0)
}
guard a.count >= 3 else { fputs("usage: tsinput <move|click|rmbclick|down|up|scroll|dims> ...\n", stderr); exit(2) }
let cmd = a[1]
func d(_ i: Int) -> Double { Double(a[i]) ?? 0 }
switch cmd {
case "move":
    mouse(.mouseMoved, x: d(2), y: d(3), button: .left)
case "down":
    mouse(.leftMouseDown, x: d(2), y: d(3), button: .left)
case "up":
    mouse(.leftMouseUp, x: d(2), y: d(3), button: .left)
case "click":
    mouse(.leftMouseDown, x: d(2), y: d(3), button: .left)
    usleep(30_000)
    mouse(.leftMouseUp, x: d(2), y: d(3), button: .left)
case "rmbclick":
    mouse(.rightMouseDown, x: d(2), y: d(3), button: .right)
    usleep(30_000)
    mouse(.rightMouseUp, x: d(2), y: d(3), button: .right)
case "scroll":
    let loc = (CGEvent(source: nil)?.location) ?? .zero
    let ev = CGEvent(scrollWheelEvent2Source: nil, units: .pixel, wheelCount: 1,
                      wheel1: Int32(d(2)), wheel2: 0, wheel3: 0)
    ev?.location = loc
    ev?.post(tap: .cghidEventTap)
default:
    fputs("unknown command: \(cmd)\n", stderr); exit(2)
}
exit(0)
exit(0)
