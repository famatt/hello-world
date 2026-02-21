import Foundation

/// Dixit Maximum Deflection Index (MDI) algorithm for
/// distinguishing septal from free wall RVOT origin,
/// and identifying possible epicardial origin.
///
/// MDI = time from QRS onset to maximum deflection / QRS duration
/// in any precordial lead.
///
/// Reference:
///   Dixit S, Gerstenfeld EP, Callans DJ, Marchlinski FE.
///   "Electrocardiographic patterns of superior right ventricular
///    outflow tract tachycardias: distinguishing septal and
///    free-wall sites of origin."
///   J Cardiovasc Electrophysiol. 2003;14(1):1-7.

struct DixitAlgorithm: PVCAlgorithm {
    let name = "Dixit MDI (Maximum Deflection Index)"
    let authors = "Dixit S, Gerstenfeld EP, Callans DJ, Marchlinski FE"
    let year = 2003
    let journal = "J Cardiovasc Electrophysiol"
    let doi = "10.1046/j.1540-8167.2003.02404.x"
    let summary = "MDI >= 0.55 suggests free wall or epicardial origin. MDI < 0.55 suggests septal origin. Measured as time to maximum deflection divided by total QRS duration."

    func analyze(_ ecg: ECGMeasurements) -> AlgorithmResult {
        // Need timing measurements
        guard ecg.maxDeflectionTimeMs > 0 && ecg.qrsDurationMs > 0 else {
            return notApplicable(
                reason: "Maximum deflection time and QRS duration measurements are required. Measure from QRS onset to the peak of the largest deflection in any precordial lead."
            )
        }

        let mdi = ecg.mdi
        var reasoning = "MDI = \(String(format: "%.0f", ecg.maxDeflectionTimeMs))ms / "
        reasoning += "\(String(format: "%.0f", ecg.qrsDurationMs))ms = "
        reasoning += "\(String(format: "%.2f", mdi))\n"

        if mdi >= 0.55 {
            reasoning += "MDI >= 0.55 -> free wall or epicardial origin.\n"

            if ecg.bundleBranch == .lbbb && ecg.axis == .inferior {
                reasoning += "With outflow tract morphology: RVOT free wall.\n"
                return result(origins: [
                    OriginPrediction(origin: .rvotFreeWall, confidence: .high,
                        detail: "MDI = \(String(format: "%.2f", mdi)) >= 0.55 with OT morphology"),
                    OriginPrediction(origin: .epicardial, confidence: .moderate,
                        detail: "Epicardial origin should also be considered"),
                    OriginPrediction(origin: .rvotSeptal, confidence: .unlikely,
                        detail: "Septal origin unlikely with MDI >= 0.55")
                ], reasoning: reasoning)
            } else {
                reasoning += "Non-outflow tract morphology: consider epicardial.\n"
                return result(origins: [
                    OriginPrediction(origin: .epicardial, confidence: .moderate,
                        detail: "MDI = \(String(format: "%.2f", mdi)) >= 0.55 suggests epicardial"),
                    OriginPrediction(origin: .rvFreeWall, confidence: .moderate,
                        detail: "Free wall origin also possible")
                ], reasoning: reasoning)
            }
        } else {
            reasoning += "MDI < 0.55 -> septal origin.\n"

            if ecg.bundleBranch == .lbbb && ecg.axis == .inferior {
                reasoning += "With outflow tract morphology: RVOT septal.\n"
                return result(origins: [
                    OriginPrediction(origin: .rvotSeptal, confidence: .high,
                        detail: "MDI = \(String(format: "%.2f", mdi)) < 0.55 with OT morphology"),
                    OriginPrediction(origin: .rvotFreeWall, confidence: .unlikely,
                        detail: "Free wall unlikely with MDI < 0.55"),
                    OriginPrediction(origin: .epicardial, confidence: .unlikely,
                        detail: "Epicardial unlikely with MDI < 0.55")
                ], reasoning: reasoning)
            } else {
                reasoning += "Non-outflow tract: endocardial/septal origin.\n"
                return result(origins: [
                    OriginPrediction(origin: .rvSeptum, confidence: .moderate,
                        detail: "MDI = \(String(format: "%.2f", mdi)) < 0.55 suggests septal"),
                    OriginPrediction(origin: .epicardial, confidence: .unlikely,
                        detail: "Epicardial less likely with short MDI")
                ], reasoning: reasoning)
            }
        }
    }
}
