import Foundation

/// Master localization algorithm based on Josephson / Segal decision tree.
///
/// Uses V1 morphology (LBBB vs RBBB), QRS axis, and precordial
/// transition zone to broadly localize PVC/VT origin to one of
/// ~12 anatomical regions.
///
/// Reference:
///   Segal OR, Chow AW, Wong T, et al.
///   "A novel algorithm for determining endocardial VT exit site
///    from 12-lead surface ECG characteristics in human,
///    infarct-related ventricular tachycardia."
///   J Cardiovasc Electrophysiol. 2007;18(2):161-168.
///
///   Also informed by:
///   Josephson ME. Clinical Cardiac Electrophysiology. 5th Ed.
///   Lippincott Williams & Wilkins, 2015.

struct JosephsonAlgorithm: PVCAlgorithm {
    let name = "Josephson-Segal Algorithm"
    let authors = "Segal OR, Chow AW, Wong T, et al."
    let year = 2007
    let journal = "J Cardiovasc Electrophysiol"
    let doi = "10.1111/j.1540-8167.2006.00687.x"
    let summary = "Master localization using V1 morphology, axis, and precordial transition to identify broad origin region."

    func analyze(_ ecg: ECGMeasurements) -> AlgorithmResult {
        var origins: [OriginPrediction] = []
        var reasoning = ""

        let isLBBB = ecg.bundleBranch == .lbbb
        let axis = ecg.axis
        let transition = ecg.pvcTransition

        if isLBBB {
            reasoning += "LBBB pattern in V1 -> origin likely RV or LVOT/aortic region.\n"
            origins = analyzeLBBB(ecg: ecg, axis: axis, transition: transition, reasoning: &reasoning)
        } else {
            reasoning += "RBBB pattern in V1 -> origin likely LV.\n"
            origins = analyzeRBBB(ecg: ecg, axis: axis, transition: transition, reasoning: &reasoning)
        }

        return result(origins: origins, reasoning: reasoning)
    }

    // MARK: - LBBB Branch

    private func analyzeLBBB(ecg: ECGMeasurements, axis: QRSAxis, transition: TransitionZone, reasoning: inout String) -> [OriginPrediction] {
        switch axis {
        case .inferior:
            reasoning += "Inferior axis -> outflow tract origin.\n"
            return analyzeLBBBInferior(ecg: ecg, transition: transition, reasoning: &reasoning)

        case .superior:
            reasoning += "Superior axis -> non-outflow tract, body of ventricle.\n"
            return analyzeLBBBSuperior(ecg: ecg, transition: transition, reasoning: &reasoning)

        case .rightward:
            reasoning += "Rightward axis with LBBB -> consider tricuspid annulus or RV.\n"
            return [
                OriginPrediction(origin: .tricuspidAnnulus, confidence: .moderate,
                    detail: "LBBB + rightward axis suggests tricuspid annular origin"),
                OriginPrediction(origin: .rvFreeWall, confidence: .low,
                    detail: "Also consider RV free wall")
            ]

        case .extreme:
            reasoning += "Extreme axis with LBBB -> unusual, consider apical or epicardial.\n"
            return [
                OriginPrediction(origin: .lvApical, confidence: .low,
                    detail: "Extreme axis with LBBB is uncommon"),
                OriginPrediction(origin: .epicardial, confidence: .low,
                    detail: "Consider epicardial origin")
            ]
        }
    }

    private func analyzeLBBBInferior(ecg: ECGMeasurements, transition: TransitionZone, reasoning: inout String) -> [OriginPrediction] {
        if transition.isEarly {
            reasoning += "Early transition (<=V3) -> LVOT or aortic cusp origin.\n"
            if ecg.leadIPolarity == .positive {
                reasoning += "Lead I positive -> favors LCC or L-R commissure.\n"
                return [
                    OriginPrediction(origin: .aorticLCC, confidence: .high,
                        detail: "LBBB + inferior axis + early transition + lead I positive"),
                    OriginPrediction(origin: .aorticLRCommissure, confidence: .moderate,
                        detail: "L-R commissure also possible"),
                    OriginPrediction(origin: .lvotGeneral, confidence: .moderate,
                        detail: "LVOT cannot be excluded")
                ]
            } else {
                reasoning += "Lead I negative/isoelectric -> favors RCC.\n"
                return [
                    OriginPrediction(origin: .aorticRCC, confidence: .high,
                        detail: "LBBB + inferior axis + early transition + lead I negative"),
                    OriginPrediction(origin: .lvotGeneral, confidence: .moderate,
                        detail: "LVOT possible")
                ]
            }
        } else {
            reasoning += "Late transition (>=V4) -> RVOT origin.\n"
            if ecg.leadIPolarity == .negative {
                reasoning += "Lead I negative -> RVOT free wall.\n"
                return [
                    OriginPrediction(origin: .rvotFreeWall, confidence: .high,
                        detail: "LBBB + inferior axis + late transition + lead I negative"),
                    OriginPrediction(origin: .rvotGeneral, confidence: .moderate,
                        detail: "RVOT general")
                ]
            } else {
                reasoning += "Lead I positive/isoelectric -> RVOT septal.\n"
                return [
                    OriginPrediction(origin: .rvotSeptal, confidence: .high,
                        detail: "LBBB + inferior axis + late transition + lead I positive/isoelectric"),
                    OriginPrediction(origin: .rvotGeneral, confidence: .moderate,
                        detail: "RVOT general")
                ]
            }
        }
    }

