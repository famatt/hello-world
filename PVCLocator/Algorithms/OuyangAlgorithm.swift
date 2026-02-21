import Foundation

/// Ouyang algorithm for differentiating RVOT from LVOT origin
/// using R-wave duration index and R/S amplitude ratio in V1/V2.
///
/// Only applicable to outflow tract VTs (LBBB + inferior axis).
///
/// Reference:
///   Ouyang F, Fotuhi P, Ho SY, et al.
///   "Repetitive monomorphic ventricular tachycardia originating
///    from the aortic sinus cusp: electrocardiographic
///    characterization for guiding catheter ablation."
///   J Am Coll Cardiol. 2002;39(3):500-508.

struct OuyangAlgorithm: PVCAlgorithm {
    let name = "Ouyang R-Wave Index"
    let authors = "Ouyang F, Fotuhi P, Ho SY, et al."
    let year = 2002
    let journal = "J Am Coll Cardiol"
    let doi = "10.1016/S0735-1097(01)01767-3"
    let summary = "Uses R-wave duration index (>=50%) and R/S amplitude ratio (>=30%) in V1/V2 to differentiate LVOT from RVOT. Meeting either criterion suggests LVOT."

    func analyze(_ ecg: ECGMeasurements) -> AlgorithmResult {
        guard ecg.bundleBranch == .lbbb && ecg.axis == .inferior else {
            return notApplicable(
                reason: "Ouyang criteria only apply to LBBB + inferior axis (outflow tract) morphology."
            )
        }

        let rwdi = ecg.rWaveDurationIndex
        let rsRatio = ecg.rSAmplitudeRatio
        var reasoning = ""

        // R-wave duration index: R wave duration in V1 or V2 / QRS duration
        reasoning += "R-wave duration index = \(String(format: "%.0f", rwdi * 100))%"
        reasoning += " (threshold >= 50%)\n"

        // R/S amplitude ratio in V1
        reasoning += "R/S amplitude ratio in V1 = \(String(format: "%.0f", rsRatio * 100))%"
        reasoning += " (threshold >= 30%)\n"

        let rwdiMet = rwdi >= 0.50
        let rsMet = rsRatio >= 0.30

        if rwdiMet || rsMet {
            var criteria: [String] = []
            if rwdiMet { criteria.append("R-wave duration index >= 50%") }
            if rsMet { criteria.append("R/S amplitude ratio >= 30%") }
            reasoning += "Criteria met: \(criteria.joined(separator: ", "))\n"
            reasoning += "-> Suggests LVOT / aortic cusp origin.\n"

            let confidence: ConfidenceLevel = (rwdiMet && rsMet) ? .high : .moderate

            return result(origins: [
                OriginPrediction(origin: .lvotGeneral, confidence: confidence,
                    detail: "Ouyang criteria met: \(criteria.joined(separator: " + "))"),
                OriginPrediction(origin: .aorticCuspGeneral, confidence: confidence,
                    detail: "Aortic cusp origin equally likely"),
                OriginPrediction(origin: .rvotGeneral, confidence: .unlikely,
                    detail: "RVOT unlikely when Ouyang criteria met")
            ], reasoning: reasoning)
        } else {
            reasoning += "Neither criterion met -> favors RVOT origin.\n"
            return result(origins: [
                OriginPrediction(origin: .rvotGeneral, confidence: .moderate,
                    detail: "Ouyang criteria not met, RVOT more likely"),
                OriginPrediction(origin: .lvotGeneral, confidence: .low,
                    detail: "LVOT less likely but not excluded")
            ], reasoning: reasoning)
        }
    }
}
