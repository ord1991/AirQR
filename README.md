# 📡 AirQR: Optical Air-Gap File Transfer System

AirQR is a robust, symmetric Python-based solution for transferring files between two air-gapped computers using nothing but their screens and webcams. It uses animated QR codes to create a bi-directional data link.

---

## 🚀 Quick Start

### 📦 Installation
Ensure you have Python 3.10+ installed. Install the required dependencies:
```bash
pip install opencv-python qrcode pyzbar numpy
```
*Note: Linux users might need `sudo apt install libzbar0` for the scanning engine.*

### 📤 Sending a File
```bash
python airqr.py --send document.pdf --camera 0
```

### 📥 Receiving a File
```bash
python airqr.py --receive --camera 0
```

---

## 🛠 Engineering Architecture

### 🏗️ Symmetric Design
AirQR uses a **Single-Binary Symmetric Architecture**. Both machines run the exact same code. This simplifies deployment in restricted environments. The script spawns two parallel threads:
1.  **Display Thread 📺**: Renders QR codes on the screen using OpenCV.
2.  **Capture Thread 📷**: Captures frames from the webcam, preprocesses them, and decodes QR data in real-time.

### 📜 The Protocol: Optical Stop-and-Wait ARQ
To ensure reliability over an unstable optical link, AirQR implements a custom protocol inspired by TCP/IP:

1.  **Handshake (Header QR)**:
    - The Sender generates a unique **32-bit Session ID** 🔑.
    - It displays a Header QR containing: Filename, File Size, Total Chunks, and the **SHA-256 Hash** 🛡️ of the original file.
    - The Receiver captures this and displays an **ACK (Acknowledgment) 0** QR.
2.  **Data Transfer**:
    - The Sender reads the ACK 0 and begins displaying **Data QR 1**.
    - Each Data QR contains: `[Type: Data] | [Session ID] | [Seq Number] | [1KB Payload]`.
    - The Receiver captures the chunk and updates its screen to show **ACK [Seq Number]**.
    - The Sender only advances to the next chunk once it visually confirms the correct ACK.
3.  **Verification**:
    - Once all chunks are collected, the Receiver reassembles the file.
    - It calculates the SHA-256 hash and compares it to the metadata. **Bit-for-bit integrity guaranteed!** ✅

### 📐 QR Specifications
- **Version**: 40 (177x177 modules) for maximum data density.
- **Error Correction**: Level H (30% restoration capacity) to survive screen glare and camera noise 🌫️.
- **Encoding**: Raw Byte Mode for binary file support (PDF, EXE, DOCX, etc.).

### 👁️ Computer Vision Preprocessing
Optical links face challenges like screen refresh rates and glare. AirQR uses OpenCV to:
- Convert frames to **Grayscale** 🏁.
- Apply **Otsu’s Binarization** 🌓 to maximize contrast between modules.
- Filter out noise to ensure high-speed decoding.

---

## 📊 Technical Specs
| Feature | Specification |
| :--- | :--- |
| **Payload Size** | 1024 Bytes / Frame |
| **Integrity** | SHA-256 |
| **Collision Avoidance** | 32-bit Session ID |
| **Max Capacity** | Tested up to several MBs |
| **UI** | OpenCV (Live Feed + Display) |

---

## ⚠️ Important Considerations
- **Distance**: Keep the devices 10-30cm apart for optimal focus.
- **Brightness**: Ensure the sender's screen is at high brightness.
- **Focus**: Tap your webcam or adjust settings if the image appears blurry in the "Scanner Feed" window.

---
*Created by an expert Python & Network Engineer. Secure. Air-Gapped. Reliable.* 🔒
