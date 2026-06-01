import os
import sys
import time
import hashlib
import struct
import threading
import secrets
import argparse
from typing import Optional, Tuple

import cv2
import qrcode
import numpy as np
from pyzbar import pyzbar

# --- Constants ---
QR_VERSION = 40
QR_ERROR_CORRECT = qrcode.constants.ERROR_CORRECT_H
CHUNK_SIZE = 1024  # 1KB payload per Data QR

PACKET_TYPE_HEADER = 0
PACKET_TYPE_DATA = 1
PACKET_TYPE_ACK = 2

# Struct formats (Big-endian)
# Header: Type(B), SessionID(I), FileSize(Q), NumChunks(I), Hash(32s), FilenameLen(H)
HEADER_STRUCT_BASE = "!BIQI32sH"
# Data: Type(B), SessionID(I), SeqNum(I), Payload(1024s)
DATA_STRUCT = f"!BII{CHUNK_SIZE}s"
# ACK: Type(B), SessionID(I), SeqNum(I)
ACK_STRUCT = "!BII"

class AirQRTransceiver:
    def __init__(self, camera_index: int):
        self.camera_index = camera_index
        self.current_qr_image = None
        self.last_received_packet = None
        self.running = True
        self.lock = threading.Lock()

    def display_thread(self):
        """Thread to display the current QR code on screen."""
        cv2.namedWindow("AirQR - Display", cv2.WINDOW_NORMAL)
        while self.running:
            with self.lock:
                img = self.current_qr_image

            if img is not None:
                cv2.imshow("AirQR - Display", img)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.running = False
                break
        cv2.destroyWindow("AirQR - Display")

    def capture_thread(self):
        """Thread to capture and decode QR codes from webcam."""
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            print(f"Error: Could not open camera {self.camera_index}")
            self.running = False
            return

        while self.running:
            ret, frame = cap.read()
            if not ret:
                continue

            # Preprocessing for better QR detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Increase contrast/brightness if needed, or simple thresholding
            _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

            # Show camera feed (optional, but helpful for alignment)
            cv2.imshow("AirQR - Scanner Feed", frame)

            # Try to decode QR
            decoded_objs = pyzbar.decode(gray) # Often works better on gray than thresh
            if not decoded_objs:
                decoded_objs = pyzbar.decode(thresh)

            for obj in decoded_objs:
                with self.lock:
                    self.last_received_packet = obj.data
                break # Only process one QR per frame

            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.running = False
                break

        cap.release()
        cv2.destroyWindow("AirQR - Scanner Feed")

    def set_qr_data(self, data: bytes):
        """Generates a QR image from raw bytes and updates the display."""
        qr = qrcode.QRCode(
            version=QR_VERSION,
            error_correction=QR_ERROR_CORRECT,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=False)
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert PIL image to OpenCV format (numpy array)
        open_cv_image = np.array(img.convert('RGB'))
        # Convert RGB to BGR
        open_cv_image = open_cv_image[:, :, ::-1].copy()

        with self.lock:
            self.current_qr_image = open_cv_image

    def get_last_received(self) -> Optional[bytes]:
        with self.lock:
            data = self.last_received_packet
            self.last_received_packet = None # Consume it
            return data

