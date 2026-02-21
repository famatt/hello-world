import SwiftUI

/// Step-by-step guided ECG feature input form.
/// The user references the ECG photo while answering questions
/// about the morphological features.
struct ECGInputView: View {
    let ecgImage: UIImage?
    @State private var ecg = ECGMeasurements()
    @State private var currentStep = 0
    @State private var showResults = false
    @State private var showImageFullscreen = false
    @StateObject private var engine = AlgorithmEngine()

    private let totalSteps = 9

    var body: some View {
        VStack(spacing: 0) {
            // ECG image reference bar
            if let image = ecgImage {
                Button { showImageFullscreen = true } label: {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(maxHeight: 100)
                        .cornerRadius(8)
                        .overlay(
                            HStack {
                                Spacer()
                                Image(systemName: "arrow.up.left.and.arrow.down.right")
                                    .padding(4)
                                    .background(.ultraThinMaterial)
                                    .cornerRadius(4)
                                    .padding(4)
                            },
                            alignment: .bottomTrailing
                        )
                }
                .padding(.horizontal)
                .padding(.top, 4)
            }

            // Progress bar
            ProgressView(value: Double(currentStep + 1), total: Double(totalSteps))
                .padding(.horizontal)
                .padding(.vertical, 8)

            Text("Step \(currentStep + 1) of \(totalSteps)")
                .font(.caption)
                .foregroundColor(.secondary)

            // Step content
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    stepContent
                }
                .padding()
            }

