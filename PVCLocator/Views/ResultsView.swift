import SwiftUI

/// Displays the consensus result and all individual algorithm results
/// with citations.
struct ResultsView: View {
    let consensus: ConsensusResult
    let ecgImage: UIImage?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                consensusCard
                rankedOrigins
                algorithmResults
                disclaimer
            }
            .padding()
        }
        .navigationTitle("Analysis Results")
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Consensus Card

    private var consensusCard: some View {
        VStack(spacing: 12) {
            Image(systemName: "target")
                .font(.system(size: 40))
                .foregroundColor(.red)

            Text("Most Likely Origin")
                .font(.caption)
                .foregroundColor(.secondary)

            Text(consensus.topOrigin.rawValue)
                .font(.title2.bold())
                .multilineTextAlignment(.center)

            Text(consensus.topRegion)
                .font(.subheadline)
                .foregroundColor(.secondary)

            HStack(spacing: 16) {
                StatBadge(
                    label: "Agreement",
                    value: "\(consensus.agreementCount)/\(consensus.totalApplicable)",
                    color: consensus.agreementPercentage >= 50 ? .green : .orange
                )
                StatBadge(
                    label: "Algorithms",
                    value: "\(consensus.totalApplicable) applicable",
                    color: .blue
                )
            }
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.red.opacity(0.05))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.red.opacity(0.2), lineWidth: 1)
                )
        )
    }

    // MARK: - Ranked Origins

    private var rankedOrigins: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Ranked Predictions")
                .font(.headline)

            ForEach(Array(consensus.rankedOrigins.enumerated()), id: \.offset) { index, item in
                HStack {
                    Text("#\(index + 1)")
                        .font(.caption.bold())
                        .foregroundColor(.white)
                        .frame(width: 28, height: 28)
                        .background(index == 0 ? Color.red : Color.gray)
                        .cornerRadius(14)

                    VStack(alignment: .leading) {
                        Text(item.origin.rawValue)
                            .font(.callout.bold())
                        Text(item.origin.region)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer()

                    Text("\(item.count) algo\(item.count == 1 ? "" : "s")")
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(6)
                }
                .padding(.vertical, 4)
            }
        }
    }

    // MARK: - Individual Algorithm Results

    private var algorithmResults: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Algorithm Details")
                .font(.headline)

            ForEach(consensus.allResults) { result in
                NavigationLink {
                    AlgorithmDetailView(result: result)
                } label: {
                    AlgorithmCard(result: result)
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Disclaimer

    private var disclaimer: some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider()
            Text("Important Notice")
                .font(.caption.bold())
                .foregroundColor(.red)
            Text("This tool is for educational and research purposes only. PVC/VT localization from the surface ECG has inherent limitations. Final determination of arrhythmia origin requires invasive electrophysiology study with activation mapping and/or pace mapping. Always correlate with clinical context and imaging.")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Algorithm Card

private struct AlgorithmCard: View {
    let result: AlgorithmResult

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(result.algorithmName)
                    .font(.callout.bold())
                Spacer()
                if result.applicable {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.caption)
                } else {
                    Text("N/A")
                        .font(.caption)
                        .foregroundColor(.orange)
                }
            }

            Text("\(result.authors) (\(result.year))")
                .font(.caption2)
                .foregroundColor(.secondary)

            if result.applicable, let top = result.topPrediction {
                HStack {
                    Circle()
                        .fill(top.confidenceColor)
                        .frame(width: 8, height: 8)
                    Text(top.origin.rawValue)
                        .font(.caption)
                    Text("(\(top.confidence.rawValue))")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            } else if let reason = result.notApplicableReason {
                Text(reason)
                    .font(.caption2)
                    .foregroundColor(.orange)
                    .lineLimit(2)
            }
        }
        .padding()
        .background(Color.gray.opacity(0.05))
        .cornerRadius(10)
    }
}

// MARK: - Stat Badge

private struct StatBadge: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.callout.bold())
                .foregroundColor(color)
            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(color.opacity(0.1))
        .cornerRadius(8)
    }
}
