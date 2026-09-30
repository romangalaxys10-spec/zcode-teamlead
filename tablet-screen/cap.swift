// cap.swift — WBeam mac host capture: ScreenCaptureKit -> VideoToolbox H.264 -> pipe.
//
// Usage: cap <fps> [bitrate] [streamW] [streamH]
//   fps      target/maximum capture rate (<= display refresh; 120 on this ProMotion panel)
//   bitrate  default 16_000_000
//   streamW  default 1920
//   streamH  default 1200
//
// Pipe protocol (stdout), one 22-byte record header + payload per encoded frame:
//   u32 magic "CRCD" | u32 w | u32 h | u32 keyframe(0/1) | u64 tsUs | u32 len | <H.264 Annex-B bytes>
// tsUs = unix epoch microseconds at stream start + sample presentation time.
//
// Also: attempts to switch the main display to its highest-refresh mode at startup.

import CoreGraphics
import CoreVideo
import Foundation
import ScreenCaptureKit
import VideoToolbox
import CoreMedia

var stderrFile: FileHandle? = FileHandle.standardError
func log(_ s: String) {
    if let d = ("cap: " + s + "\n").data(using: .utf8), let f = stderrFile {
        f.write(d)
    }
}

// ── 0. Switch display to max-refresh mode (ProMotion 120Hz). Best effort. ──
func switchToMaxRefresh() {
    let main = CGMainDisplayID()
    let modes = CGDisplayCopyAllDisplayModes(main, nil) as? [CGDisplayMode] ?? []
    var best: CGDisplayMode? = nil
    for m in modes where m.pixelWidth > 1500 {
        if best == nil || m.refreshRate > best!.refreshRate { best = m }
    }
    guard let target = best else { return }
    log("best mode \(target.pixelWidth)x\(target.pixelHeight) @ \(target.refreshRate)Hz")
    let sym = dlsym(UnsafeMutableRawPointer(bitPattern: -1), "CGConfigureDisplayWithMode")
    guard let fn = sym else {
        log("CGConfigureDisplayWithMode not available; staying at current refresh")
        return
    }
    typealias ConfigureFn = @convention(c) (UInt32, CGDisplayMode, UInt32, Bool) -> Int32
    let configure = unsafeBitCast(fn, to: ConfigureFn.self)
    let rc = configure(main, target, 0, false)
    log("refresh switch rc=\(rc) (0 = applied)")
}

// ── 1. frame writer (stdout pipe) — 22-byte CRCD record ──
func be32(_ v: UInt32) -> [UInt8] { var x = v.bigEndian; return withUnsafeBytes(of: x) { Array($0) } }
func be64(_ v: UInt64) -> [UInt8] { var x = v.bigEndian; return withUnsafeBytes(of: x) { Array($0) } }

func writeFrame(_ key: Bool, _ tsUs: UInt64, _ payload: [UInt8], w: Int, h: Int) {
    var hdr = Data()
    hdr.append(contentsOf: Array("CRCD".utf8))
    hdr.append(contentsOf: be32(UInt32(w)))
    hdr.append(contentsOf: be32(UInt32(h)))
    hdr.append(contentsOf: be32(key ? 1 : 0))
    hdr.append(contentsOf: be64(tsUs))
    hdr.append(contentsOf: be32(UInt32(payload.count)))
    hdr.append(contentsOf: payload)
    FileHandle.standardOutput.write(hdr)
}

// ── 2. encoder context + C-convention compressed output handler ──
final class OutCtx {
    var keyframes: [UInt8] = []
    var w: Int32 = 1920
    var h: Int32 = 1200
    var sentSPSPPS = false
    var frames = 0
    var epochBaseUs: UInt64 = 0
    var t0 = Date().timeIntervalSince1970
    var lastUs: UInt64 = 0
}
let gCtx = OutCtx()

func h264ParameterSets(_ desc: CMFormatDescription) -> [UInt8] {
    var count: size_t = 0
    CMVideoFormatDescriptionGetH264ParameterSetAtIndex(desc, parameterSetIndex: 0,
                                                        parameterSetPointerOut: nil, parameterSetSizeOut: nil,
                                                        parameterSetCountOut: &count, nalUnitHeaderLengthOut: nil)
    var out: [UInt8] = []
    for i in 0..<min(count, 2) {
        var p: UnsafePointer<UInt8>?
        var sz: size_t = 0
        let ok = CMVideoFormatDescriptionGetH264ParameterSetAtIndex(desc, parameterSetIndex: i,
                                                                     parameterSetPointerOut: &p, parameterSetSizeOut: &sz,
                                                                     parameterSetCountOut: nil, nalUnitHeaderLengthOut: nil) == 0
        if ok, let pp = p, sz > 0 {
            out += [0,0,0,1]
            out.append(contentsOf: UnsafeBufferPointer(start: pp, count: Int(sz)))
        }
    }
    return out
}