    private func analyzeLBBBSuperior(ecg: ECGMeasurements, transition: TransitionZone, reasoning: inout String) -> [OriginPrediction] {
        if transition.isEarly {
            reasoning += "Early transition + superior axis -> mitral annulus or LV anterolateral.\n"
            return [
                OriginPrediction(origin: .mitralAnnulus, confidence: .moderate,
                    detail: "LBBB + superior axis + early transition"),
                OriginPrediction(origin: .lvAnterolateral, confidence: .moderate,
                    detail: "LV anterolateral wall also possible")
            ]
        } else {
            if ecg.leadAVLPolarity == .positive {
                reasoning += "Late transition + aVL positive -> LV inferoseptal.\n"
                return [
                    OriginPrediction(origin: .lvInferoseptal, confidence: .high,
                        detail: "LBBB + superior axis + late transition + aVL positive"),
                    OriginPrediction(origin: .papillaryPosteromedial, confidence: .low,
                        detail: "Posteromedial papillary muscle possible")
                ]
            } else {
                reasoning += "Late transition + aVL negative -> LV apical.\n"
                return [
                    OriginPrediction(origin: .lvApical, confidence: .moderate,
                        detail: "LBBB + superior axis + late transition + aVL negative"),
                    OriginPrediction(origin: .rvFreeWall, confidence: .low,
                        detail: "RV free wall also possible")
                ]
            }
        }
    }

    // MARK: - RBBB Branch

    private func analyzeRBBB(ecg: ECGMeasurements, axis: QRSAxis, transition: TransitionZone, reasoning: inout String) -> [OriginPrediction] {
        switch axis {
        case .inferior:
            reasoning += "RBBB + inferior axis -> LV basal (mitral annulus, AMC).\n"
            return [
                OriginPrediction(origin: .lvBasal, confidence: .high,
                    detail: "RBBB + inferior axis suggests LV basal origin"),
                OriginPrediction(origin: .aortoMitralContinuity, confidence: .moderate,
                    detail: "Aorto-mitral continuity possible"),
                OriginPrediction(origin: .mitralAnnulus, confidence: .moderate,
                    detail: "Mitral annulus also possible")
            ]

        case .superior:
            reasoning += "RBBB + superior axis -> LV body or fascicular.\n"
            return analyzeRBBBSuperior(ecg: ecg, transition: transition, reasoning: &reasoning)

        case .rightward:
            reasoning += "RBBB + right axis -> fascicular VT (left posterior fascicle).\n"
            return [
                OriginPrediction(origin: .fascicularLPF, confidence: .high,
                    detail: "RBBB + right axis deviation, classic for LPF VT"),
                OriginPrediction(origin: .rvSeptum, confidence: .low,
                    detail: "Interventricular septum less likely")
            ]

        case .extreme:
            reasoning += "RBBB + extreme axis -> unusual, consider septum or epicardial.\n"
            return [
                OriginPrediction(origin: .rvSeptum, confidence: .low,
                    detail: "Extreme axis with RBBB is uncommon"),
                OriginPrediction(origin: .epicardial, confidence: .low,
                    detail: "Consider epicardial origin")
            ]
        }
    }

    private func analyzeRBBBSuperior(ecg: ECGMeasurements, transition: TransitionZone, reasoning: inout String) -> [OriginPrediction] {
        // Narrow QRS suggests fascicular VT
        if ecg.qrsDurationMs < 130 {
            reasoning += "Relatively narrow QRS (<130ms) -> fascicular VT likely.\n"
            return [
                OriginPrediction(origin: .fascicularLAF, confidence: .high,
                    detail: "RBBB + left superior axis + narrow QRS = left anterior fascicular VT"),
                OriginPrediction(origin: .lvInferoseptal, confidence: .low,
                    detail: "Inferoseptal LV less likely")
            ]
        }

        if transition.isEarly {
            reasoning += "Early transition -> LV anteroseptal.\n"
            return [
                OriginPrediction(origin: .lvAnterolateral, confidence: .moderate,
                    detail: "RBBB + superior axis + early transition"),
                OriginPrediction(origin: .papillaryAnterolateral, confidence: .low,
                    detail: "Anterolateral papillary muscle possible")
            ]
        } else {
            reasoning += "Late transition -> LV apical or inferoseptal.\n"
            return [
                OriginPrediction(origin: .lvApical, confidence: .moderate,
                    detail: "RBBB + superior axis + late transition"),
                OriginPrediction(origin: .lvInferoseptal, confidence: .moderate,
                    detail: "Inferoseptal also possible"),
                OriginPrediction(origin: .papillaryPosteromedial, confidence: .low,
                    detail: "Posteromedial papillary muscle possible")
            ]
        }
    }
}
