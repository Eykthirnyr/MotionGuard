import subprocess
import sys

# Function to check and install dependencies if missing
def check_install(package):
    try:
        __import__(package)
        print(f"{package} is already installed.")
    except ImportError:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# List of required dependencies
dependencies = [
    "tkinter",       # For the GUI
    "Pillow",        # For image manipulation
    "opencv-python", # For motion detection (OpenCV)
    "numpy",         # For array processing
    "pygame"         # For playing sound
]

# Loop through each dependency and install it if not already installed
for package in dependencies:
    check_install(package)

print("All dependencies are installed.")
