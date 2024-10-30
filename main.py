import time; start_time = time.time()
import os
import traceback
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, jsonify
from flask_cors import CORS


MONGO_API_URL = os.environ.get('MONGO_API_URL', 'http://localhost:5000')
CLOUD_SCHEDULER_API_URL = os.environ.get('CLOUD_SCHEDULER_API_URL', 'http://localhost:5001')
AI_CAMERA_MANAGER_API_URL = os.environ.get('AI_CAMERA_MANAGER_API_URL', 'http://localhost:5004')
CAMERA_VISION_AI_API_URL = os.environ.get('CAMERA_VISION_AI_API_URL', 'http://localhost:5005')

SCHEDULER_PROJECT_ID = os.environ['SCHEDULER_PROJECT_ID']
SCHEDULER_LOCATION = os.environ.get('SCHEDULER_LOCATION', 'us-central-1')

ZONEMINDER_IP = os.environ['ZONEMINDER_IP']
ZONEMINDER_USER_NAME = os.environ['ZONEMINDER_USER_NAME']
ZONEMINDER_PASSWORD = os.environ['ZONEMINDER_PASSWORD']

ZONEMINDER_API_URL = f'http://{ZONEMINDER_IP}/zm/api'
zm_auth = {"user": ZONEMINDER_USER_NAME, "pass": ZONEMINDER_PASSWORD}

mongo_auth = {'email': 'luisresende13@gmail.com', 'password': 'Gaia0333'}

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

def mongodb_login():
    # Send the POST request
    res = requests.post(f"{MONGO_API_URL}/signin", json=mongo_auth)
    
    # Check the response
    if res.status_code != 200:
        print(f"Login to MongoDB API failed | status-code: {res.status_code} | message: {res.reason} | data: {res.text}")
    else:
        token = res.json()['token']
        return token


app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def root():
    return "AI Camera Client API"

@app.route('/zm/login', methods=['GET'])
def zm_login_endpoint():
    zm_token = zm_login()
    if zm_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to zoneminder", 'token': None}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500
    
    msg = {'ok': True, 'detail': f"Login to zoneminder successful", 'token': zm_token}
    return jsonify(msg)

# Create user
@app.route("/user", methods=["POST"])
def create_user():
    # Get body from the request
    body = request.json

    # Login to MongoDB API
    mongo_token = mongodb_login()
    if mongo_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to MongoDB API"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    url = f'{MONGO_API_URL}/octacity/users'
    headers = {'Authorization': f'Bearer {mongo_token}'}
    user = {**body,}
    
    res = requests.post(url, headers=headers, json=user)

    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to create user object in mongo collection'}
        print(f'ERROR IN POST REQUEST TO CREATE USER | {msg}')
        return jsonify(msg), 500

    # Get the created camera object
    created = res.json()
    user = created['data']
    user_id = user['_id']

    # Get base classes
    url = f'{MONGO_API_URL}/octacity/classes-base'
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.get(url, headers=headers)

    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to get base classes from mongo collection'}
        print(f'ERROR IN POST REQUEST TO CREATE USER | {msg}')
        return jsonify(msg), 500

    classes_base = res.json()

    # # Get base settings
    # url = f'{MONGO_API_URL}/octacity/settings-base'
    # headers = {'Authorization': f'Bearer {mongo_token}'}
    # res = requests.get(url, headers=headers)

    # if not res.ok:
    #     msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to get base settings from mongo collection'}
    #     print(f'ERROR IN POST REQUEST TO CREATE USER | {msg}')
    #     return jsonify(msg), 500

    # settings_base = res.json()[0]

    # Create user classes
    url = f'{MONGO_API_URL}/octacity/classes'
    headers = {'Authorization': f'Bearer {mongo_token}'}

    data = []
    for obj in classes_base.copy():
        del obj['_id']
        data.append({'user_id': user_id, **obj})

    res = requests.post(url, headers=headers, json=data)
    
    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to post user classes to mongo collection'}
        print(f'ERROR IN POST REQUEST TO CREATE USER | {msg}')
        return jsonify(msg), 500

    # # Create user settings
    # url = f'{MONGO_API_URL}/octacity/settings'
    # headers = {'Authorization': f'Bearer {mongo_token}'}
    
    # data = {'user_id': user_id, **settings_base}
    # res = requests.post(url, headers=headers, json=data)
    
    # if not res.ok:
    #     msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to post user settings to mongo collection'}
    #     print(f'ERROR IN POST REQUEST TO CREATE USER | {msg}')
    #     return jsonify(msg), 500
    
    msg = {'user_id': user_id, 'ok': True, 'data': user, 'detail': "User object created successfully"}
    print(f'POST REQUEST TO CREATE USER FINISHED | {msg}')
    return jsonify(msg), 201