def run_sender(file_path: str, camera_index: int):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    filename = os.path.basename(file_path)
    filename_bytes = filename.encode('utf-8')
    file_size = os.path.getsize(file_path)

    with open(file_path, "rb") as f:
        file_data = f.read()

    file_hash = hashlib.sha256(file_data).digest()
    num_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    session_id = secrets.randbits(32)

    print(f"Sending file: {filename} ({file_size} bytes)")
    print(f"Session ID: {session_id:08X}")
    print(f"Total chunks: {num_chunks}")
    print(f"SHA-256: {file_hash.hex()}")

    transceiver = AirQRTransceiver(camera_index)

    t_display = threading.Thread(target=transceiver.display_thread)
    t_capture = threading.Thread(target=transceiver.capture_thread)
    t_display.start()
    t_capture.start()

    try:
        # 1. Send Header
        header_base = struct.pack(HEADER_STRUCT_BASE, PACKET_TYPE_HEADER, session_id, file_size, num_chunks, file_hash, len(filename_bytes))
        header_packet = header_base + filename_bytes

        print("Displaying Header QR. Waiting for ACK 0...")
        transceiver.set_qr_data(header_packet)

        while transceiver.running:
            raw_ack = transceiver.get_last_received()
            if raw_ack and len(raw_ack) == struct.calcsize(ACK_STRUCT):
                p_type, s_id, seq = struct.unpack(ACK_STRUCT, raw_ack)
                if p_type == PACKET_TYPE_ACK and s_id == session_id and seq == 0:
                    print("Header ACK'd.")
                    break
            time.sleep(0.1)

        # 2. Send Data Chunks
        for i in range(num_chunks):
            if not transceiver.running: break

            start_offset = i * CHUNK_SIZE
            chunk_data = file_data[start_offset : start_offset + CHUNK_SIZE]
            # Pad chunk_data if it's the last one
            if len(chunk_data) < CHUNK_SIZE:
                chunk_data = chunk_data.ljust(CHUNK_SIZE, b'\x00')

            data_packet = struct.pack(DATA_STRUCT, PACKET_TYPE_DATA, session_id, i + 1, chunk_data)

            print(f"Sending Chunk {i+1}/{num_chunks}...")
            transceiver.set_qr_data(data_packet)

            while transceiver.running:
                raw_ack = transceiver.get_last_received()
                if raw_ack and len(raw_ack) == struct.calcsize(ACK_STRUCT):
                    p_type, s_id, seq = struct.unpack(ACK_STRUCT, raw_ack)
                    if p_type == PACKET_TYPE_ACK and s_id == session_id and seq == (i + 1):
                        print(f"Chunk {i+1} ACK'd.")
                        break
                time.sleep(0.1)

        print("Transfer Complete.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        transceiver.running = False
        t_display.join()
        t_capture.join()

def run_receiver(camera_index: int):
    transceiver = AirQRTransceiver(camera_index)

    t_display = threading.Thread(target=transceiver.display_thread)
    t_capture = threading.Thread(target=transceiver.capture_thread)
    t_display.start()
    t_capture.start()

    try:
        session_id = None
        file_size = 0
        num_chunks = 0
        expected_hash = b''
        filename = ""
        received_chunks = {}

        print("Waiting for Header QR...")

        # 1. Wait for Header
        while transceiver.running:
            raw_packet = transceiver.get_last_received()
            if raw_packet and len(raw_packet) >= struct.calcsize(HEADER_STRUCT_BASE):
                p_type = raw_packet[0]
                if p_type == PACKET_TYPE_HEADER:
                    p_type, session_id, file_size, num_chunks, expected_hash, name_len = struct.unpack(HEADER_STRUCT_BASE, raw_packet[:struct.calcsize(HEADER_STRUCT_BASE)])
                    filename = raw_packet[struct.calcsize(HEADER_STRUCT_BASE):struct.calcsize(HEADER_STRUCT_BASE)+name_len].decode('utf-8')

                    print(f"Header received! File: {filename}, Size: {file_size}, Chunks: {num_chunks}")

                    # Send ACK 0
                    ack_packet = struct.pack(ACK_STRUCT, PACKET_TYPE_ACK, session_id, 0)
                    transceiver.set_qr_data(ack_packet)
                    break
            time.sleep(0.1)

        # 2. Receive Data
        start_time = time.time()
        while transceiver.running and len(received_chunks) < num_chunks:
            raw_packet = transceiver.get_last_received()
            if raw_packet and len(raw_packet) == struct.calcsize(DATA_STRUCT):
                p_type, s_id, seq, payload = struct.unpack(DATA_STRUCT, raw_packet)
                if p_type == PACKET_TYPE_DATA and s_id == session_id:
                    if seq not in received_chunks:
                        # If this is the last chunk, we might need to trim it later based on file_size
                        received_chunks[seq] = payload
                        elapsed = time.time() - start_time
                        speed = (len(received_chunks) * CHUNK_SIZE) / (elapsed if elapsed > 0 else 1) / 1024
                        print(f"Received Chunk {seq}/{num_chunks} ({speed:.2f} KB/s)")

                    # Always ACK the received chunk (Sender might have missed previous ACK)
                    ack_packet = struct.pack(ACK_STRUCT, PACKET_TYPE_ACK, session_id, seq)
                    transceiver.set_qr_data(ack_packet)

            # Re-send last ACK occasionally if no new packets arrive?
            # In stop-and-wait, the sender keeps displaying until it gets ACK.
            # We just need to make sure we keep displaying the ACK.
            time.sleep(0.1)

        # 3. Reassemble and Verify
        if len(received_chunks) == num_chunks:
            full_data = b"".join(received_chunks[i] for i in range(1, num_chunks + 1))
            # Trim to actual file size
            full_data = full_data[:file_size]

            actual_hash = hashlib.sha256(full_data).digest()
            print(f"Final Hash: {actual_hash.hex()}")
            if actual_hash == expected_hash:
                print("SUCCESS: Hash match! Bit-for-bit identical.")
                output_path = "received_" + filename
                with open(output_path, "wb") as f:
                    f.write(full_data)
                print(f"File saved to {output_path}")
            else:
                print("FAILURE: Hash mismatch!")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Give a small delay so the sender can see the last ACK
        time.sleep(2)
        transceiver.running = False
        t_display.join()
        t_capture.join()

def main():
    parser = argparse.ArgumentParser(description="AirQR Optical File Transfer")
    parser.add_argument("--send", help="Path to the file to send")
    parser.add_argument("--receive", action="store_true", help="Receive a file")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    args = parser.parse_args()

    if args.send:
        run_sender(args.send, args.camera)
    elif args.receive:
        run_receiver(args.camera)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
