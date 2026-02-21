import Foundation

/// Yamada algorithm for sublocalization of aortic cusp VTs
/// to specific cusps (LCC, RCC, NCC, L-R commissure).
///
/// Only applicable when LVOT / aortic cusp origin is suspected
/// (LBBB + inferior axis + early precordial transition).
///
/// Reference:
///   Yamada T, McElderry HT, Doppalapudi H, et al.
///   "Idiopathic ventricular arrhythmias originating from the
///    aortic root: prevalence, electrocardiographic and
///    electrophysiologic characteristics, and results of
///    radiofrequency catheter ablation."
///   J Am Coll Cardiol. 2008;52(2):139-147.

struct YamadaAlgorithm: PVCAlgorithm {
    let name = "Yamada Aortic Cusp Algorithm"
    let authors = "Yamada T, McElderry HT, Doppalapudi H, et al."
    let year = 2008
    let journal = "J Am Coll Cardiol"
    let doi = "10.1016/j.jacc.2008.03.040"
    let summary = "Sublocalizes aortic cusp VTs to LCC, RCC, NCC, or L-R commissure using lead I polarity, V1 morphology, and transition zone."

    func analyze(_ ecg: ECGMeasurements) -> AlgorithmResult {
        // Applies to LBBB + inferior axis + early transition (cusp morphology)
        guard ecg.bundleBranch == .lbbb && ecg.axis == .inferior else {
            return notApplicable(
                reason: "Yamada cusp algorithm only applies to LBBB + inferior axis morphology."
            )
        }

        guard ecg.pvcTransition.isEarly else {
            return notApplicable(
                reason: "Yamada cusp algorithm applies when precordial transition is early (V1-V3), suggesting aortic cusp origin."
            )
        }

        var reasoning = "LBBB + inferior axis + early transition -> aortic cusp morphology.\n"
        reasoning += "Applying Yamada cusp differentiation criteria:\n"

        let leadINeg = ecg.leadIPolarity == .negative
        let leadIIso = ecg.leadIPolarity == .isoelectric
        let leadIPos = ecg.leadIPolarity == .positive
        let hasWPatternV1 = ecg.v1WPattern

        // LCC: Lead I positive, early transition (V1-V2), taller R waves in V1/V2
        // RCC: Lead I negative or isoelectric, transition V1-V3
        // L-R commissure: M or W pattern in V1, features intermediate
        // NCC: Broader QRS, less common, later transition than LCC

        if hasWPatternV1 {
            reasoning += "W or M pattern in V1 -> L-R cusp commissure origin.\n"
            return result(origins: [
                OriginPrediction(origin: .aorticLRCommissure, confidence: .high,
                    detail: "M/W pattern in V1 characteristic of L-R commissure"),
                OriginPrediction(origin: .aorticLCC, confidence: .low,
                    detail: "LCC less likely with W pattern"),
                OriginPrediction(origin: .aorticRCC, confidence: .low,
                    detail: "RCC less likely with W pattern")
            ], reasoning: reasoning)
        }

        if leadIPos {
            reasoning += "Lead I positive -> left coronary cusp (LCC).\n"
            reasoning += "LCC VTs typically show: positive lead I, tall R in V1/V2, "
            reasoning += "early transition by V1-V2, monophasic R in inferior leads.\n"

            let transitionV1V2 = ecg.pvcTransition.rawValue <= 2
            let conf: ConfidenceLevel = transitionV1V2 ? .high : .moderate

            return result(origins: [
                OriginPrediction(origin: .aorticLCC, confidence: conf,
                    detail: "Lead I positive + early transition = LCC"),
                OriginPrediction(origin: .aorticLRCommissure, confidence: .low,
                    detail: "L-R commissure possible if notching in V1"),
                OriginPrediction(origin: .lvotGeneral, confidence: .low,
                    detail: "Sub-valvular LVOT also possible")
            ], reasoning: reasoning)
        }

        if leadINeg || leadIIso {
            reasoning += "Lead I negative/isoelectric -> right coronary cusp (RCC).\n"
            reasoning += "RCC VTs: negative or isoelectric lead I, "
            reasoning += "transition typically V2-V3, prominent R in inferior leads.\n"

            // Distinguish from NCC: NCC tends to have broader QRS and later transition
            if ecg.qrsDurationMs > 160 && ecg.pvcTransition.rawValue >= 3 {
                reasoning += "Broader QRS (>160ms) with V3 transition raises possibility of NCC.\n"
                return result(origins: [
                    OriginPrediction(origin: .aorticNCC, confidence: .moderate,
                        detail: "Lead I neg + broad QRS + V3 transition suggests NCC"),
                    OriginPrediction(origin: .aorticRCC, confidence: .moderate,
                        detail: "RCC also possible"),
                    OriginPrediction(origin: .aorticCuspGeneral, confidence: .moderate,
                        detail: "Cusp origin confirmed")
                ], reasoning: reasoning)
            }

            return result(origins: [
                OriginPrediction(origin: .aorticRCC, confidence: .high,
                    detail: "Lead I negative/isoelectric + early transition = RCC"),
                OriginPrediction(origin: .aorticNCC, confidence: .low,
                    detail: "NCC less likely with typical QRS duration"),
                OriginPrediction(origin: .lvotGeneral, confidence: .low,
                    detail: "Sub-valvular LVOT also possible")
            ], reasoning: reasoning)
        }

        // Fallback
        reasoning += "Indeterminate lead I polarity, general aortic cusp.\n"
        return result(origins: [
            OriginPrediction(origin: .aorticCuspGeneral, confidence: .moderate,
                detail: "Aortic cusp origin likely but specific cusp unclear")
        ], reasoning: reasoning)
    }
}