            // Navigation buttons
            HStack {
                if currentStep > 0 {
                    Button("Back") {
                        withAnimation { currentStep -= 1 }
                    }
                    .buttonStyle(.bordered)
                }

                Spacer()

                if currentStep < totalSteps - 1 {
                    Button("Next") {
                        withAnimation { currentStep += 1 }
                    }
                    .buttonStyle(.borderedProminent)
                } else {
                    Button("Analyze") {
                        showResults = true
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.red)
                }
            }
            .padding()
        }
        .navigationTitle("ECG Features")
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showImageFullscreen) {
            if let image = ecgImage {
                ZoomableImageView(image: image)
            }
        }
        .navigationDestination(isPresented: $showResults) {
            ResultsView(consensus: engine.analyzeAll(ecg), ecgImage: ecgImage)
        }
    }

    // MARK: - Step Content

    @ViewBuilder
    private var stepContent: some View {
        switch currentStep {
        case 0: step1_BundleBranch
        case 1: step2_Axis
        case 2: step3_Transition
        case 3: step4_QRSDuration
        case 4: step5_V2Measurements
        case 5: step6_V1V2Detail
        case 6: step7_LeadIDetail
        case 7: step8_TimingMeasurements
        case 8: step9_AdditionalMorphology
        default: EmptyView()
        }
    }

    // MARK: Step 1 - Bundle Branch Pattern
    private var step1_BundleBranch: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("QRS Morphology in V1")
                .font(.headline)
            Text("Is the QRS in lead V1 predominantly positive (tall R wave) or predominantly negative (deep S wave)?")
                .font(.subheadline)
                .foregroundColor(.secondary)

            ForEach(BundleBranchPattern.allCases) { pattern in
                SelectionRow(
                    title: pattern.rawValue,
                    isSelected: ecg.bundleBranch == pattern
                ) {
                    ecg.bundleBranch = pattern
                }
            }

            InfoBox(text: "LBBB pattern (V1 negative): Origin is typically RV, RVOT, LVOT, or aortic cusps.\nRBBB pattern (V1 positive): Origin is typically LV.")
        }
    }

    // MARK: Step 2 - QRS Axis
    private var step2_Axis: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("QRS Axis (Limb Leads)")
                .font(.headline)
            Text("Determine the polarity of the QRS in leads I, aVF, and aVL.")
                .font(.subheadline)
                .foregroundColor(.secondary)

            PolarityPicker(label: "Lead I", selection: $ecg.leadIPolarity)
            PolarityPicker(label: "Lead aVF", selection: $ecg.leadAVFPolarity)
            PolarityPicker(label: "Lead aVL", selection: $ecg.leadAVLPolarity)

            Text("Calculated Axis: \(ecg.axis.rawValue)")
                .font(.callout.bold())
                .padding()
                .frame(maxWidth: .infinity)
                .background(Color.blue.opacity(0.1))
                .cornerRadius(8)

            InfoBox(text: "Inferior axis (I+, aVF+): Outflow tract origin.\nSuperior axis (I+, aVF-): Body of ventricle.\nRight axis (I-, aVF+): Consider fascicular or tricuspid annular.")
        }
    }

    // MARK: Step 3 - Precordial Transition
    private var step3_Transition: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Precordial R-Wave Transition")
                .font(.headline)
            Text("In which lead does the R wave first become taller than the S wave (R >= S)?")
                .font(.subheadline)
                .foregroundColor(.secondary)

            Text("PVC Transition Zone:")
                .font(.callout.bold())
            Picker("PVC Transition", selection: $ecg.pvcTransition) {
                ForEach(TransitionZone.allCases) { zone in
                    Text(zone.label).tag(zone)
                }
            }
            .pickerStyle(.segmented)

            Text("Sinus Rhythm Transition Zone:")
                .font(.callout.bold())
            Picker("Sinus Transition", selection: $ecg.sinusTransition) {
                ForEach(TransitionZone.allCases) { zone in
                    Text(zone.label).tag(zone)
                }
            }
            .pickerStyle(.segmented)

            InfoBox(text: "Early transition (V1-V3): Suggests LVOT or aortic cusp origin.\nLate transition (V4-V6): Suggests RVOT origin.\nSinus transition is needed for the V2 Transition Ratio (Betensky).")
        }
    }

    // MARK: Step 4 - QRS Duration
    private var step4_QRSDuration: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("QRS Duration")
                .font(.headline)
            Text("Measure the QRS duration (onset to offset) in the widest lead.")
                .font(.subheadline)
                .foregroundColor(.secondary)

            HStack {
                Text("\(Int(ecg.qrsDurationMs)) ms")
                    .font(.title2.bold())
                    .frame(width: 100)
                Slider(value: $ecg.qrsDurationMs, in: 80...250, step: 5)
            }

            InfoBox(text: "QRS < 130ms with RBBB + superior axis suggests fascicular VT.\nQRS > 160ms may suggest free wall or epicardial origin.")
        }
    }

    // MARK: Step 5 - V2 Amplitude Measurements
    private var step5_V2Measurements: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("V2 Amplitude Measurements")
                .font(.headline)
            Text("Measure R and S wave amplitudes in V2 during the PVC and during a sinus beat. Enter in mm (small squares).")
                .font(.subheadline)
                .foregroundColor(.secondary)

            Group {
                Text("During PVC:").font(.callout.bold())
                MeasurementRow(label: "V2 R-wave (mm)", value: $ecg.v2RWavePVC)
                MeasurementRow(label: "V2 S-wave (mm)", value: $ecg.v2SWavePVC)

                Text("During Sinus Rhythm:").font(.callout.bold())
                MeasurementRow(label: "V2 R-wave (mm)", value: $ecg.v2RWaveSinus)
                MeasurementRow(label: "V2 S-wave (mm)", value: $ecg.v2SWaveSinus)
            }

            if ecg.v2TransitionRatio > 0 {
                Text("V2 Transition Ratio: \(String(format: "%.2f", ecg.v2TransitionRatio))")
                    .font(.callout.bold())
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(ecg.v2TransitionRatio >= 0.6
                        ? Color.orange.opacity(0.1) : Color.blue.opacity(0.1))
                    .cornerRadius(8)
            }

            InfoBox(text: "V2TR >= 0.6: LVOT/aortic cusp (Betensky, sensitivity 95%, specificity 100%).\nV2TR < 0.6: RVOT origin.\nLeave at 0 if unable to measure.")
        }
    }

    // MARK: Step 6 - V1/V2 Detail
    private var step6_V1V2Detail: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("V1/V2 Detailed Morphology")
                .font(.headline)
            Text("For LBBB patterns, examine the initial portion of the QRS in V1 and V2.")
                .font(.subheadline)
                .foregroundColor(.secondary)

            Toggle("Initial r-wave present in V1", isOn: $ecg.v1HasInitialR)
            Toggle("Initial r-wave present in V2", isOn: $ecg.v2HasInitialR)

            MeasurementRow(label: "V1 R-wave duration (ms)", value: $ecg.v1RWaveDurationMs)
            MeasurementRow(label: "V1 R-wave amplitude (mm)", value: $ecg.v1RWaveAmplitude)
            MeasurementRow(label: "V1 S-wave amplitude (mm)", value: $ecg.v1SWaveAmplitude)

            InfoBox(text: "R-wave duration index = R-wave duration / QRS duration.\n>= 50% suggests LVOT (Ouyang).\nR/S ratio >= 30% also suggests LVOT.")
        }
    }

    // MARK: Step 7 - Lead I Detail
    private var step7_LeadIDetail: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Lead I & Inferior Lead Details")
                .font(.headline)

            PolarityPicker(label: "Lead II", selection: $ecg.leadIIPolarity)
            PolarityPicker(label: "Lead III", selection: $ecg.leadIIIPolarity)

            Toggle("Notching present in lead I", isOn: $ecg.leadINotching)
            Toggle("Notching in inferior leads (II, III, aVF)", isOn: $ecg.inferiorLeadNotching)
            Toggle("Q wave in inferior leads", isOn: $ecg.qInInferiorLeads)
            Toggle("Lead II amplitude > Lead III", isOn: $ecg.leadIIGreaterThanIII)

            InfoBox(text: "Lead I negative + LBBB + inferior axis: RVOT free wall.\nNotching in inferior leads: suggests free wall RVOT.\nLead II > III: posterior RVOT. Lead III > II: anterior.")
        }
    }

    // MARK: Step 8 - Timing Measurements
    private var step8_TimingMeasurements: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Timing Measurements")
                .font(.headline)
            Text("These measurements help identify epicardial origin. Leave at 0 if unable to measure.")
                .font(.subheadline)
                .foregroundColor(.secondary)

            MeasurementRow(label: "Pseudo-delta wave (ms)", value: $ecg.pseudoDeltaWaveMs)
            MeasurementRow(label: "Intrinsicoid deflection (ms)", value: $ecg.intrinsicoidDeflectionMs)
            MeasurementRow(label: "Shortest RS complex (ms)", value: $ecg.shortestRSComplexMs)
            MeasurementRow(label: "Time to max deflection (ms)", value: $ecg.maxDeflectionTimeMs)

            if ecg.mdi > 0 {
                Text("MDI: \(String(format: "%.2f", ecg.mdi))")
                    .font(.callout.bold())
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(ecg.mdi >= 0.55
                        ? Color.orange.opacity(0.1) : Color.green.opacity(0.1))
                    .cornerRadius(8)
            }

            InfoBox(text: "Berruezo epicardial criteria:\n- Pseudo-delta >= 34ms\n- Intrinsicoid deflection >= 85ms\n- Shortest RS >= 121ms\n\nDixit MDI >= 0.55: free wall / epicardial.\nMDI < 0.55: septal.")
        }
    }

    // MARK: Step 9 - Additional Morphology
    private var step9_AdditionalMorphology: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Additional Morphology")
                .font(.headline)

            Toggle("aVL shows QS pattern", isOn: $ecg.avlQSPattern)
            Toggle("V1 shows W or M pattern", isOn: $ecg.v1WPattern)

            Divider()

            Text("Review Summary")
                .font(.headline)

            VStack(alignment: .leading, spacing: 6) {
                SummaryRow(label: "V1 Pattern", value: ecg.bundleBranch.shortName)
                SummaryRow(label: "Axis", value: ecg.axis.rawValue)
                SummaryRow(label: "PVC Transition", value: ecg.pvcTransition.label)
                SummaryRow(label: "QRS Duration", value: "\(Int(ecg.qrsDurationMs))ms")
                if ecg.v2TransitionRatio > 0 {
                    SummaryRow(label: "V2TR", value: String(format: "%.2f", ecg.v2TransitionRatio))
                }
                if ecg.mdi > 0 {
                    SummaryRow(label: "MDI", value: String(format: "%.2f", ecg.mdi))
                }
            }
            .padding()
            .background(Color.gray.opacity(0.1))
            .cornerRadius(8)

            InfoBox(text: "Press 'Analyze' to run all 7 algorithms and get a consensus localization result with paper citations.")
        }
    }
}

