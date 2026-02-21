import Foundation

/// Orchestrates all PVC/VT localization algorithms and produces
/// a consensus result.
final class AlgorithmEngine: ObservableObject {

    /// All registered algorithms in analysis order
    let algorithms: [PVCAlgorithm] = [
        JosephsonAlgorithm(),
        BetenskyAlgorithm(),
        OuyangAlgorithm(),
        YamadaAlgorithm(),
        DixitAlgorithm(),
        BerruezoAlgorithm(),
        RVOTMorphologyAlgorithm()
    ]

    /// Run all algorithms and return individual + consensus results
    func analyzeAll(_ ecg: ECGMeasurements) -> ConsensusResult {
        let results = algorithms.map { $0.analyze(ecg) }
        return buildConsensus(from: results)
    }

    /// Build consensus from individual algorithm results
    private func buildConsensus(from results: [AlgorithmResult]) -> ConsensusResult {
        let applicable = results.filter { $0.applicable }

        // Count origin predictions weighted by confidence
        var originScores: [PVCOrigin: Double] = [:]
        var originCounts: [PVCOrigin: Int] = [:]

        for result in applicable {
            if let top = result.topPrediction {
                let weight: Double
                switch top.confidence {
                case .high: weight = 3.0
                case .moderate: weight = 2.0
                case .low: weight = 1.0
                case .unlikely: weight = 0.0
                }
                originScores[top.origin, default: 0] += weight
                originCounts[top.origin, default: 0] += 1
            }
        }

        // Also consider region-level agreement (e.g., RVOT septal and RVOT general
        // should both count toward "RVOT")
        var regionScores: [String: Double] = [:]
        for (origin, score) in originScores {
            regionScores[origin.region, default: 0] += score
        }

        // Find the top origin by weighted score
        let topOrigin = originScores.max(by: { $0.value < $1.value })?.key ?? .rvotGeneral
        let topRegion = regionScores.max(by: { $0.value < $1.value })?.key ?? "Unknown"
        let agreementCount = originCounts[topOrigin] ?? 0

        return ConsensusResult(
            topOrigin: topOrigin,
            topRegion: topRegion,
            agreementCount: agreementCount,
            totalApplicable: applicable.count,
            allResults: results
        )
    }

    /// Get a brief summary of which algorithms are applicable
    /// for a given ECG morphology (useful for UI hints)
    func applicableSummary(for ecg: ECGMeasurements) -> String {
        let applicable = algorithms.filter { alg in
            let result = alg.analyze(ecg)
            return result.applicable
        }
        return "\(applicable.count) of \(algorithms.count) algorithms applicable"
    }
}
