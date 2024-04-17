# Update Package Lists:
sudo apt update

# Install Git (if not already installed):
sudo apt install git

# Run the following command to install the python3-venv package:
sudo apt install python3-venv

# Clone Your Flask App Repository:
# Navigate to the directory where you want to clone your Flask app repository and execute:
git clone https://github.com/luisresende13/ai-camera-api.git

# Install Required Dependencies:
# Navigate to your Flask app directory and install necessary dependencies. It's recommended to use a virtual environment:
cd ai-camera-api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# If your app uses opencv, run the following:
sudo -i
sudo apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
exit

# Make sure you are still at the repository directory
# cd ai-camera-api

# Create a Systemd Service Unit File:
# Create a systemd unit file (your_flask_app.service) to manage your Flask app as a system service:
sudo nano /etc/systemd/system/ai_camera_api.service

# Create a service file with the content of the "service.service" file present in the same directory as this file.
# Replace your_username, your_group, /path/to/your_flask_app_directory, and /path/to/your_flask_app_file.py with appropriate values for your setup.

# Reload Systemd and Start the Service:
# After creating the systemd unit file, reload the systemd manager configuration and start your Flask app service:
sudo systemctl daemon-reload
sudo systemctl start ai_camera_api

# Enable the Service to Start on Boot:
# To ensure your Flask app service starts automatically on boot, enable it:
sudo systemctl enable ai_camera_api

# Verify the Service Status:
# Check the status of your Flask app service to ensure it's running without errors:
sudo systemctl status ai_camera_api

# Listen to logs from the server
sudo journalctl -u ai_camera_api -f --since "1 hour ago"

# Watch log files
sudo tail -n 30 -f access.log
sudo tail -n 30 -f error.log

# Configure Firewall Rules:
# If you haven't already done so, configure firewall rules to allow traffic on the port your Flask app is running on (usually port 5000).
