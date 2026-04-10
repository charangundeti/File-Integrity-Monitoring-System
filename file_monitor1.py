import time
import sqlite3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import hashlib
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import cv2

# Function to calculate the hash of a file using SHA-256
def calculate_hash(file_path):
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
    except FileNotFoundError:
        return None
    return sha256_hash.hexdigest()

# Initialize SQLite database and create the file_info table
def initialize_database():
    conn = sqlite3.connect('file_integrity.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS file_info (
        file_path TEXT PRIMARY KEY,
        file_hash TEXT
    )
    ''')
    conn.commit()
    conn.close()

# Insert or update file metadata in the SQLite database
def store_file_metadata(file_path, file_hash):
    conn = sqlite3.connect('file_integrity.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO file_info (file_path, file_hash)
    VALUES (?, ?)
    ''', (file_path, file_hash))
    conn.commit()
    conn.close()

# Fetch the current hash of a file from the database
def get_stored_hash(file_path):
    conn = sqlite3.connect('file_integrity.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT file_hash FROM file_info WHERE file_path = ?
    ''', (file_path,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Send an email alert with an attachment
def send_email_alert(subject, body, attachment_path=None):
    sender_email = "techytricks23@gmail.com"
    receiver_email = "charangundeti23@gmail.com"
    password = "rshr jiut fcpq egvm"

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    # Attach the file if it's provided
    if attachment_path:
        try:
            # Open the attachment file in binary mode
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition", f"attachment; filename={os.path.basename(attachment_path)}"
                )
                message.attach(part)

            print(f"Attachment added: {attachment_path}")
        except Exception as e:
            print(f"Failed to attach file: {e}")

    # Send the email
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())
        server.quit()
        print(f"Email alert sent: {subject}")
    except Exception as e:
        print(f"Failed to send email alert: {e}")

# Capture and save a photo using OpenCV
def capture_photo(event_type, file_path):
    if not os.path.exists("captured_photos"):
        os.makedirs("captured_photos")
    
    cap = cv2.VideoCapture(0)  # Initialize webcam (0 for default)
    ret, frame = cap.read()
    
    if ret:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        photo_filename = f"captured_photos/{event_type}_{timestamp}.jpg"
        cv2.imwrite(photo_filename, frame)
        print(f"Photo captured: {photo_filename}")
    else:
        print("Failed to capture photo.")
    
    cap.release()
    return photo_filename

# Handler for file system events
class ChangeHandler(FileSystemEventHandler):
    excluded_files = ['file_integrity.db', 'file_integrity.db-journal']

    def on_modified(self, event):
        if not event.is_directory and os.path.basename(event.src_path) not in self.excluded_files:
            new_hash = calculate_hash(event.src_path)
            if new_hash:
                stored_hash = get_stored_hash(event.src_path)
                if stored_hash != new_hash:
                    store_file_metadata(event.src_path, new_hash)
                    print(f'File {event.src_path} has been modified.')
                    photo_path = capture_photo("modified", event.src_path)  # Capture photo on modification
                    send_email_alert("File Modified", f"The file {event.src_path} has been modified.", photo_path)

    def on_created(self, event):
        if not event.is_directory and os.path.basename(event.src_path) not in self.excluded_files:
            new_hash = calculate_hash(event.src_path)
            if new_hash:
                store_file_metadata(event.src_path, new_hash)
                print(f'File {event.src_path} has been created.')
                photo_path = capture_photo("created", event.src_path)  # Capture photo on creation
                send_email_alert("File Created", f"The file {event.src_path} has been created.", photo_path)

    def on_deleted(self, event):
        if not event.is_directory and os.path.basename(event.src_path) not in self.excluded_files:
            print(f'File {event.src_path} has been deleted.')
            photo_path = capture_photo("deleted", event.src_path)  # Capture photo on deletion
            send_email_alert("File Deleted", f"The file {event.src_path} has been deleted.", photo_path)

# Main function to monitor the current directory
if __name__ == "__main__":
    initialize_database()  # Set up the database
    
    path_to_watch = "./"  # Directory to monitor
    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=path_to_watch, recursive=True)
    
    print(f"Monitoring directory: {os.path.abspath(path_to_watch)}")  # Confirm directory being monitored
    
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