// C callback (non-ambiguous overload): (refCon, sourceFrameRefCon, status, infoFlags, sampleBuffer)
let outHandler: @convention(c) (UnsafeMutableRawPointer?, UnsafeMutableRawPointer?, OSStatus,
                                VTEncodeInfoFlags, CMSampleBuffer?) -> Void = { _, _, status, _, sampleBuf in
    guard status == noErr, let sampleBuf = sampleBuf else {
        if status != noErr { log("encode status \(status)") }
        return
    }
    let ctx = gCtx

    if !ctx.sentSPSPPS, let desc = CMSampleBufferGetFormatDescription(sampleBuf) {
        let kp = h264ParameterSets(desc)
        if !kp.isEmpty {
            ctx.keyframes = kp
            ctx.sentSPSPPS = true
            log("SPS/PPS captured (\(kp.count) bytes)")
        }
    }

    guard CMSampleBufferGetNumSamples(sampleBuf) > 0,
          let block = CMSampleBufferGetDataBuffer(sampleBuf) else { return }
    let total = CMSampleBufferGetTotalSampleSize(sampleBuf)
    guard total > 0 else { return }
    var frameBytes = [UInt8](repeating: 0, count: Int(total))
    let copyStatus = frameBytes.withUnsafeMutableBytes { raw in
        CMBlockBufferCopyDataBytes(block, atOffset: 0, dataLength: total, destination: raw.baseAddress!)
    }
    if copyStatus != 0 {
        log("block copy err \(copyStatus)")
        return
    }
    // VideoToolbox H.264 output here is AVCC (4-byte length-prefixed NAL units),
    // not Annex-B. WBeam's decoder expects Annex-B start codes, so convert:
    // walk the 4-byte length prefixes, replace each with a 00 00 00 01 start code.
    var avcc = frameBytes
    var annexB: [UInt8] = []
    var isKey = false
    if avcc.count >= 4 {
        var i = 0
        while i + 4 < avcc.count {
            let len = (Int(avcc[i]) << 24) | (Int(avcc[i+1]) << 16) | (Int(avcc[i+2]) << 8) | Int(avcc[i+3])
            if len <= 0 || i + 4 + len > avcc.count { break }
            let nalHdr = avcc[i + 4]
            let nalType = nalHdr & 0x1F
            if nalType == 5 {
                isKey = true   // IDR slice
            }
            annexB.append(contentsOf: [0, 0, 0, 1])
            annexB.append(contentsOf: avcc[(i+4)..<(i+4+len)])
            i += 4 + len
        }
    }
    // If conversion produced nothing (already Annex-B fallback), use raw bytes.
    let framePayload = annexB.isEmpty ? frameBytes : annexB
    if annexB.isEmpty {
        // fallback: detect start codes
        var j = 0
        while j + 3 < framePayload.count && !(framePayload[j] == 0 && framePayload[j+1] == 0 && framePayload[j+2] == 1) { j += 1 }
        if j + 3 < framePayload.count {
            let t2 = framePayload[j+3] & 0x1F
            isKey = (t2 == 5) || (t2 == 7)
        }
    }

    var payload: [UInt8]
    if isKey && !ctx.keyframes.isEmpty {
        payload = ctx.keyframes + framePayload
    } else {
        payload = framePayload
    }

    let t = CMSampleBufferGetPresentationTimeStamp(sampleBuf)
    let relUs = t.timescale > 0 ? UInt64((Double(t.value) / Double(t.timescale)) * 1_000_000) : 0
    let tsUs = ctx.epochBaseUs + relUs

    ctx.frames += 1
    if ctx.frames % 90 == 1 {
        log("frame \(ctx.frames) \(isKey ? "KEY" : "-") \(payload.count)B @ \(tsUs)")
    }
    writeFrame(isKey, tsUs, payload, w: Int(ctx.w), h: Int(ctx.h))
}

