import Foundation
import SwiftUI

// MARK: - Result from a single algorithm

struct AlgorithmResult: Identifiable {
    let id = UUID()
    let algorithmName: String
    let authors: String
    let year: Int
    let journal: String
    let doi: String
    let predictedOrigins: [OriginPrediction]
    let reasoning: String
    let applicable: Bool       // whether this algorithm applies to the given morphology
    let notApplicableReason: String?

    var citation: String {
        "\(authors) (\(year)). \(journal). DOI: \(doi)"
    }

    var topPrediction: OriginPrediction? {
        predictedOrigins.first
    }
}

// MARK: - Single origin prediction with confidence

struct OriginPrediction: Identifiable {
    let id = UUID()
    let origin: PVCOrigin
    let confidence: ConfidenceLevel
    let detail: String

    var confidenceColor: Color {
        switch confidence {
        case .high: return .green
        case .moderate: return .yellow
        case .low: return .orange
        case .unlikely: return .red
        }
    }
}

enum ConfidenceLevel: String, Comparable {
    case high = "High"
    case moderate = "Moderate"
    case low = "Low"
    case unlikely = "Unlikely"

    private var sortOrder: Int {
        switch self {
        case .high: return 4
        case .moderate: return 3
        case .low: return 2
        case .unlikely: return 1
        }
    }

    static func < (lhs: ConfidenceLevel, rhs: ConfidenceLevel) -> Bool {
        lhs.sortOrder < rhs.sortOrder
    }
}

// MARK: - Consensus result combining all algorithms

struct ConsensusResult {
    let topOrigin: PVCOrigin
    let topRegion: String
    let agreementCount: Int
    let totalApplicable: Int
    let allResults: [AlgorithmResult]

    var agreementPercentage: Int {
        totalApplicable > 0 ? (agreementCount * 100) / totalApplicable : 0
    }

    /// All unique origins predicted across all algorithms, ranked by frequency
    var rankedOrigins: [(origin: PVCOrigin, count: Int)] {
        var counts: [PVCOrigin: Int] = [:]
        for result in allResults where result.applicable {
            if let top = result.topPrediction {
                counts[top.origin, default: 0] += 1
            }
        }
        return counts.sorted { $0.value > $1.value }.map { ($0.key, $0.value) }
    }
}
