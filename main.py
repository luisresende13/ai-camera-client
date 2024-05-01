import time; start_time = time.time()
import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

SCHEDULER_PROJECT_ID = os.environ.get('SCHEDULER_PROJECT_ID')
SCHEDULER_LOCATION = os.environ.get('SCHEDULER_LOCATION')
MONGO_API_URL = os.environ.get('MONGO_API_URL')
CLOUD_SCHEDULER_API_URL = os.environ.get('CLOUD_SCHEDULER_API_URL')
AI_CAMERA_MANAGER_API_URL = os.environ.get('AI_CAMERA_MANAGER_API_URL')
PROCESS_STREAM_API_URL = os.environ.get('PROCESS_STREAM_API_URL')
ZONEMINDER_API_URL = os.environ.get('ZONEMINDER_API_URL')
ZONEMINDER_USER_NAME = os.environ.get('ZONEMINDER_USER_NAME')
ZONEMINDER_PASSWORD = os.environ.get('ZONEMINDER_PASSWORD')

# PROCESS_STREAM_API_URL = 'http://localhost:5001'
# ZONEMINDER_API_URL = f'http://localhost/zm/api'

# Define the URL and data
zm_auth = {"user": ZONEMINDER_USER_NAME, "pass": ZONEMINDER_PASSWORD}

def zm_login():
    # Send the POST request
    res = requests.post(f"{ZONEMINDER_API_URL}/host/login.json", data=zm_auth)
    
    # Check the response
    if res.status_code != 200:
        print(f"Login to ZoneMinder failed | status-code: {res.status_code} | message: {res.reason} | data: {res.text}")
    else:
        # print("Login to ZoneMinder successful")
        zm_token = res.json()['access_token']
        return zm_token


app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def root():
    return "AI Camera Client API"

# Endpoint to create a new configuration object in MongoDB and create a job in Cloud Scheduler
@app.route("/cameras", methods=["POST"])
def create_camera_and_monitor():
    # Get body from the request
    body = request.json

    # Get attribute values from body
    user_id = body['user_id']
    name = body['name']
    protocol = body['protocol']
    address = body['address']
    port = int(body['port'])
    subpath = body['subpath']

    zm_token = zm_login()
    if zm_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to zoneminder"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    monitor_url = f'{protocol}://{address}:{port}/{subpath}'
    
    # Test the camera connection
    url = f'{PROCESS_STREAM_API_URL}/connect'
    connect = {
        'url': monitor_url,
        'thumbnail': True
    }
    res = requests.post(url, json=connect)
    data = res.json()

    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to test the camera url connection using the Process Stream API"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    connected = data['connected']

    if not connected:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to connect to the camera url connection using the Process Stream API"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    # Get camera connection status
    width = data['width']
    height = data['height']
    fps = data['fps']
    image = data['image']    
    
    # Make a request to MongoDB API to create a configuration object
    url = f'{MONGO_API_URL}/octacity/cameras'

    camera = {
        'user_id': user_id,
        'name': name,
        'protocol': protocol,
        'address': 'address',
        'port': port,
        'subpath': subpath,
        'connected': connected,
        'fps': fps,
        'width': width,
        'height': height,
    }
    
    res = requests.post(url, json=camera)

    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to create camera object in mongo collection'}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    # Get the created camera object
    data = res.json()
    camera = data['data']
    camera_id = camera['_id']

    # Define monitor data
    monitor_name = camera_id
    monitor_width = width
    monitor_height = height
    monitor_function = 'Monitor'
    monitor_colours = 4
    
    if protocol == 'rtsp':
        monitor_type = 'Ffmpeg'
        monitor_method = 'rtpRtsp'
        monitor_protocol = None
        monitor_host = None
        monitor_port = ''
        monitor_path = monitor_url
    
    else:
        monitor_type = 'Remote'
        monitor_method = 'simple'
        monitor_protocol = protocol
        monitor_host = address
        monitor_port = port
        monitor_path = f'/{subpath}'
    
    url = f'{ZONEMINDER_API_URL}/monitors.json?token={zm_token}'
    
    data = {
        'Name': monitor_name,
        'Function': monitor_function,
        'Method': monitor_method,
        'Type': monitor_type,
        'Protocol': monitor_protocol,
        'Host': monitor_host,
        'Port': monitor_port,
        'Path': monitor_path,
        'Width': monitor_width,
        'Height': monitor_height,
        'Colours': monitor_colours,
        # 'User': None,
        # 'Pass': None,
    }
    data = {f'Monitor[{key}]': value for key, value in data.items()}
    
    res = requests.post(url, data=data)

    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to create monitor in zoneminder"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    msg = {'camera_id': camera_id, 'ok': True, 'data': camera, 'detail': "Configuration object created and job created successfully"}
    print(f'POST REQUEST TO CREATE CAMERA FINISHED | {msg}')
    return jsonify(msg), 200


