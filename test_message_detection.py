"""
Test script for message overlay detection.
Place test images in a folder and run this script to see detection results.
"""

import cv2
import numpy as np
import os
import sys


def has_message_overlay(frame):
    """
    Detect if message overlays are present in loot window.
    Messages appear as dark semi-transparent boxes in the bottom-left area.
    Returns True if message detected, False if clean view.
    """
    try:
        # Check bottom-left region where messages typically appear
        # Based on loot window crop: (207, 209, 397x262)
        # Bottom-left corner of that region
        message_region = frame[150:220, 0:150]

        # Convert to grayscale
        gray = cv2.cvtColor(message_region, cv2.COLOR_BGR2GRAY)

        # Messages have dark backgrounds (pixel values < 40)
        # Count dark pixels
        dark_pixels = np.sum(gray < 40)
        total_pixels = gray.size
        dark_ratio = dark_pixels / total_pixels

        # If > 20% of region is very dark, message is present
        return dark_ratio > 0.20, dark_ratio, message_region

    except Exception as e:
        # If detection fails, assume no message (safe default)
        return False, 0.0, None


def test_image(image_path):
    """Test message detection on a single image"""
    print(f"\n{'='*70}")
    print(f"Testing: {os.path.basename(image_path)}")
    print(f"{'='*70}")

    # Load image
    frame = cv2.imread(image_path)

    if frame is None:
        print(f"❌ ERROR: Could not load image!")
        return

    print(f"Image size: {frame.shape[1]}x{frame.shape[0]}")

    # Run detection
    has_message, dark_ratio, message_region = has_message_overlay(frame)

    # Print results
    print(f"\nDetection Results:")
    print(f"  Dark pixel ratio: {dark_ratio:.2%}")
    print(f"  Threshold: 20%")
    print(f"  Message detected: {'✅ YES' if has_message else '❌ NO'}")

    if has_message:
        print(f"\n  → Bot would SKIP this window (wait for message to clear)")
    else:
        print(f"\n  → Bot would PROCESS this window")

    # Create visualization
    vis_frame = frame.copy()

    # Draw rectangle around detection region
    cv2.rectangle(vis_frame, (0, 150), (150, 220), (0, 255, 0) if not has_message else (0, 0, 255), 2)

    # Add text overlay
    status_text = "MESSAGE DETECTED" if has_message else "CLEAN WINDOW"
    color = (0, 0, 255) if has_message else (0, 255, 0)
    cv2.putText(vis_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    cv2.putText(vis_frame, f"Dark: {dark_ratio:.1%}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Show detection region separately
    if message_region is not None:
        # Enlarge detection region for better visibility
        detection_display = cv2.resize(message_region, (300, 140))
        cv2.putText(detection_display, "Detection Region", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Display results
    window_name = f"Test: {os.path.basename(image_path)}"
    cv2.imshow(window_name, vis_frame)

    if message_region is not None:
        cv2.imshow(f"Detection Region - {os.path.basename(image_path)}", detection_display)

    print(f"\nPress any key to continue to next image...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def find_all_session_screenshots():
    """Find first 10 screenshots from EACH session folder"""
    base_path = os.path.join(os.path.dirname(__file__), "Data", "All Loot Screenshots")

    if not os.path.exists(base_path):
        return []

    # Find all session folders
    session_folders = [f for f in os.listdir(base_path) if f.startswith('Session_')]

    if not session_folders:
        return []

    # Sort sessions (newest first)
    session_folders.sort(reverse=True)

    # Collect first 10 images from EACH session
    all_images = []
    for session in session_folders:
        # Get screenshots from Regular Loot folder
        regular_loot_path = os.path.join(base_path, session, "Regular Loot")

        if not os.path.exists(regular_loot_path):
            continue

        # Find all images in this session
        session_images = []
        for file in os.listdir(regular_loot_path):
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                full_path = os.path.join(regular_loot_path, file)
                session_images.append(full_path)

        # Sort and take first 10 from this session
        session_images.sort()
        for img_path in session_images[:10]:
            all_images.append((img_path, session))

    return all_images


def main():
    """Main test function"""
    print("="*70)
    print("MESSAGE OVERLAY DETECTION TEST")
    print("="*70)

    # Default to specific session folder
    default_folder = r"C:\Users\andre\Desktop\TLOPO-Looter\Data\All Loot Screenshots\Session_29-10-2025_21.11.45\Regular Loot"

    # Check if folder path provided
    if len(sys.argv) > 1:
        test_folder = sys.argv[1]
    else:
        test_folder = default_folder

    print(f"\nTest folder: {test_folder}")

    if not os.path.exists(test_folder):
        print(f"\n❌ ERROR: Folder not found!")
        return

    # Find ALL image files (no limit)
    image_data = []
    for file in os.listdir(test_folder):
        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
            full_path = os.path.join(test_folder, file)
            image_data.append((full_path, os.path.basename(test_folder)))

    # Sort by filename (1.jpg, 2.jpg, ..., 21.jpg)
    image_data.sort(key=lambda x: int(os.path.splitext(os.path.basename(x[0]))[0]) if os.path.splitext(os.path.basename(x[0]))[0].isdigit() else 0)

    print(f"Found {len(image_data)} image(s) to test\n")

    if not image_data:
        print(f"\n❌ ERROR: No image files found")
        return

    # Test each image
    for i, (image_path, session_name) in enumerate(image_data, 1):
        print(f"\n[{i}/{len(image_data)}] Session: {session_name}")
        test_image(image_path)

    print(f"\n{'='*70}")
    print(f"Testing complete! Tested {len(image_data)} image(s)")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
