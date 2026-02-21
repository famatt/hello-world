import Foundation

/// Berruezo epicardial origin criteria.
///
/// Three ECG features that suggest an epicardial origin for VT:
///   1. Pseudo-delta wave >= 34ms
///   2. Intrinsicoid deflection time >= 85ms
///   3. Shortest RS complex >= 121ms
///
/// Any single criterion present raises suspicion for epicardial
/// origin. Specificity increases when multiple criteria are met.
///
/// Reference:
///   Berruezo A, Mont L, Nava S, Chueca E, Bartholomay E, Brugada J.
///   "Electrocardiographic recognition of the epicardial origin
///    of ventricular tachycardias."
///   Circulation. 2004;109(15):1842-1847.

struct BerruezoAlgorithm: PVCAlgorithm {
    let name = "Berruezo Epicardial Criteria"
    let authors = "Berruezo A, Mont L, Nava S, et al."
    let year = 2004
    let journal = "Circulation"
    let doi = "10.1161/01.CIR.0000125525.04081.4B"
    let summary = "Three criteria for epicardial VT origin: pseudo-delta >= 34ms, intrinsicoid deflection >= 85ms, shortest RS >= 121ms. Any one present suggests epicardial. Multiple increase specificity."

    func analyze(_ ecg: ECGMeasurements) -> AlgorithmResult {
        // Need at least one timing measurement
        let hasPseudoDelta = ecg.pseudoDeltaWaveMs > 0
        let hasIntrinsicoid = ecg.intrinsicoidDeflectionMs > 0
        let hasShortestRS = ecg.shortestRSComplexMs > 0

        guard hasPseudoDelta || hasIntrinsicoid || hasShortestRS else {
            return notApplicable(
                reason: "At least one timing measurement is needed: pseudo-delta wave, intrinsicoid deflection time, or shortest RS complex duration."
            )
        }

        var criteriaMetCount = 0
        var criteriaDetails: [String] = []
        var reasoning = "Berruezo Epicardial Criteria Assessment:\n"

        // Criterion 1: Pseudo-delta wave >= 34ms
        if hasPseudoDelta {
            let met = ecg.pseudoDeltaWaveMs >= 34
            reasoning += "1. Pseudo-delta wave = \(String(format: "%.0f", ecg.pseudoDeltaWaveMs))ms"
            reasoning += " (threshold >= 34ms): \(met ? "MET" : "not met")\n"
            if met {
                criteriaMetCount += 1
                criteriaDetails.append("Pseudo-delta >= 34ms")
            }
        } else {
            reasoning += "1. Pseudo-delta wave: not measured\n"
        }

        // Criterion 2: Intrinsicoid deflection time >= 85ms
        if hasIntrinsicoid {
            let met = ecg.intrinsicoidDeflectionMs >= 85
            reasoning += "2. Intrinsicoid deflection = \(String(format: "%.0f", ecg.intrinsicoidDeflectionMs))ms"
            reasoning += " (threshold >= 85ms): \(met ? "MET" : "not met")\n"
            if met {
                criteriaMetCount += 1
                criteriaDetails.append("Intrinsicoid deflection >= 85ms")
            }
        } else {
            reasoning += "2. Intrinsicoid deflection: not measured\n"
        }

        // Criterion 3: Shortest RS complex >= 121ms
        if hasShortestRS {
            let met = ecg.shortestRSComplexMs >= 121
            reasoning += "3. Shortest RS complex = \(String(format: "%.0f", ecg.shortestRSComplexMs))ms"
            reasoning += " (threshold >= 121ms): \(met ? "MET" : "not met")\n"
            if met {
                criteriaMetCount += 1
                criteriaDetails.append("Shortest RS >= 121ms")
            }
        } else {
            reasoning += "3. Shortest RS complex: not measured\n"
        }

        let totalMeasured = (hasPseudoDelta ? 1 : 0)
            + (hasIntrinsicoid ? 1 : 0) + (hasShortestRS ? 1 : 0)

        reasoning += "\nCriteria met: \(criteriaMetCount) of \(totalMeasured) measured.\n"

        if criteriaMetCount >= 2 {
            reasoning += "Multiple epicardial criteria met -> high suspicion for epicardial origin.\n"
            return result(origins: [
                OriginPrediction(origin: .epicardial, confidence: .high,
                    detail: "\(criteriaMetCount)/\(totalMeasured) criteria met: \(criteriaDetails.joined(separator: ", "))"),
                OriginPrediction(origin: .lvSummit, confidence: .moderate,
                    detail: "LV summit / great cardiac vein region possible")
            ], reasoning: reasoning)
        } else if criteriaMetCount == 1 {
            reasoning += "One epicardial criterion met -> moderate suspicion.\n"
            return result(origins: [
                OriginPrediction(origin: .epicardial, confidence: .moderate,
                    detail: "1/\(totalMeasured) criteria met: \(criteriaDetails.joined(separator: ", "))"),
                OriginPrediction(origin: .lvSummit, confidence: .low,
                    detail: "LV summit possible")
            ], reasoning: reasoning)
        } else {
            reasoning += "No epicardial criteria met -> endocardial origin likely.\n"
            return result(origins: [
                OriginPrediction(origin: .epicardial, confidence: .unlikely,
                    detail: "0/\(totalMeasured) epicardial criteria met")
            ], reasoning: reasoning)
        }
    }
}
