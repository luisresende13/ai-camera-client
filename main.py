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
    
    # Make a request to MongoDB API to create a configuration object
    url = f"{MONGO_API_URL}/octacity/configs"
    res = requests.post(url, json=body)
    
    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to create configuration object in mongo collection"}
        print(f'ERROR IN POST REQUEST TO CREATE CONFIG | {msg}')
        return msg, 500

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
    
    if not res.ok:
        msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to create config job in cloud scheduler"}
        print(f'ERROR IN POST REQUEST TO CREATE CONFIG JOB | {msg}')
        return msg, 500

    msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'detail': "Configuration object created and job created successfully"}
    print(f'POST REQUEST TO CREATE CONFIG FINISHED | {msg}')
    return msg, 200

@app.route("/config/<string:config_id>", methods=["PUT"])
def update_config_and_job(config_id):
    # Get body from the request
    body = request.json

    # Update the configuration object in MongoDB
    url = f"{MONGO_API_URL}/octacity/configs/{config_id}"
    res = requests.put(url, json=body)
    
    if not res.ok:
        msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to update config job in cloud scheduler"}
        print(f'ERROR IN PUT REQUEST TO UPDATE CONFIG | {msg}')
        return msg, 500

    # Update the corresponding job in Cloud Scheduler
    data = {
        "project_id": SCHEDULER_PROJECT_ID,
        "location": SCHEDULER_LOCATION,
        "job_name": f"config-{config_id}",
        "updates": body  # Pass any updates for the job
    }
    url = f"{CLOUD_SCHEDULER_API_URL}/job/update"
    res = requests.post(url, json=data)
    
    if not res.ok:
        msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to update config job in cloud scheduler"}
        print(f'ERROR IN POST REQUEST TO UPDATE CONFIG JOB | {msg}')
        return msg, 500

    msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'detail': "Configuration object update and job updated successfully"}
    print(f'PUT REQUEST TO UPDATE CONFIG FINISHED | {msg}')
    return msg, 200

@app.route("/config/<string:config_id>", methods=["DELETE"])
def delete_config_and_job(config_id):
    # Delete the configuration object from MongoDB
    mongo_url = f"{MONGO_API_URL}/octacity/configs/{config_id}"
    res = requests.delete(mongo_url)
    
    if not res.ok:
        msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to delete configuration object from MongoDB"}
        print(f'ERROR IN DELETE REQUEST TO DELETE CONFIG | {msg}')
        return msg, 500

    # Delete the corresponding job from Cloud Scheduler
    # Delete the job from Cloud Scheduler
    job_name = f"config-{config_id}"
    scheduler_url = f"{CLOUD_SCHEDULER_API_URL}/job/delete"
    data = {"project_id": SCHEDULER_PROJECT_ID, "location": SCHEDULER_LOCATION, "job_name": job_name}
    res = requests.post(scheduler_url, json=data)
    
    if not res.ok:
        msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to delete job from Cloud Scheduler"}
        print(f'ERROR IN DELETE REQUEST TO DELETE CONFIG JOB | {msg}')
        return msg, 500

    msg = {'config_id': config_id, 'detail': "Configuration object deleted and job deleted successfully"}
    print(f'DELETE REQUEST TO DELETE CONFIG FINISHED | {msg}')
    return msg, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