# Endpoint to create a new configuration object in MongoDB and create a job in Cloud Scheduler
@app.route("/config", methods=["POST"])
def create_config_and_job():
    # Get body from the request
    body = request.json

    # Get attribute values from body
    user_id = body['user_id']
    camera_id = body['camera_id']
    class_id = body['class_id']
    job_schedule = body['schedule'] # example: "0 15 * * *"
    job_time_zone = body.get('time_zone', 'America/Sao_Paulo')
    
    # Make a request to MongoDB API to create a configuration object
    url = f"{MONGO_API_URL}/octacity/configs"
    res = requests.post(url, json=body)
    
    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to create configuration object in mongo collection"}
        print(f'ERROR IN POST REQUEST TO CREATE CONFIG | {msg}')
        return jsonify(msg), 500

    # Get the created config object
    data = res.json()
    config = data['data']
    config_id = config['_id']
    
    # Custom attributes
    job_name = f"config-{config_id}"
    job_url = f'{AI_CAMERA_MANAGER_API_URL}/process_config/{config_id}'

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
        return jsonify(msg), 500

    msg = {'config_id': config_id, 'ok': True, 'data': config, 'detail': "Configuration object created and job created successfully"}
    print(f'POST REQUEST TO CREATE CONFIG FINISHED | {msg}')
    return jsonify(msg), 200

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
        return jsonify(msg), 500

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
        return jsonify(msg), 500

    msg = {'config_id': config_id, 'ok': True, 'detail': "Configuration object update and job updated successfully"}
    print(f'PUT REQUEST TO UPDATE CONFIG FINISHED | {msg}')
    return jsonify(msg), 200

@app.route("/config/<string:config_id>", methods=["DELETE"])
def delete_config_and_job(config_id):
    # Delete the configuration object from MongoDB
    mongo_url = f"{MONGO_API_URL}/octacity/configs/{config_id}"
    res = requests.delete(mongo_url)
    
    if not res.ok:
        msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to delete configuration object from MongoDB"}
        print(f'ERROR IN DELETE REQUEST TO DELETE CONFIG | {msg}')
        return jsonify(msg), 500

    # Delete the corresponding job from Cloud Scheduler
    # Delete the job from Cloud Scheduler
    job_name = f"config-{config_id}"
    scheduler_url = f"{CLOUD_SCHEDULER_API_URL}/job/delete"
    data = {"project_id": SCHEDULER_PROJECT_ID, "location": SCHEDULER_LOCATION, "job_name": job_name}
    res = requests.post(scheduler_url, json=data)
    
    if not res.ok:
        msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to delete job from Cloud Scheduler"}
        print(f'ERROR IN DELETE REQUEST TO DELETE CONFIG JOB | {msg}')
        return jsonify(msg), 500

    msg = {'config_id': config_id, 'ok': True, 'detail': "Configuration object deleted and job deleted successfully"}
    print(f'DELETE REQUEST TO DELETE CONFIG FINISHED | {msg}')
    return jsonify(msg), 200

app_load_time = round(time.time() - start_time, 3)
print(f'\nFLASK APPLICATION STARTED... | APP-LOAD-TIME: {app_load_time} s')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