// MARK: - Reusable Components

private struct SelectionRow: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack {
                Text(title)
                    .foregroundColor(.primary)
                Spacer()
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .foregroundColor(isSelected ? .blue : .gray)
            }
            .padding()
            .background(isSelected ? Color.blue.opacity(0.08) : Color.gray.opacity(0.05))
            .cornerRadius(8)
        }
    }
}

private struct PolarityPicker: View {
    let label: String
    @Binding var selection: QRSPolarity

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.callout.bold())
            Picker(label, selection: $selection) {
                ForEach(QRSPolarity.allCases) { polarity in
                    Text(polarity.rawValue).tag(polarity)
                }
            }
            .pickerStyle(.segmented)
        }
    }
}

private struct MeasurementRow: View {
    let label: String
    @Binding var value: Double

    var body: some View {
        HStack {
            Text(label)
                .font(.callout)
            Spacer()
            TextField("0", value: $value, format: .number)
                .keyboardType(.decimalPad)
                .textFieldStyle(.roundedBorder)
                .frame(width: 80)
        }
    }
}

private struct InfoBox: View {
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "info.circle")
                .foregroundColor(.blue)
            Text(text)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color.blue.opacity(0.05))
        .cornerRadius(8)
    }
}

private struct SummaryRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label).font(.caption).foregroundColor(.secondary)
            Spacer()
            Text(value).font(.caption.bold())
        }
    }
}

/// Fullscreen zoomable image viewer for the ECG photo.
struct ZoomableImageView: View {
    let image: UIImage
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView([.horizontal, .vertical]) {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