// ── 3. SCK output (receives pixel buffers) + stop delegate ──
final class OutDel: NSObject, SCStreamOutput {
    var session: VTCompressionSession!
    func stream(_ stream: SCStream, didOutputSampleBuffer sb: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .screen, sb.numSamples > 0,
              let pb = CMSampleBufferGetImageBuffer(sb) else { return }
        var info: VTEncodeInfoFlags = []
        let ts = CMSampleBufferGetPresentationTimeStamp(sb)
        let err = VTCompressionSessionEncodeFrame(
            session,
            imageBuffer: pb,
            presentationTimeStamp: ts,
            duration: .invalid,
            frameProperties: nil,
            sourceFrameRefcon: nil,
            infoFlagsOut: &info)
        if err != noErr {
            log("encode err \(err)")
        }
    }
}
final class StopDel: NSObject, SCStreamDelegate {
    func stream(_ stream: SCStream, didStopWithError error: any Error) {
        log("stream stopped: \(error)")
    }
}

// ── 4. run ──
let args = CommandLine.arguments
let fps = args.count > 1 ? Int(args[1]) ?? 90 : 90
let bitrate = args.count > 2 ? Int(args[2]) ?? 16_000_000 : 16_000_000
let streamW = args.count > 3 ? Int(args[3]) ?? 1920 : 1920
let streamH = args.count > 4 ? Int(args[4]) ?? 1200 : 1200

switchToMaxRefresh()

gCtx.w = Int32(streamW); gCtx.h = Int32(streamH)

let content = try await SCShareableContent.current
guard let display = content.displays.first else {
    log("no display"); exit(1)
}
log("display \(display.width)x\(display.height) (px), windows=\(content.windows.count)")

let filter = SCContentFilter(display: display, excludingWindows: [])
let config = SCStreamConfiguration()
config.showsCursor = true
config.pixelFormat = kCVPixelFormatType_32BGRA
config.width = streamW
config.height = streamH
config.minimumFrameInterval = CMTime(value: 1, timescale: 240)   // allow up to 240; display caps at 120

let outDel = OutDel()
let stopDel = StopDel()
let stream = SCStream(filter: filter, configuration: config, delegate: stopDel)
let sckQueue = DispatchQueue(label: "cap.sck")
let addOk = try stream.addStreamOutput(outDel, type: .screen, sampleHandlerQueue: sckQueue)
log("addStreamOutput ok=\(addOk)")

let spec: [CFString: Any] = [
    kVTCompressionPropertyKey_AverageBitRate: bitrate,
    kVTCompressionPropertyKey_DataRateLimits: [bitrate / 4, bitrate * 2] as CFArray,
    kVTCompressionPropertyKey_ExpectedFrameRate: fps,
    kVTCompressionPropertyKey_RealTime: kCFBooleanTrue,
    kVTCompressionPropertyKey_UsingHardwareAcceleratedVideoEncoder: kCFBooleanTrue,
    kVTCompressionPropertyKey_MaxKeyFrameInterval: 30,
    kVTCompressionPropertyKey_MaxKeyFrameIntervalDuration: 2.0,
    kVTCompressionPropertyKey_AllowFrameReordering: false,
    kVTCompressionPropertyKey_PrioritizeEncodingSpeedOverQuality: true,
]
let attrs: [CFString: Any] = [kCVPixelBufferPixelFormatTypeKey: kCVPixelFormatType_32BGRA]
var outSession: VTCompressionSession? = nil
let createStatus = VTCompressionSessionCreate(
    allocator: nil,
    width: Int32(streamW),
    height: Int32(streamH),
    codecType: kCMVideoCodecType_H264,
    encoderSpecification: spec as CFDictionary,
    imageBufferAttributes: attrs as CFDictionary,
    compressedDataAllocator: nil,
    outputCallback: outHandler,
    refcon: nil,
    compressionSessionOut: &outSession
)
guard let session = outSession else {
    log("session create failed status=\(createStatus)"); exit(3)
}
outDel.session = session
gCtx.epochBaseUs = UInt64(Date().timeIntervalSince1970 * 1_000_000)

let prep = VTCompressionSessionPrepareToEncodeFrames(session)
log("prepare encode err=\(prep)")

_ = try await stream.startCapture()
log("stream started; grant Screen Recording to cap if black frames")
let keepAlive = DispatchSemaphore(value: 0)
keepAlive.wait()
