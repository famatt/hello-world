import Foundation

/// Protocol for all PVC/VT localization algorithms.
/// Each algorithm implements a published decision tree and returns
/// its prediction along with the paper citation.
protocol PVCAlgorithm {
    var name: String { get }
    var authors: String { get }
    var year: Int { get }
    var journal: String { get }
    var doi: String { get }
    var summary: String { get }

    /// Analyze ECG measurements and return localization result
    func analyze(_ ecg: ECGMeasurements) -> AlgorithmResult
}

extension PVCAlgorithm {
    /// Helper to build a result when the algorithm does not apply
    func notApplicable(reason: String) -> AlgorithmResult {
        AlgorithmResult(
            algorithmName: name,
            authors: authors,
            year: year,
            journal: journal,
            doi: doi,
            predictedOrigins: [],
            reasoning: reason,
            applicable: false,
            notApplicableReason: reason
        )
    }

    /// Helper to build a result with predictions
    func result(origins: [OriginPrediction], reasoning: String) -> AlgorithmResult {
        AlgorithmResult(
            algorithmName: name,
            authors: authors,
            year: year,
            journal: journal,
            doi: doi,
            predictedOrigins: origins,
            reasoning: reasoning,
            applicable: true,
            notApplicableReason: nil
        )
    }
}
