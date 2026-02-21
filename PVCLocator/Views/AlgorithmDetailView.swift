import SwiftUI

/// Detailed view for a single algorithm result, showing the
/// full reasoning chain and paper citation.
struct AlgorithmDetailView: View {
    let result: AlgorithmResult

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                if result.applicable {
                    predictions
                    reasoningSection
                }
                citationSection
            }
            .padding()
        }
        .navigationTitle(result.algorithmName)
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Header

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: result.applicable
                    ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .foregroundColor(result.applicable ? .green : .orange)
                Text(result.applicable ? "Algorithm Applied" : "Not Applicable")
                    .font(.subheadline.bold())
                    .foregroundColor(result.applicable ? .green : .orange)
            }

            if let reason = result.notApplicableReason {
                Text(reason)
                    .font(.callout)
                    .foregroundColor(.secondary)
                    .padding()
                    .background(Color.orange.opacity(0.05))
                    .cornerRadius(8)
            }
        }
    }

    // MARK: - Predictions

    private var predictions: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Predictions")
                .font(.headline)

            ForEach(result.predictedOrigins) { prediction in
                HStack(alignment: .top, spacing: 12) {
                    Circle()
                        .fill(prediction.confidenceColor)
                        .frame(width: 12, height: 12)
                        .padding(.top, 4)

                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(prediction.origin.rawValue)
                                .font(.callout.bold())
                            Spacer()
                            Text(prediction.confidence.rawValue)
                                .font(.caption)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 2)
                                .background(prediction.confidenceColor.opacity(0.15))
                                .cornerRadius(4)
                        }

                        Text(prediction.origin.region)
                            .font(.caption)
                            .foregroundColor(.secondary)

                        Text(prediction.detail)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                .padding()
                .background(Color.gray.opacity(0.05))
                .cornerRadius(8)
            }
        }
    }

    // MARK: - Reasoning

    private var reasoningSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Reasoning")
                .font(.headline)

            Text(result.reasoning)
                .font(.system(.caption, design: .monospaced))
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.gray.opacity(0.05))
                .cornerRadius(8)
        }
    }

    // MARK: - Citation

    private var citationSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Reference")
                .font(.headline)

            VStack(alignment: .leading, spacing: 6) {
                Text(result.authors)
                    .font(.callout)

                Text("(\(result.year))")
                    .font(.callout.bold())

                Text(result.journal)
                    .font(.callout.italic())

                HStack {
                    Text("DOI:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(result.doi)
                        .font(.caption)
                        .foregroundColor(.blue)
                }
            }
            .padding()
            .background(Color.blue.opacity(0.05))
            .cornerRadius(8)
        }
    }
}