# Endpoint to create a new camera object in MongoDB
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
    attach_monitor = body.get('attach_monitor', 'false') == 'true'

    # Login to MongoDB API
    mongo_token = mongodb_login()
    if mongo_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to MongoDB API"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500
    
    # Login to ZoneMinder
    if attach_monitor:
        zm_token = zm_login()

        if zm_token is None:
            msg = {'ok': False, 'detail': f"Failed to login to zoneminder"}
            print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
            return jsonify(msg), 500

    camera_url = f'{protocol}://{address}:{port}/{subpath}'
    
    # Test the camera connection
    url = f'{CAMERA_VISION_AI_API_URL}/connect'
    connect = {
        'url': camera_url,
        'thumbnail': True
    }
    res = requests.post(url, json=connect)
    connection = res.json()

    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to test the camera url connection using the Process Stream API"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    connected = connection['connected']

    if not connected:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to connect to the camera url connection using the Process Stream API"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    # Get camera connection status
    message = connection['message']
    width = connection['width']
    height = connection['height']
    fps = connection['fps']
    image = connection['image']    

    # Make a request to MongoDB API to create a camera object
    url = f'{MONGO_API_URL}/octacity/cameras'
    camera = {
        'user_id': user_id,
        'name': name,
        'protocol': protocol,
        'address': address,
        'port': port,
        'subpath': subpath,
        'connected': connected,
        'message': message,
        'fps': fps,
        'width': width,
        'height': height,
        'url': camera_url,
        'monitor_id': None,
        'zm_url': None,
    }
    headers = {'Authorization': f'Bearer {mongo_token}'}
    
    res = requests.post(url, json=camera, headers=headers)

    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to create camera object in mongo collection'}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    # Get the created camera object
    created = res.json()
    camera = created['data']
    camera_id = camera['_id']

    # Create and attach monitor from zoneminder
    if attach_monitor:
        
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
            monitor_path = camera_url
        
        else:
            monitor_type = 'Remote'
            monitor_method = 'simple'
            monitor_protocol = protocol
            monitor_host = address
            monitor_port = port
            monitor_path = f'/{subpath}'
        
        monitor = {
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
        
        url = f'{ZONEMINDER_API_URL}/monitors.json?token={zm_token}'
        monitor = {f'Monitor[{key}]': value for key, value in monitor.items()}
                
        res = requests.post(url, data=monitor)
    
        if not res.ok:
            msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to create monitor in zoneminder"}
            print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
            return jsonify(msg), 500
    
        # Get created monitor from zoneminder
        url = f'{ZONEMINDER_API_URL}/monitors/index/Name:{monitor_name}.json?token={zm_token}'
        res = requests.get(url)
        
        if not res.ok:
            msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to get monitor from zoneminder"}
            print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
            return jsonify(msg), 500
    
        monitors = res.json()
        monitor = monitors['monitors'][0]['Monitor']
        monitor_id = monitor['Id']
        zm_url = f'http://{ZONEMINDER_IP}/zm/cgi-bin/nph-zms?monitor={monitor_id}&width={width}px&height={height}px&maxfps={fps}&buffer=1000&scale=100&mode=jpeg'
    
        # Update camera object with monitor id
        url = f'{MONGO_API_URL}/octacity/cameras/{camera_id}'
        update = {
            'monitor_id': monitor_id,
            'zm_url': zm_url,
        }
        headers = {'Authorization': f'Bearer {mongo_token}'}
        
        res = requests.put(url, json=update, headers=headers)
    
        if not res.ok:
            msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to update camera object with monitor id in mongo collection'}
            print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
            return jsonify(msg), 500

        # Get the created camera object
        updated = res.json()
        camera_update = updated['data']
        camera = {**camera, **camera_update}
    
    msg = {'camera_id': camera_id, 'ok': True, 'data': camera, 'detail': "Camera object monitor created successfully"}
    print(f'POST REQUEST TO CREATE CAMERA FINISHED | {msg}')
    return jsonify(msg), 201


# Endpoint to create a new configuration object in MongoDB and create a job in Cloud Scheduler
@app.route("/cameras/<camera_id>", methods=["PUT"])
def update_camera_and_monitor(camera_id):
    # Get body from the request
    body = request.json
    update_monitor = body.get('update_monitor', 'false') == 'true'

    if 'update_monitor' in body:
        del body['update_monitor']
        
    # Return if not allowed field is found
    for key in body.keys():
        if key not in ['name', 'protocol', 'address', 'port', 'subpath']:
            msg = {'ok': False, 'detail': f'Field not allowed: {key} = {body[key]}'}
            print(f'ERROR IN PUT REQUEST TO UPDATE CAMERA | {msg}')
            return jsonify(msg), 400

    if body.get('port') is not None:
        body['port'] = int(body['port'])

    update_connection = not list(body.keys()) == ['name']

    # Login to MongoDB API
    mongo_token = mongodb_login()

    if mongo_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to MongoDB API"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500
    
    if update_connection:

        # Make a request to MongoDB API to get a camera object
        url = f'{MONGO_API_URL}/octacity/cameras/{camera_id}'
        headers = {'Authorization': f'Bearer {mongo_token}'}
        res = requests.get(url, headers=headers)
    
        if not res.ok:
            msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to get camera object from mongo collection'}
            print(f'ERROR IN PUT REQUEST TO UPDATE CAMERA | {msg}')
            return jsonify(msg), 500

        camera = res.json()

        if update_monitor and camera['monitor_id']:
            zm_token = zm_login()
            if zm_token is None:
                msg = {'ok': False, 'detail': f"Failed to login to zoneminder"}
                print(f'ERROR IN PUT REQUEST TO UPDATE CAMERA | {msg}')
                return jsonify(msg), 500

            monitor_name = camera_id
            url = f'{ZONEMINDER_API_URL}/monitors/index/Name:{monitor_name}.json?token={zm_token}'
            res = requests.get(url)
            
            if not res.ok:
                msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to get monitor from zoneminder"}
                print(f'ERROR IN PUT REQUEST TO UPDATE CAMERA | {msg}')
                return jsonify(msg), 500
    
            monitors = res.json()
            monitor = monitors['monitors'][0]['Monitor']
            monitor_id = monitor['Id']
        
        protocol = body.get('protocol', camera['protocol'])
        address = body.get('address', camera['address'])
        port = body.get('port', camera['port'])
        subpath = body.get('subpath', camera['subpath'])

        camera_url = f'{protocol}://{address}:{port}/{subpath}'
            
        # Test the camera connection
        url = f'{CAMERA_VISION_AI_API_URL}/connect'
        connect = {
            'url': camera_url,
            'thumbnail': True
        }
        res = requests.post(url, json=connect)
    
        if not res.ok:
            msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to test the camera url connection using the Process Stream API"}
            print(f'ERROR IN PUT REQUEST TO UPDATE CAMERA | {msg}')
            return jsonify(msg), 500
    
        connection = res.json()
    
        if not connection['connected']:
            msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to connect to the camera url connection using the Process Stream API"}
            print(f'ERROR IN PUT REQUEST TO UPDATE CAMERA | {msg}')
            return jsonify(msg), 500

        del connection['image']
        width = connection['width'] 
        height = connection['height']
        fps = connection['fps']

        # Include the new connection in the update object
        body = {**body, **connection}
        
        if update_monitor and camera['monitor_id']:
            zm_url = f'http://{ZONEMINDER_IP}/zm/cgi-bin/nph-zms?monitor={monitor_id}&width={width}px&height={height}px&maxfps={fps}&buffer=1000&scale=100&mode=jpeg'
    
            # Include the new zm monitor url in the update object
            body = {**body, 'zm_url': zm_url}

            # get updated camera object
            # camera_updated = {**camera, **body, **connection}
            
            # Define monitor data
            monitor_width = width
            monitor_height = height
            
            if protocol == 'rtsp':
                monitor_type = 'Ffmpeg'
                monitor_method = 'rtpRtsp'
                monitor_protocol = None
                monitor_host = None
                monitor_port = ''
                monitor_path = camera_url
            
            else:
                monitor_type = 'Remote'
                monitor_method = 'simple'
                monitor_protocol = protocol
                monitor_host = address
                monitor_port = port
                monitor_path = f'/{subpath}'
        
            url = f"{ZONEMINDER_API_URL}/monitors/{monitor_id}.json?token={zm_token}"
        
            monitor_update = {
                'Type': monitor_type,
                'Method': monitor_method,
                'Protocol': monitor_protocol,
                'Host': monitor_host,
                'Port': monitor_port,
                'Path': monitor_path,
                'Width': monitor_width,
                'Height': monitor_height,
                # Fields ignored
                # 'Name': monitor_name,
                # 'Function': monitor_function,
                # 'Colours': monitor_colours,
                # 'User': None,
                # 'Pass': None,
            }
            
            monitor_update = {f'Monitor[{key}]': value for key, value in monitor_update.items()}
            
            res = requests.post(url, data=monitor_update)
        
            if not res.ok:
                msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to update monitor in zoneminder"}
                print(f'ERROR IN PUT REQUEST TO UPDATE CAMERA | {msg}')
                return jsonify(msg), 500

    # Make a request to MongoDB API to create a configuration object
    url = f'{MONGO_API_URL}/octacity/cameras/{camera_id}'
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.put(url, json=body, headers=headers)

    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to update camera object in mongo collection'}
        print(f'ERROR IN PUT REQUEST TO UPDATE CAMERA | {msg}')
        return jsonify(msg), 500

    # Get the created camera object
    updated = res.json()
    camera_update = updated['data'] # should return the same value as `body` by now
    
    msg = {'camera_id': camera_id, 'ok': True, 'data': camera_update, 'detail': "Camera object updated and monitor updated successfully"}
    print(f'PUT REQUEST TO UPDATE CAMERA FINISHED | {msg}')
    return jsonify(msg), 200

# Endpoint to create a new configuration object in MongoDB and create a job in Cloud Scheduler
@app.route("/cameras/<camera_id>", methods=["DELETE"])
def delete_camera_and_monitor(camera_id):

    # Login to MongoDB API
    mongo_token = mongodb_login()
    if mongo_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to MongoDB API"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    # Make a request to MongoDB API to get the camera object
    url = f'{MONGO_API_URL}/octacity/cameras/{camera_id}'
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.get(url, headers=headers)

    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to get camera object from MongoDB"}
        print(f'ERROR IN DELETE REQUEST TO DELETE CAMERA | {msg}')
        return jsonify(msg), 500

    camera = res.json()

    if camera['monitor_id']:
        zm_token = zm_login()
        if zm_token is None:
            msg = {'ok': False, 'detail': f"Failed to login to zoneminder"}
            print(f'ERROR IN PUT REQUEST TO UPDATE CAMERA | {msg}')
            return jsonify(msg), 500
    
        monitor_name = camera_id
        url = f'{ZONEMINDER_API_URL}/monitors/index/Name:{monitor_name}.json?token={zm_token}'
        res = requests.get(url)
        
        if not res.ok:
            msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to get monitor from zoneminder"}
            print(f'ERROR IN DELETE REQUEST TO DELETE CAMERA | {msg}')
            return jsonify(msg), 500
    
        monitors = res.json()
    
        monitor_deleted = {'ok': False, 'status': 'failed', 'statustext': 'Monitor not found in zoneminder'}
        if len(monitors['monitors']):
            monitor = monitors['monitors'][0]['Monitor']
            monitor_id = monitor['Id']
    
            url = f'{ZONEMINDER_API_URL}/monitors/{monitor_id}.json?token={zm_token}'
            res = requests.delete(url)
        
            if not res.ok or not res.json()['status'] == 'ok':
                msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to delete monitor from zoneminder"}
                print(f'ERROR IN DELETE REQUEST TO DELETE CAMERA | {msg}')
                return jsonify(msg), 500
        
            monitor_deleted = res.json()

    # Make a request to MongoDB API to delete a camera object
    url = f'{MONGO_API_URL}/octacity/cameras/{camera_id}'
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.delete(url, headers=headers)

    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to delete camera object from mongo collection'}
        print(f'ERROR IN DELETE REQUEST TO DELETE CAMERA | {msg}')
        return jsonify(msg), 500

    camera_deleted = res.json()
    camera_id = camera_deleted['deleted_record_id']
            
    data = {'camera_deleted': camera_deleted}

    if camera['monitor_id']:
        data['monitor_deleted'] = monitor_deleted
    
    msg = {'camera_id': camera_id, 'ok': True, 'data': data, 'detail': "Camera object and monitor deleted successfully"}
    print(f'DELETE REQUEST TO DELETE CAMERA FINISHED | {msg}')
    return jsonify(msg), 200


# Endpoint to create a new configuration object in MongoDB and create a job in Cloud Scheduler
@app.route("/config", methods=["POST"])
def create_config_and_job():
    # Get body from the request
    body = request.json

    # Get attribute values from body
    camera_id = body['camera_id']
    class_id = body['class_id']
    schedule = body['schedule'] # example: "0 15 * * *"
    time_zone = body.get('time_zone', 'America/Sao_Paulo')
    start_time = body.get('start_time', '00:00:00')
    end_time = body.get('end_time', '23:59:59')

    # Login to MongoDB API
    mongo_token = mongodb_login()
    if mongo_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to MongoDB API"}
        print(f'ERROR IN LOGGING INTO MONGO API | {msg}')
        return jsonify(msg), 500

    # Make a request to MongoDB API to get the camera object
    url = f'{MONGO_API_URL}/octacity/cameras/{camera_id}'
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.get(url, headers=headers)

    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f'Failed to get camera object from mongo collection'}
        print(f'ERROR IN POST REQUEST TO GET CAMERA OBJECT FROM MONGO | {msg}')
        return jsonify(msg), 500

    camera = res.json()

    # Add user_id to the body so to include it in the config object for convenience access
    user_id = camera['user_id']
    body['user_id'] = user_id
    
    # Make a request to MongoDB API to create a configuration object
    url = f"{MONGO_API_URL}/octacity/configs"
    config_body = {
        **body,
        'time_zone': time_zone,
        'start_time': start_time,
        'end_time': end_time
    }
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.post(url, json=config_body, headers=headers)
    
    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to create configuration object in mongo collection"}
        print(f'ERROR IN POST REQUEST TO CREATE CONFIG | {msg}')
        return jsonify(msg), 500

    # Get the created config object
    data = res.json()
    config = data['data']
    config_id = config['_id']
    
    # Custom attributes
    name = f"config-{config_id}"
    job_url = f'{AI_CAMERA_MANAGER_API_URL}/process_config/{config_id}'

    # If MongoDB operation succeeds, create a job in Cloud Scheduler
    job_data = {
        "project_id": SCHEDULER_PROJECT_ID,
        "location": SCHEDULER_LOCATION,
        "name": name,
        "schedule": schedule,  # Every day at 15:00 UTC
        "time_zone": time_zone,
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
    return jsonify(msg), 201

@app.route("/config/<string:config_id>", methods=["PUT"])
def update_config_and_job(config_id):
    # Get body from the request
    body = request.json

    # Login to MongoDB API
    mongo_token = mongodb_login()
    if mongo_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to MongoDB API"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    # Update the configuration object in MongoDB
    url = f"{MONGO_API_URL}/octacity/configs/{config_id}"
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.put(url, json=body, headers=headers)
    
    if not res.ok:
        msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to update config job in cloud scheduler"}
        print(f'ERROR IN PUT REQUEST TO UPDATE CONFIG | {msg}')
        return jsonify(msg), 500

    # Update the corresponding job in Cloud Scheduler
    name = f"config-{config_id}"
    data = {
        "project_id": SCHEDULER_PROJECT_ID,
        "location": SCHEDULER_LOCATION,
        "name": name,
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
    # Login to MongoDB API
    mongo_token = mongodb_login()
    if mongo_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to MongoDB API"}
        print(f'ERROR IN POST REQUEST TO CREATE CAMERA | {msg}')
        return jsonify(msg), 500

    # Delete the configuration object from MongoDB
    mongo_url = f"{MONGO_API_URL}/octacity/configs/{config_id}"
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.delete(mongo_url, headers=headers)
    
    if not res.ok:
        msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to delete configuration object from MongoDB"}
        print(f'ERROR IN DELETE REQUEST TO DELETE CONFIG | {msg}')
        return jsonify(msg), 500

    # Delete the corresponding job from Cloud Scheduler
    # Delete the job from Cloud Scheduler
    name = f"config-{config_id}"
    scheduler_url = f"{CLOUD_SCHEDULER_API_URL}/job/delete"
    data = {"project_id": SCHEDULER_PROJECT_ID, "location": SCHEDULER_LOCATION, "name": name}
    res = requests.post(scheduler_url, json=data)
    
    if not res.ok and res.status_code != 404:
        msg = {'config_id': config_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to delete job from Cloud Scheduler"}
        print(f'ERROR IN DELETE REQUEST TO DELETE CONFIG JOB | {msg}')
        return jsonify(msg), 500

    msg = {'config_id': config_id, 'ok': True, 'detail': "Configuration object deleted and job deleted successfully"}
    print(f'DELETE REQUEST TO DELETE CONFIG FINISHED | {msg}')
    return jsonify(msg), 200

# Function that will be called in parallel for each dict
def call_post_config(item):
    with app.test_request_context(json=item):
        response = create_config_and_job()
        
        # Flask responses can return a tuple (response, status_code, headers), so handle this correctly
        if isinstance(response, tuple):
            response_data, status_code = response[0], response[1]  # Unpack response tuple
        else:
            response_data = response

        # Convert response data to a JSON object if needed
        return response_data.get_json() if hasattr(response_data, 'get_json') else response_data

# Function that will be called in parallel for each config_id to delete the config
def call_delete_config(config_id):
    with app.test_request_context():
        # Manually set the path to the DELETE endpoint
        with app.test_client() as client:
            response = client.delete(f'/config/{config_id}')

        # Flask responses can return a tuple (response, status_code, headers), so handle this correctly
        if isinstance(response, tuple):
            response_data, status_code = response[0], response[1]
        else:
            response_data = response

        # Convert response data to a JSON object if needed
        return response_data.get_json() if hasattr(response_data, 'get_json') else response_data

# Endpoint to receive list of dicts and process them in parallel
@app.route('/configs', methods=['POST'])
def post_config_parallel():
    data = request.get_json()  # Expecting a list of dicts
    max_workers = None  # Number of parallel workers (threads)
    
    # Ensure data is a list of dicts
    # if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
    #     return jsonify({"error": "Invalid input format. Expected a list of dictionaries."}), 400

    # Use ThreadPoolExecutor to process each item in parallel
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit each item for parallel processing
        futures = {executor.submit(call_post_config, item): item for item in data}
        
        # Collect results as they complete
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({"error": traceback.format_exc()})

    return jsonify(results)

# Endpoint to receive a list of config IDs and delete them in parallel
@app.route('/configs/delete', methods=['POST'])
def delete_config_parallel():
    data = request.get_json()  # Expecting a list of config IDs
    max_workers = None  # Number of parallel workers (threads)
    
    # Ensure data is a list of strings (config IDs)
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        return jsonify({"error": "Invalid input format. Expected a list of config IDs (strings)."}), 400

    # Use ThreadPoolExecutor to delete each config in parallel
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit each config_id for parallel deletion
        futures = {executor.submit(call_delete_config, config_id): config_id for config_id in data}
        
        # Collect results as they complete
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({"error": traceback.format_exc()})

    return jsonify(results)

# Function that will be called in parallel for each dict
def call_post_config_parallel(items):
    with app.test_request_context(json=items):
        response = post_config_parallel()
        
        # Flask responses can return a tuple (response, status_code, headers), so handle this correctly
        if isinstance(response, tuple):
            response_data, status_code = response[0], response[1]  # Unpack response tuple
        else:
            response_data = response

        # Convert response data to a JSON object if needed
        return response_data.get_json() if hasattr(response_data, 'get_json') else response_data

# Function that will be called in parallel for each list of config IDs
def call_delete_config_parallel(config_ids):
    with app.test_request_context(json=config_ids):
        response = delete_config_parallel()
        
        # Flask responses can return a tuple (response, status_code, headers), so handle this correctly
        if isinstance(response, tuple):
            response_data, status_code = response[0], response[1]  # Unpack response tuple
        else:
            response_data = response

        # Convert response data to a JSON object if needed
        return response_data.get_json() if hasattr(response_data, 'get_json') else response_data

@app.route('/profile', methods=['POST'])
def post_profile():
    # data = request.get_json()  # Expecting a list of dicts

    # Get body from the request
    body = request.json

    # Get attribute values from body
    user_id = body['user_id'] 
    camera_ids = body['camera_ids']
    class_id = body['class_id']
    schedule = body['schedule'] # example: "0 15 * * *"
    time_zone = body.get('time_zone', 'America/Sao_Paulo')
    start_time = body.get('start_time', '00:00:00')
    end_time = body.get('end_time', '23:59:59')

    # Login to MongoDB API
    mongo_token = mongodb_login()
    if mongo_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to MongoDB API"}
        print(f'ERROR IN LOGGING INTO MONGO API | {msg}')
        return jsonify(msg), 500

    # Create multiple configs in parallel
    del body['camera_ids']
    items = [{**body, 'camera_id': _id} for _id in camera_ids]
    body['camera_ids'] = camera_ids
    configs_data = call_post_config_parallel(items)

    success = all([obj['ok'] for obj in configs_data])
    if not success:
        msg = {'ok': False, 'response': configs_data, 'detail': f"Failed to create multiple config objects in parallel in mongo collection"}
        print(f'ERROR IN POST REQUEST TO CREATE PROFILE | {msg}')
        return jsonify(msg), 500

    config_ids = [obj['data']['_id'] for obj in configs_data]
    state = 'resumed'
    
    # Make a request to MongoDB API to create a configuration object
    url = f"{MONGO_API_URL}/octacity/profiles"
    profile_body = {
        **body,
        'time_zone': time_zone,
        'start_time': start_time,
        'end_time': end_time,
        'config_ids': config_ids,
        'state': state
    }
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.post(url, json=profile_body, headers=headers)
    
    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to create profile object in mongo collection"}
        print(f'ERROR IN POST REQUEST TO CREATE PROFILE | {msg}')
        return jsonify(msg), 500

    # Get the created config object
    data = res.json()
    profile = data['data']
    profile_id = profile['_id']

    msg = {'profile_id': profile_id, 'ok': True, 'data': profile, 'configs_data': configs_data, 'detail': "Profile object created successfully"}
    print(f'POST REQUEST TO CREATE PROFILE FINISHED | {msg}')
    return jsonify(msg), 201


@app.route('/profile/<string:profile_id>', methods=['DELETE'])
def delete_profile(profile_id):

    # Login to MongoDB API
    mongo_token = mongodb_login()
    if mongo_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to MongoDB API"}
        print(f'ERROR IN LOGGING INTO MONGO API | {msg}')
        return jsonify(msg), 500

    # Make a request to MongoDB API to create a configuration object
    url = f"{MONGO_API_URL}/octacity/profiles/{profile_id}"
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.get(url, headers=headers)
    
    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to get profile object from mongo collection"}
        print(f'ERROR IN POST REQUEST TO DELETE PROFILE | {msg}')
        return jsonify(msg), 500

    # Get the created config object
    profile = res.json()

    # Create multiple configs in parallel
    delete_configs_data = call_delete_config_parallel(profile['config_ids'])

    success = all([obj['ok'] for obj in delete_configs_data])
    if not success:
        msg = {'ok': False, 'response': delete_configs_data, 'detail': f"Failed to delete multiple config objects in parallel in mongo collection"}
        print(f'ERROR IN POST REQUEST TO DELETE PROFILE | {msg}')
        return jsonify(msg), 500

    # Delete the configuration object from MongoDB
    mongo_url = f"{MONGO_API_URL}/octacity/profiles/{profile_id}"
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.delete(mongo_url, headers=headers)
    
    if not res.ok:
        msg = {'profile_id': profile_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to delete profile object from MongoDB"}
        print(f'ERROR IN DELETE REQUEST TO DELETE PROFILE | {msg}')
        return jsonify(msg), 500
    
    msg = {'profile_id': profile_id, 'ok': True, 'data': profile, 'delete_configs_data': delete_configs_data, 'detail': "Profile object deleted successfully"}
    print(f'POST REQUEST TO DELETE PROFILE FINISHED | {msg}')
    return jsonify(msg), 200

@app.route('/profile/pause', methods=['POST'])
def pause_profile():

    # Get body from the request
    body = request.json

    # Get attribute values from body
    profile_id = body['profile_id'] 
    pause = body['pause'] 
    
    # Login to MongoDB API
    mongo_token = mongodb_login()
    if mongo_token is None:
        msg = {'ok': False, 'detail': f"Failed to login to MongoDB API"}
        print(f'ERROR IN LOGGING INTO MONGO API | {msg}')
        return jsonify(msg), 500

    # Make a request to MongoDB API to get a configuration object
    url = f"{MONGO_API_URL}/octacity/profiles/{profile_id}"
    headers = {'Authorization': f'Bearer {mongo_token}'}
    res = requests.get(url, headers=headers)
    
    if not res.ok:
        msg = {'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to get profile object from mongo collection"}
        print(f'ERROR IN REQUEST TO GET PROFILE | {msg}')
        return jsonify(msg), 500

    # Get the created config object
    profile = res.json()
    
    # Delete the job from Cloud Scheduler
    names = [f"config-{config_id}" for config_id in profile['config_ids']]
    url = f"{CLOUD_SCHEDULER_API_URL}/job/pause-resume-multiple"
    data = {
        "names": names,
        "pause": pause,
        "project_id": SCHEDULER_PROJECT_ID,
        "location": SCHEDULER_LOCATION,
    }
    res = requests.post(url, json=data)
    
    if not res.ok:
        msg = {'profile_id': profile_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to pause multiple jobs from Cloud Scheduler"}
        print(f'ERROR IN POST REQUEST TO PAUSE/RESUME PROFILE JOBS | {msg}')
        return jsonify(msg), 500
    
    results = res.json()
    state = 'paused' if pause else 'resumed'

    # Make a request to MongoDB API to update a configuration object
    url = f"{MONGO_API_URL}/octacity/profiles/{profile_id}"
    headers = {'Authorization': f'Bearer {mongo_token}'}
    data = {'state': state}
    res = requests.put(url, json=data, headers=headers)

    if not res.ok:
        msg = {'profile_id': profile_id, 'ok': res.ok, 'status_code': res.status_code, 'message': res.reason, 'response': res.text, 'detail': f"Failed to update profile record in mongo collection"}
        print(f'ERROR IN PUT REQUEST TO UPDATE PROFILE | {msg}')
        return jsonify(msg), 500
    
    msg = {'profile_id': profile_id, 'ok': True, 'data': results, 'detail': "Profile jobs paused/resume successfully"}
    print(f'POST REQUEST TO PAUSE/RESUME PROFILE JOBS FINISHED | {msg}')
    return jsonify(msg), 200


app_load_time = round(time.time() - start_time, 3)
print(f'\nFLASK APPLICATION STARTED... | APP-LOAD-TIME: {app_load_time} s')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
