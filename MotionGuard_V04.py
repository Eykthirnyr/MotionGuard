import tkinter as tk
from tkinter import Canvas, messagebox, ttk, filedialog
import webbrowser
import subprocess
import sys
import os

# Function to check and install dependencies if missing
def check_install(package, import_name=None):
    try:
        if import_name is None:
            import_name = package
        __import__(import_name)
    except ImportError:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Ensure required dependencies are installed
dependencies = {
    "opencv-python": "cv2",
    "Pillow": "PIL",
    "pygame": "pygame",
    "numpy": "numpy",
    "smtplib": "smtplib",
    "email": "email.mime.text",
}

for package, import_name in dependencies.items():
    check_install(package, import_name)

# After ensuring dependencies are installed, import them
from PIL import Image, ImageGrab, ImageTk
import cv2
import numpy as np
import pygame
import configparser
import time
import threading
import smtplib
from email.mime.text import MIMEText

# Initialize pygame for sound playing
pygame.mixer.init()

# Load configuration
config = configparser.ConfigParser()
config_file = "config.ini"

if os.path.exists(config_file):
    config.read(config_file)
    # Ensure 'volume' is in the SoundAlert section, add it if missing
    if 'volume' not in config['SoundAlert']:
        config['SoundAlert']['volume'] = '1.0'
else:
    config['SoundAlert'] = {'enabled': 'False', 'sound_file': '', 'volume': '1.0'}
    config['SMTP'] = {
        'enabled': 'False',
        'server': '',
        'port': '',
        'email': '',
        'password': '',
        'recipient': '',
        'subject': 'Motion Detected',
        'body': 'Motion detected by the application.'
    }

# Save the updated configuration (in case 'volume' was missing)
with open(config_file, 'w') as configfile:
    config.write(configfile)

class MotionDetectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Motion Detector App")
        self.root.geometry("570x800")
        self.root.resizable(False, False)  # Fixed window size

        self.selected_area = None
        self.sensitivity = 50  # Default sensitivity
        self.cooldown_time = 10  # Default cooldown time in seconds for the red dot
        self.is_running = False  # Track if detection is running
        self.motion_detected_time = None  # Time when motion was detected
        self.sound_playing = False  # Track if sound is currently playing

        # Load settings from config
        self.sound_alert_enabled = config.getboolean('SoundAlert', 'enabled')
        self.sound_file = config['SoundAlert']['sound_file']
        self.sound_volume = float(config['SoundAlert']['volume'])
        self.smtp_enabled = config.getboolean('SMTP', 'enabled')
        self.smtp_settings = {
            'server': config['SMTP']['server'],
            'port': config['SMTP']['port'],
            'email': config['SMTP']['email'],
            'password': config['SMTP']['password'],
            'recipient': config['SMTP']['recipient'],
            'subject': config['SMTP']['subject'],
            'body': config['SMTP']['body']
        }

        # Create notebook with tabs
        self.notebook = ttk.Notebook(root)
        self.main_frame = ttk.Frame(self.notebook)
        self.settings_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.main_frame, text="Main")
        self.notebook.add(self.settings_frame, text="Settings")
        self.notebook.pack(expand=1, fill="both")

        # Title
        title_label = tk.Label(self.main_frame, text="Motion Detection App", font=("Arial", 18, "bold"))
        title_label.pack(pady=10)  # Add title at the top with some padding

        # Subtitle
        subtitle_label = tk.Label(self.main_frame, text="Detect movement in a selected area", font=("Arial", 12))
        subtitle_label.pack(pady=5)  # Add subtitle below the title

        # Main tab components
        self.select_button = tk.Button(self.main_frame, text="Select Screen Area", command=self.take_screenshot)
        self.select_button.pack(pady=10)

        self.sensitivity_label = tk.Label(self.main_frame, text="Sensitivity (%)")
        self.sensitivity_label.pack()

        self.sensitivity_slider = tk.Scale(self.main_frame, from_=100, to=0, orient=tk.HORIZONTAL, command=self.update_sensitivity)
        self.sensitivity_slider.set(self.sensitivity)
        self.sensitivity_slider.pack(pady=10)

        # Cooldown time slider for red dot
        self.cooldown_label = tk.Label(self.main_frame, text="Cooldown Time for Red Dot (seconds)")
        self.cooldown_label.pack()

        self.cooldown_slider = tk.Scale(self.main_frame, from_=1, to=60, orient=tk.HORIZONTAL, command=self.update_cooldown)
        self.cooldown_slider.set(self.cooldown_time)
        self.cooldown_slider.pack(pady=10)

        self.start_button = tk.Button(self.main_frame, text="Start Detection", command=self.start_detection)
        self.start_button.pack(pady=10)

        self.stop_button = tk.Button(self.main_frame, text="Stop Detection", command=self.stop_detection, state=tk.DISABLED)
        self.stop_button.pack(pady=10)

        # Indicator for motion detection (red = motion, green = no motion)
        self.motion_indicator = tk.Canvas(self.main_frame, width=20, height=20)
        self.motion_indicator.pack(pady=10)
        self.set_motion_indicator(False)  # Start with green (no motion)

        # Credit link
        credit = tk.Label(self.main_frame, text="Made by Clément GHANEME", fg="blue", cursor="hand2")
        credit.pack(side=tk.BOTTOM, pady=10)  # Moves to the bottom of the window
        credit.bind("<Button-1>", lambda e: webbrowser.open_new("https://www.clement.business"))

        # Settings tab components
        self.build_settings_tab()

    def set_motion_indicator(self, motion_detected):
        """Sets the motion indicator color based on whether motion is detected or not."""
        self.motion_indicator.delete("all")
        color = "red" if motion_detected else "green"
        self.motion_indicator.create_oval(2, 2, 18, 18, fill=color)

    def take_screenshot(self):
        # Take a full-screen screenshot
        screenshot = ImageGrab.grab()

        # Convert the screenshot to a Tkinter-compatible image
        self.screenshot_image = ImageTk.PhotoImage(screenshot)

        # Create a new window to display the screenshot for area selection
        self.selection_window = tk.Toplevel(self.root)
        self.selection_window.attributes('-fullscreen', True)  # Make the window full-screen

        self.canvas = Canvas(self.selection_window, cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Display the screenshot on the canvas
        self.canvas.create_image(0, 0, image=self.screenshot_image, anchor=tk.NW)

        # Variables to track the rectangle
        self.start_x = None
        self.start_y = None
        self.rect = None

        # Bind mouse events to draw the rectangle
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

    def on_button_press(self, event):
        # Record the starting point
        self.start_x = event.x
        self.start_y = event.y

        # Create the rectangle
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)

    def on_mouse_drag(self, event):
        # Update the rectangle as the mouse is dragged
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        # Finalize the rectangle when the mouse button is released
        end_x, end_y = event.x, event.y

        # Store the selected area (top-left and bottom-right coordinates)
        self.selected_area = (min(self.start_x, end_x), min(self.start_y, end_y), max(self.start_x, end_x), max(self.start_y, end_y))

        # Close the selection window
        self.selection_window.destroy()

    def update_sensitivity(self, val):
        """Update sensitivity dynamically."""
        self.sensitivity = int(val)

    def update_cooldown(self, val):
        """Update the cooldown time for the red dot."""
        self.cooldown_time = int(val)

    def start_detection(self):
        if self.selected_area is None:
            messagebox.showerror("Error", "Please select an area first.")
            return

        # Update UI components
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        # Start detection in a separate thread
        self.detection_thread = threading.Thread(target=self.detect_motion)
        self.detection_thread.start()

    def stop_detection(self):
        """Stops the motion detection."""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.set_motion_indicator(False)

    def detect_motion(self):
        try:
            # Capture the first frame within the selected area
            prev_frame = np.array(ImageGrab.grab(bbox=self.selected_area).convert('L'))

            while self.is_running:
                # Capture the current frame within the selected area
                curr_frame = np.array(ImageGrab.grab(bbox=self.selected_area).convert('L'))

                # Check if the frame sizes match
                if prev_frame.shape != curr_frame.shape:
                    print("Error: Frame sizes do not match!")
                    continue

                # Calculate the difference between frames
                diff = cv2.absdiff(prev_frame, curr_frame)
                _, diff_thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

                # Calculate the motion score based on the differences
                motion_score = np.sum(diff_thresh) / diff_thresh.size

                # If motion score exceeds the inversed sensitivity threshold, trigger the motion event
                if motion_score > (100 - self.sensitivity) * 255 / 100:
                    self.motion_detected_time = time.time()  # Log the time of motion detection
                    self.set_motion_indicator(True)  # Red = Motion Detected

                    # Play sound if enabled
                    if self.sound_alert_enabled and self.sound_file:
                        self.play_sound(self.sound_file)

                    # Send email if enabled
                    if self.smtp_enabled:
                        self.send_email()
                else:
                    # Keep red for the cooldown period after last detection
                    if self.motion_detected_time and time.time() - self.motion_detected_time < self.cooldown_time:
                        self.set_motion_indicator(True)
                    else:
                        self.set_motion_indicator(False)

                # Update previous frame for the next comparison
                prev_frame = curr_frame
                time.sleep(0.1)
        except Exception as e:
            print(f"Error during motion detection: {e}")

    def send_email(self):
        """Send an email using the configured SMTP settings with enhanced logging."""
        try:
            msg = MIMEText(self.smtp_settings['body'])
            msg['Subject'] = self.smtp_settings['subject']
            msg['From'] = self.smtp_settings['email']
            msg['To'] = self.smtp_settings['recipient']

            # Check if port 465 for SSL is being used
            if self.smtp_settings['port'] == '465':
                print(f"Connecting to SMTP server {self.smtp_settings['server']} on port {self.smtp_settings['port']} using SSL...")
                server = smtplib.SMTP_SSL(self.smtp_settings['server'], int(self.smtp_settings['port']))
            else:
                print(f"Connecting to SMTP server {self.smtp_settings['server']} on port {self.smtp_settings['port']}...")
                server = smtplib.SMTP(self.smtp_settings['server'], int(self.smtp_settings['port']))
                server.ehlo()
                if self.smtp_settings['port'] == '587':  # Port 587 uses TLS
                    print("Starting TLS...")
                    server.starttls()
                    server.ehlo()  # Re-identify ourselves after starting TLS

            print(f"Logging in as {self.smtp_settings['email']}...")
            server.login(self.smtp_settings['email'], self.smtp_settings['password'])
            
            print("Sending email...")
            server.sendmail(self.smtp_settings['email'], [self.smtp_settings['recipient']], msg.as_string())
            print("Email sent successfully.")
            server.quit()

        except smtplib.SMTPAuthenticationError:
            print("Authentication failed: Incorrect username or password.")
        except smtplib.SMTPConnectError:
            print("Connection error: Unable to establish a connection with the server.")
        except smtplib.SMTPServerDisconnected:
            print("The server unexpectedly disconnected.")
        except Exception as e:
            print(f"Error sending email: {e}")

    def build_settings_tab(self):
        """Builds the settings tab with Sound Alert and SMTP settings."""
        # Sound Alert settings
        sound_frame = tk.LabelFrame(self.settings_frame, text="Sound Alert", padx=10, pady=10)
        sound_frame.pack(fill="both", expand="yes", padx=10, pady=10)

        self.sound_enable_var = tk.BooleanVar(value=self.sound_alert_enabled)
        sound_enable_check = tk.Checkbutton(sound_frame, text="Enable", variable=self.sound_enable_var)
        sound_enable_check.pack(anchor="w")

        sound_button = tk.Button(sound_frame, text="Choose Sound File", command=self.choose_sound_file)
        sound_button.pack(pady=5)

        # Test Sound Button
        test_sound_button = tk.Button(sound_frame, text="Test Sound", command=lambda: self.play_sound(self.sound_file))
        test_sound_button.pack(pady=5)

        # Volume Slider
        volume_label = tk.Label(sound_frame, text="Volume")
        volume_label.pack(pady=5)
        self.volume_slider = tk.Scale(sound_frame, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL, command=self.update_volume)
        self.volume_slider.set(self.sound_volume)
        self.volume_slider.pack(pady=5)

        # SMTP settings
        smtp_frame = tk.LabelFrame(self.settings_frame, text="SMTP", padx=10, pady=10)
        smtp_frame.pack(fill="both", expand="yes", padx=10, pady=10)

        self.smtp_enable_var = tk.BooleanVar(value=self.smtp_enabled)
        smtp_enable_check = tk.Checkbutton(smtp_frame, text="Enable", variable=self.smtp_enable_var)
        smtp_enable_check.pack(anchor="w")

        tk.Label(smtp_frame, text="SMTP Server").pack(anchor="w")
        self.smtp_server_entry = tk.Entry(smtp_frame)
        self.smtp_server_entry.insert(0, self.smtp_settings['server'])
        self.smtp_server_entry.pack(fill="x", pady=5)

        tk.Label(smtp_frame, text="Port").pack(anchor="w")
        self.smtp_port_entry = tk.Entry(smtp_frame)
        self.smtp_port_entry.insert(0, self.smtp_settings['port'])
        self.smtp_port_entry.pack(fill="x", pady=5)

        tk.Label(smtp_frame, text="Email").pack(anchor="w")
        self.smtp_email_entry = tk.Entry(smtp_frame)
        self.smtp_email_entry.insert(0, self.smtp_settings['email'])
        self.smtp_email_entry.pack(fill="x", pady=5)

        tk.Label(smtp_frame, text="Password").pack(anchor="w")
        self.smtp_password_entry = tk.Entry(smtp_frame, show="*")
        self.smtp_password_entry.insert(0, self.smtp_settings['password'])
        self.smtp_password_entry.pack(fill="x", pady=5)

        tk.Label(smtp_frame, text="Recipient Email").pack(anchor="w")
        self.smtp_recipient_entry = tk.Entry(smtp_frame)
        self.smtp_recipient_entry.insert(0, self.smtp_settings['recipient'])
        self.smtp_recipient_entry.pack(fill="x", pady=5)

        tk.Label(smtp_frame, text="Email Subject").pack(anchor="w")
        self.smtp_subject_entry = tk.Entry(smtp_frame)
        self.smtp_subject_entry.insert(0, self.smtp_settings['subject'])
        self.smtp_subject_entry.pack(fill="x", pady=5)

        tk.Label(smtp_frame, text="Email Body").pack(anchor="w")
        self.smtp_body_entry = tk.Entry(smtp_frame)
        self.smtp_body_entry.insert(0, self.smtp_settings['body'])
        self.smtp_body_entry.pack(fill="x", pady=5)

        # Apply Config button
        apply_button = tk.Button(self.settings_frame, text="Apply Config", command=self.apply_config)
        apply_button.pack(pady=10)

    def choose_sound_file(self):
        """Opens a file dialog to choose a sound file."""
        self.sound_file = filedialog.askopenfilename(filetypes=[("Audio Files", "*.wav *.mp3")])

    def apply_config(self):
        """Applies the settings and saves them to the config file."""
        self.sound_alert_enabled = self.sound_enable_var.get()

        self.smtp_enabled = self.smtp_enable_var.get()
        self.smtp_settings = {
            'server': self.smtp_server_entry.get(),
            'port': self.smtp_port_entry.get(),
            'email': self.smtp_email_entry.get(),
            'password': self.smtp_password_entry.get(),
            'recipient': self.smtp_recipient_entry.get(),
            'subject': self.smtp_subject_entry.get(),
            'body': self.smtp_body_entry.get()
        }

        # Save to config file
        config['SoundAlert']['enabled'] = str(self.sound_alert_enabled)
        config['SoundAlert']['sound_file'] = self.sound_file
        config['SoundAlert']['volume'] = str(self.sound_volume)

        config['SMTP']['enabled'] = str(self.smtp_enabled)
        config['SMTP']['server'] = self.smtp_settings['server']
        config['SMTP']['port'] = self.smtp_settings['port']
        config['SMTP']['email'] = self.smtp_settings['email']
        config['SMTP']['password'] = self.smtp_settings['password']
        config['SMTP']['recipient'] = self.smtp_settings['recipient']
        config['SMTP']['subject'] = self.smtp_settings['subject']
        config['SMTP']['body'] = self.smtp_settings['body']

        with open(config_file, 'w') as configfile:
            config.write(configfile)

    def play_sound(self, sound_file):
        """Plays the selected sound file using pygame if it is not already playing."""
        if not self.sound_playing:
            try:
                pygame.mixer.music.load(sound_file)
                pygame.mixer.music.set_volume(self.sound_volume)
                pygame.mixer.music.play()

                self.sound_playing = True
                pygame.mixer.music.set_endevent(pygame.USEREVENT)
                threading.Thread(target=self.check_sound_end).start()

            except Exception as e:
                print(f"Error playing sound: {e}")

    def check_sound_end(self):
        """Waits for the sound to finish and resets the state."""
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        self.sound_playing = False

    def update_volume(self, val):
        """Updates the sound volume from the slider."""
        self.sound_volume = float(val)
        pygame.mixer.music.set_volume(self.sound_volume)

# Main application
if __name__ == "__main__":
    root = tk.Tk()
    app = MotionDetectorApp(root)
    root.mainloop()
