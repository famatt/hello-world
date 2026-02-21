import Foundation

/// Betensky V2 Transition Ratio algorithm for distinguishing
/// RVOT from LVOT / aortic cusp origin.
///
/// Only applicable to outflow tract VTs (LBBB + inferior axis).
/// Compares the R/(R+S) ratio in V2 during the PVC to the same
/// ratio during sinus rhythm.
///
/// Reference:
///   Betensky BP, Park RE, Marchlinski FE, et al.
///   "The V2 Transition Ratio: A New Electrocardiographic Criterion
///    for Distinguishing Left From Right Ventricular Outflow Tract
///    Tachycardia Origin."
///   J Am Coll Cardiol. 2011;57(22):2255-2262.

struct BetenskyAlgorithm: PVCAlgorithm {
    let name = "Betensky V2 Transition Ratio"
    let authors = "Betensky BP, Park RE, Marchlinski FE, et al."
    let year = 2011
    let journal = "J Am Coll Cardiol"
    let doi = "10.1016/j.jacc.2011.01.035"
    let summary = "Uses the ratio of R/(R+S) in V2 during PVC vs sinus to differentiate LVOT from RVOT. V2TR >= 0.6 predicts LVOT with 95% sensitivity and 100% specificity."

    func analyze(_ ecg: ECGMeasurements) -> AlgorithmResult {
        // Only applicable to outflow tract morphology
        guard ecg.bundleBranch == .lbbb && ecg.axis == .inferior else {
            return notApplicable(
                reason: "V2 Transition Ratio only applies to LBBB + inferior axis (outflow tract) morphology."
            )
        }

        // Need V2 measurements
        guard (ecg.v2RWavePVC + ecg.v2SWavePVC) > 0 &&
              (ecg.v2RWaveSinus + ecg.v2SWaveSinus) > 0 else {
            return notApplicable(
                reason: "V2 R and S wave measurements are required for both PVC and sinus beats."
            )
        }

        let v2tr = ecg.v2TransitionRatio
        var reasoning = "V2 Transition Ratio = \(String(format: "%.2f", v2tr))\n"
        reasoning += "PVC V2 R/(R+S) = \(String(format: "%.2f", ecg.v2RWavePVC / (ecg.v2RWavePVC + ecg.v2SWavePVC)))\n"
        reasoning += "Sinus V2 R/(R+S) = \(String(format: "%.2f", ecg.v2RWaveSinus / (ecg.v2RWaveSinus + ecg.v2SWaveSinus)))\n"

        if v2tr >= 0.6 {
            reasoning += "V2TR >= 0.6 -> LVOT / aortic cusp origin.\n"
            reasoning += "Published sensitivity 95%, specificity 100% for this cutoff.\n"
            return result(origins: [
                OriginPrediction(origin: .lvotGeneral, confidence: .high,
                    detail: "V2TR = \(String(format: "%.2f", v2tr)) >= 0.6"),
                OriginPrediction(origin: .aorticCuspGeneral, confidence: .high,
                    detail: "Aortic cusp origin equally likely"),
                OriginPrediction(origin: .rvotGeneral, confidence: .unlikely,
                    detail: "RVOT unlikely with V2TR >= 0.6")
            ], reasoning: reasoning)
        } else {
            reasoning += "V2TR < 0.6 -> RVOT origin.\n"
            return result(origins: [
                OriginPrediction(origin: .rvotGeneral, confidence: .high,
                    detail: "V2TR = \(String(format: "%.2f", v2tr)) < 0.6"),
                OriginPrediction(origin: .lvotGeneral, confidence: .unlikely,
                    detail: "LVOT unlikely with V2TR < 0.6")
            ], reasoning: reasoning)
        }
    }
}
