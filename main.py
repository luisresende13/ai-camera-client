import os
import requests
from flask import Flask, request, jsonify

SCHEDULER_PROJECT_ID = os.environ.get('SCHEDULER_PROJECT_ID')
SCHEDULER_LOCATION = os.environ.get('SCHEDULER_LOCATION')
MONGO_API_URL = os.environ.get('MONGO_API_URL')
CLOUD_SCHEDULER_API_URL = os.environ.get('CLOUD_SCHEDULER_API_URL')
AI_CAMERA_API_URL = os.environ.get('AI_CAMERA_API_URL')

app = Flask(__name__)

@app.route('/', methods=['GET'])
def root():
    return "AI Camera Client API"

# Endpoint to create a new configuration object in MongoDB and create a job in Cloud Scheduler
@app.route("/config", methods=["POST"])
def create_config_and_job():
    # Get body from the request
    body = request.json

    # Get attribute values from body
    user_id = body['user_id']
    camera_id = body['camera_id']
    object_id = body['object_id']
    job_schedule = body['schedule'] # example: "0 15 * * *"
    job_time_zone = body.get('time_zone', 'America/Sao_Paulo')
    
    try:
        # Make a request to MongoDB API to create a configuration object
        url = f"{MONGO_API_URL}/octacity/configs"
        res = requests.post(url, json=body)
        res.raise_for_status()  # Raise an exception for non-2xx responses

        # Get the created config object
        data = res.json()
        config = data['data']
        config_id = config['_id']
        
        # Custom attributes
        job_name = f"config-{config_id}"
        job_url = f'{AI_CAMERA_API_URL}/process_stream_config?config_id={config_id}'

        # If MongoDB operation succeeds, create a job in Cloud Scheduler
        job_data = {
            "project_id": SCHEDULER_PROJECT_ID,
            "location": SCHEDULER_LOCATION,
            "job_name": job_name,
            "schedule": job_schedule,  # Every day at 15:00 UTC
            "time_zone": job_time_zone,
            "url": job_url,
            "method": 'GET',
            "headers": {"Content-Type": "application/json"}
            # "request_body": {"key": "value"},
        }

        # Make a request to Cloud Scheduler API to create a job
        url = f"{CLOUD_SCHEDULER_API_URL}/job/create"
        res = requests.post(url, json=job_data)
        res.raise_for_status()  # Raise an exception for non-2xx responses

        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'detail': "Configuration object created and job created successfully"}
        print(msg)
        return msg, 201
    except requests.exceptions.RequestException as e:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'detail': f"Failed to create configuration object: {str(e)}"}
        print(msg)
        return msg, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
