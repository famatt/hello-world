import Foundation

/// Composite RVOT sub-localization algorithm using morphological
/// features from multiple published criteria.
///
/// When RVOT origin is established, this algorithm further
/// localizes to septal vs free wall, and anterior vs posterior.
///
/// References:
///   Dixit S, et al. J Cardiovasc Electrophysiol. 2003;14:1-7.
///   Jadonath RL, et al. Am Heart J. 1995;130:1263-1273.
///   Ito S, et al. Circulation. 2003;108:1576-1581.
///   Kamakura S, et al. Circ Arrhythm Electrophysiol. 2011;4:516-523.

struct RVOTMorphologyAlgorithm: PVCAlgorithm {
    let name = "RVOT Sub-Localization (Composite)"
    let authors = "Dixit S, Jadonath RL, Ito S, Kamakura S, et al."
    let year = 2003
    let journal = "J Cardiovasc Electrophysiol / Circulation"
    let doi = "10.1046/j.1540-8167.2003.02404.x"
    let summary = "Composite criteria for RVOT sub-localization. Uses lead I morphology, aVL pattern, MDI, inferior lead morphology, and QRS duration to distinguish septal/free-wall and anterior/posterior."

    func analyze(_ ecg: ECGMeasurements) -> AlgorithmResult {
        // Only applicable to RVOT-type morphology
        guard ecg.bundleBranch == .lbbb && ecg.axis == .inferior else {
            return notApplicable(
                reason: "RVOT sub-localization only applies to LBBB + inferior axis morphology."
            )
        }

        // Should have late transition (RVOT typically V4+)
        guard ecg.pvcTransition.isLate || ecg.pvcTransition == .v3 else {
            return notApplicable(
                reason: "Early transition (V1-V2) suggests LVOT/aortic cusp rather than RVOT. This algorithm is for RVOT."
            )
        }

        var reasoning = "RVOT morphology confirmed. Sub-localizing:\n"
        var septalScore = 0
        var freeWallScore = 0
        var anteriorScore = 0
        var posteriorScore = 0

        // --- Septal vs Free Wall ---

        // 1. Lead I morphology (Dixit/Jadonath)
        // Septal: lead I isoelectric or mildly negative (R/S ~ 1)
        // Free wall: lead I more deeply negative
        if ecg.leadIPolarity == .isoelectric {
            reasoning += "Lead I isoelectric -> favors septal.\n"
            septalScore += 2
        } else if ecg.leadIPolarity == .positive {
            reasoning += "Lead I positive -> strongly favors septal.\n"
            septalScore += 3
        } else {
            reasoning += "Lead I negative -> favors free wall.\n"
            freeWallScore += 2
        }

        // 2. aVL pattern
        // Septal: aVL QS or small amplitude
        // Free wall: aVL deeper negative deflection
        if ecg.avlQSPattern {
            reasoning += "aVL QS pattern -> favors septal.\n"
            septalScore += 1
        } else if ecg.leadAVLPolarity == .negative {
            reasoning += "aVL negative (not QS) -> mild free wall lean.\n"
            freeWallScore += 1
        }

        // 3. MDI (Dixit) if available
        if ecg.maxDeflectionTimeMs > 0 && ecg.qrsDurationMs > 0 {
            let mdi = ecg.mdi
            if mdi < 0.55 {
                reasoning += "MDI = \(String(format: "%.2f", mdi)) < 0.55 -> septal.\n"
                septalScore += 2
            } else {
                reasoning += "MDI = \(String(format: "%.2f", mdi)) >= 0.55 -> free wall.\n"
                freeWallScore += 2
            }
        }

        // 4. Inferior lead notching
        // More common in free wall origin
        if ecg.inferiorLeadNotching {
            reasoning += "Notching in inferior leads -> favors free wall.\n"
            freeWallScore += 1
        }

        // 5. QRS duration (Kamakura)
        // Septal typically narrower QRS, free wall wider
        if ecg.qrsDurationMs >= 160 {
            reasoning += "QRS >= 160ms -> favors free wall (wider activation).\n"
            freeWallScore += 1
        } else if ecg.qrsDurationMs < 140 {
            reasoning += "QRS < 140ms -> favors septal (narrower activation).\n"
            septalScore += 1
        }

        // --- Anterior vs Posterior ---

        // Lead II vs Lead III amplitude ratio
        // Lead II > Lead III: posterior/inferior RVOT
        // Lead III > Lead II: anterior RVOT
        if ecg.leadIIGreaterThanIII {
            reasoning += "Lead II > Lead III -> posterior RVOT.\n"
            posteriorScore += 2
        } else {
            reasoning += "Lead III >= Lead II -> anterior RVOT.\n"
            anteriorScore += 2
        }

        // Build results
        reasoning += "\nScores: Septal=\(septalScore), FreeWall=\(freeWallScore), "
        reasoning += "Anterior=\(anteriorScore), Posterior=\(posteriorScore)\n"

        let isSeptal = septalScore > freeWallScore
        let isAnterior = anteriorScore > posteriorScore

        var origins: [OriginPrediction] = []

        // Primary prediction
        let primary: PVCOrigin
        if isSeptal && isAnterior {
            primary = .rvotSeptal
            reasoning += "-> RVOT Septal-Anterior region.\n"
        } else if isSeptal && !isAnterior {
            primary = .rvotSeptal
            reasoning += "-> RVOT Septal-Posterior region.\n"
        } else if !isSeptal && isAnterior {
            primary = .rvotFreeWall
            reasoning += "-> RVOT Free Wall-Anterior region.\n"
        } else {
            primary = .rvotFreeWall
            reasoning += "-> RVOT Free Wall-Posterior region.\n"
        }

        let diff = abs(septalScore - freeWallScore)
        let primaryConf: ConfidenceLevel = diff >= 3 ? .high : (diff >= 1 ? .moderate : .low)

        origins.append(OriginPrediction(
            origin: primary,
            confidence: primaryConf,
            detail: "Septal score \(septalScore) vs Free wall \(freeWallScore)")
        )

        // Secondary (opposite wall)
        let secondary: PVCOrigin = isSeptal ? .rvotFreeWall : .rvotSeptal
        origins.append(OriginPrediction(
            origin: secondary,
            confidence: diff >= 3 ? .unlikely : .low,
            detail: "Less likely based on morphological scoring")
        )

        // Also note anterior vs posterior
        let apOrigin: PVCOrigin = isAnterior ? .rvotAnterior : .rvotPosterior
        origins.append(OriginPrediction(
            origin: apOrigin,
            confidence: abs(anteriorScore - posteriorScore) >= 2 ? .moderate : .low,
            detail: "Anterior \(anteriorScore) vs Posterior \(posteriorScore)")
        )

        return result(origins: origins, reasoning: reasoning)
    }
}
