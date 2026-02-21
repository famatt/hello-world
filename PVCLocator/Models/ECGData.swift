import Foundation

// MARK: - Bundle Branch Pattern in V1

enum BundleBranchPattern: String, CaseIterable, Identifiable {
    case lbbb = "LBBB (V1 predominantly negative)"
    case rbbb = "RBBB (V1 predominantly positive)"

    var id: String { rawValue }

    var shortName: String {
        switch self {
        case .lbbb: return "LBBB"
        case .rbbb: return "RBBB"
        }
    }
}

// MARK: - QRS Polarity

enum QRSPolarity: String, CaseIterable, Identifiable {
    case positive = "Positive (upright)"
    case negative = "Negative (inverted)"
    case isoelectric = "Isoelectric"

    var id: String { rawValue }
}

// MARK: - QRS Axis (derived from limb leads)

enum QRSAxis: String, Identifiable {
    case inferior = "Inferior"
    case superior = "Left Superior"
    case rightward = "Right Axis"
    case extreme = "Extreme / Northwest"

    var id: String { rawValue }
}

// MARK: - Precordial Transition Zone

enum TransitionZone: Int, CaseIterable, Identifiable {
    case none = 0
    case v1 = 1, v2 = 2, v3 = 3, v4 = 4, v5 = 5, v6 = 6

    var id: Int { rawValue }

    var label: String {
        switch self {
        case .none: return "No transition"
        case .v1: return "V1"
        case .v2: return "V2"
        case .v3: return "V3"
        case .v4: return "V4"
        case .v5: return "V5"
        case .v6: return "V6"
        }
    }

    var isEarly: Bool { rawValue >= 1 && rawValue <= 3 }
    var isLate: Bool { rawValue >= 4 }
}

// MARK: - ECG Measurements (all inputs for algorithm analysis)

struct ECGMeasurements {

    // ---- Step 1: V1 Morphology ----
    var bundleBranch: BundleBranchPattern = .lbbb

    // ---- Step 2: QRS Axis (limb lead polarities) ----
    var leadIPolarity: QRSPolarity = .positive
    var leadIIPolarity: QRSPolarity = .positive
    var leadIIIPolarity: QRSPolarity = .positive
    var leadAVFPolarity: QRSPolarity = .positive
    var leadAVLPolarity: QRSPolarity = .negative

    var axis: QRSAxis {
        let iPos = leadIPolarity == .positive
        let avfPos = leadAVFPolarity == .positive
        if iPos && avfPos { return .inferior }
        if iPos && !avfPos { return .superior }
        if !iPos && avfPos { return .rightward }
        return .extreme
    }

    // ---- Step 3: Precordial Transition ----
    var pvcTransition: TransitionZone = .v4
    var sinusTransition: TransitionZone = .v3

    // ---- Step 4: QRS Duration ----
    var qrsDurationMs: Double = 140

    // ---- Step 5: V2 Amplitude Measurements (Betensky) ----
    var v2RWavePVC: Double = 0       // mm
    var v2SWavePVC: Double = 0       // mm
    var v2RWaveSinus: Double = 0     // mm
    var v2SWaveSinus: Double = 0     // mm

    /// Betensky V2 Transition Ratio
    var v2TransitionRatio: Double {
        let pvcRatio = (v2RWavePVC + v2SWavePVC) > 0
            ? v2RWavePVC / (v2RWavePVC + v2SWavePVC) : 0
        let sinusRatio = (v2RWaveSinus + v2SWaveSinus) > 0
            ? v2RWaveSinus / (v2RWaveSinus + v2SWaveSinus) : 0
        return sinusRatio > 0 ? pvcRatio / sinusRatio : 0
    }

    // ---- Step 6: V1 / V2 Detail (LBBB patterns) ----
    var v1HasInitialR: Bool = false
    var v1RWaveDurationMs: Double = 0
    var v1RWaveAmplitude: Double = 0     // mm
    var v1SWaveAmplitude: Double = 0     // mm
    var v2HasInitialR: Bool = false

    /// Ouyang R-wave duration index in V1 or V2
    var rWaveDurationIndex: Double {
        qrsDurationMs > 0 ? v1RWaveDurationMs / qrsDurationMs : 0
    }

    /// Ouyang R/S amplitude ratio in V1
    var rSAmplitudeRatio: Double {
        v1SWaveAmplitude > 0 ? v1RWaveAmplitude / v1SWaveAmplitude : 0
    }

    // ---- Step 7: Lead I Details ----
    var leadINotching: Bool = false

    // ---- Step 8: Timing Measurements ----
    var pseudoDeltaWaveMs: Double = 0
    var intrinsicoidDeflectionMs: Double = 0
    var shortestRSComplexMs: Double = 0
    var maxDeflectionTimeMs: Double = 0

    /// Dixit Maximum Deflection Index
    var mdi: Double {
        qrsDurationMs > 0 ? maxDeflectionTimeMs / qrsDurationMs : 0
    }

    // ---- Step 9: Additional Morphology ----
    var inferiorLeadNotching: Bool = false
    var qInInferiorLeads: Bool = false
    var avlQSPattern: Bool = false
    var v1WPattern: Bool = false
    var leadIIGreaterThanIII: Bool = true
}
