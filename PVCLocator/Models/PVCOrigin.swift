import Foundation

// MARK: - Anatomical origin locations for PVC / VT

enum PVCOrigin: String, CaseIterable, Identifiable {

    // Right Ventricular Outflow Tract
    case rvotSeptal          = "RVOT Septal"
    case rvotFreeWall        = "RVOT Free Wall"
    case rvotAnterior        = "RVOT Anterior"
    case rvotPosterior       = "RVOT Posterior"
    case rvotGeneral         = "RVOT (general)"

    // Left Ventricular Outflow Tract
    case lvotGeneral         = "LVOT (general)"

    // Aortic Cusps
    case aorticLCC           = "Left Coronary Cusp (LCC)"
    case aorticRCC           = "Right Coronary Cusp (RCC)"
    case aorticNCC           = "Non-Coronary Cusp (NCC)"
    case aorticLRCommissure  = "L-R Cusp Commissure"
    case aorticCuspGeneral   = "Aortic Cusp (general)"

    // Annular
    case mitralAnnulus        = "Mitral Annulus"
    case tricuspidAnnulus     = "Tricuspid Annulus"
    case aortoMitralContinuity = "Aorto-Mitral Continuity"

    // LV body
    case lvAnterolateral     = "LV Anterolateral"
    case lvInferoseptal      = "LV Inferoseptal"
    case lvApical            = "LV Apical"
    case lvBasal             = "LV Basal"
    case lvGeneral           = "LV (general)"

    // Papillary muscles
    case papillaryAnterolateral  = "Anterolateral Papillary Muscle"
    case papillaryPosteromedial  = "Posteromedial Papillary Muscle"

    // Epicardial
    case epicardial          = "Epicardial Origin"
    case lvSummit            = "LV Summit / Great Cardiac Vein"

    // Fascicular
    case fascicularLAF       = "Left Anterior Fascicle"
    case fascicularLPF       = "Left Posterior Fascicle"

    // RV body
    case rvFreeWall          = "RV Free Wall"
    case rvSeptum            = "RV Septum"

    var id: String { rawValue }

    /// Broad anatomical region for grouping
    var region: String {
        switch self {
        case .rvotSeptal, .rvotFreeWall, .rvotAnterior, .rvotPosterior, .rvotGeneral:
            return "Right Ventricular Outflow Tract"
        case .lvotGeneral:
            return "Left Ventricular Outflow Tract"
        case .aorticLCC, .aorticRCC, .aorticNCC, .aorticLRCommissure, .aorticCuspGeneral:
            return "Aortic Cusps"
        case .mitralAnnulus, .tricuspidAnnulus, .aortoMitralContinuity:
            return "Annular"
        case .lvAnterolateral, .lvInferoseptal, .lvApical, .lvBasal, .lvGeneral:
            return "Left Ventricle"
        case .papillaryAnterolateral, .papillaryPosteromedial:
            return "Papillary Muscles"
        case .epicardial, .lvSummit:
            return "Epicardial"
        case .fascicularLAF, .fascicularLPF:
            return "Fascicular"
        case .rvFreeWall, .rvSeptum:
            return "Right Ventricle"
        }
    }
}
