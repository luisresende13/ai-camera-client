# BEFORE RUNNING THIS SCRIPT, DO THE FOLLOWING:

    # Install Git (if not already installed):
    # sudo apt install git
    
    # Clone Your Flask App Repository:
    # Navigate to the directory where you want to clone your Flask app repository and execute:
    # git clone https://github.com/luisresende13/ai-camera-client.git
    
    # Navigate to your Flask app directory
    # cd ai-camera-client
    
    # GIVE THE INSTALLATION SCRIPT EXECUTABLE PERMISISON
    # chmod +x install-ubuntu.sh

    # Install script
    # ./install-ubuntu.sh
    
# Update Package Lists:
sudo apt update

# Run the following command to install the python3-venv package:
sudo apt install python3-venv

# Install Required Dependencies:
# Navigate to your Flask app directory and install necessary dependencies. It's recommended to use a virtual environment:
# cd ai-camera-client
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# If your app uses opencv, run the following:
# sudo -i
# sudo apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
# exit

# ---
# 2. FLASK APP SYSTEMCTL SERVICE CONFIGURATION

# Make sure you are still at the repository directory
# cd ai-camera-client

# Create a Systemd Service Unit File:
# Create a systemd unit file (your_flask_app.service) to manage your Flask app as a system service:
sudo cp ai_camera_client.service /etc/systemd/system/ai_camera_client.service
sudo nano /etc/systemd/system/ai_camera_client.service
# OBS: MUST FILL THE USER NAME IN THE SERVICE FILE. THE USER NAME IS USUALY THE PART OF THE GMAL BEFORE THE '@' AND REPLACING DOTS FOR HYPHENS.
# TO FIND YOUR USER NAME. RUN: ls ../

# Create a service file with the content of the "service.service" file present in the same directory as this file.
# Replace your_username, your_group, /path/to/your_flask_app_directory, and /path/to/your_flask_app_file.py with appropriate values for your setup.

# Reload Systemd and Start the Service:
# After creating the systemd unit file, reload the systemd manager configuration and start your Flask app service:
sudo systemctl daemon-reload
sudo systemctl start ai_camera_client

# Enable the Service to Start on Boot:
# To ensure your Flask app service starts automatically on boot, enable it:
sudo systemctl enable ai_camera_client

# Verify the Service Status:
# Check the status of your Flask app service to ensure it's running without errors:
sudo systemctl status ai_camera_client

# Listen to logs from the server
# sudo journalctl -u ai_camera_client -n 20