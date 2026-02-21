import SwiftUI

struct ContentView: View {
    @State private var ecgImage: UIImage?
    @State private var showCamera = false
    @State private var showPhotoLibrary = false
    @State private var showInput = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 8) {
                    Image(systemName: "waveform.path.ecg")
                        .font(.system(size: 64))
                        .foregroundColor(.red)

                    Text("PVC/VT Origin Locator")
                        .font(.title.bold())

                    Text("12-Lead ECG Algorithm Analysis")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.top, 40)

                // ECG image preview
                if let image = ecgImage {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(maxHeight: 200)
                        .cornerRadius(12)
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.secondary.opacity(0.3), lineWidth: 1)
                        )
                        .padding(.horizontal)
                }

                Spacer()

                // Action buttons
                VStack(spacing: 16) {
                    Button {
                        showCamera = true
                    } label: {
                        Label("Take ECG Photo", systemImage: "camera.fill")
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.blue)
                            .foregroundColor(.white)
                            .cornerRadius(12)
                    }

                    Button {
                        showPhotoLibrary = true
                    } label: {
                        Label("Select from Photos", systemImage: "photo.on.rectangle")
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.green)
                            .foregroundColor(.white)
                            .cornerRadius(12)
                    }

                    Button {
                        showInput = true
                    } label: {
                        Label(
                            ecgImage != nil ? "Analyze ECG" : "Manual Entry (No Photo)",
                            systemImage: "list.bullet.clipboard"
                        )
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.orange)
                        .foregroundColor(.white)
                        .cornerRadius(12)
                    }
                }
                .padding(.horizontal)

                // Disclaimer
                Text("For educational and research purposes only.\nNot a substitute for clinical electrophysiology evaluation.")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.bottom, 16)
            }
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showCamera) {
                ImagePicker(sourceType: .camera, selectedImage: $ecgImage)
                    .ignoresSafeArea()
            }
            .sheet(isPresented: $showPhotoLibrary) {
                ImagePicker(sourceType: .photoLibrary, selectedImage: $ecgImage)
                    .ignoresSafeArea()
            }
            .navigationDestination(isPresented: $showInput) {
                ECGInputView(ecgImage: ecgImage)
            }
        }
    }
}
