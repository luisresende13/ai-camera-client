import time; start_time = time.time()
import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

MONGO_API_URL = os.environ['MONGO_API_URL']
mongo_auth = {'email': 'luisresende13@gmail.com', 'password': 'Gaia0333'}

SCHEDULER_PROJECT_ID = os.environ['SCHEDULER_PROJECT_ID']
SCHEDULER_LOCATION = os.environ['SCHEDULER_LOCATION']
CLOUD_SCHEDULER_API_URL = os.environ['CLOUD_SCHEDULER_API_URL']

AI_CAMERA_MANAGER_API_URL = os.environ['AI_CAMERA_MANAGER_API_URL']
PROCESS_STREAM_API_URL = os.environ['PROCESS_STREAM_API_URL']

ZONEMINDER_IP = os.environ['ZONEMINDER_IP']
ZONEMINDER_USER_NAME = os.environ['ZONEMINDER_USER_NAME']
ZONEMINDER_PASSWORD = os.environ['ZONEMINDER_PASSWORD']

ZONEMINDER_API_URL = f'http://{ZONEMINDER_IP}/zm/api'
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
    url = f'{PROCESS_STREAM_API_URL}/connect'
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
        url = f'{PROCESS_STREAM_API_URL}/connect'
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

app_load_time = round(time.time() - start_time, 3)
print(f'\nFLASK APPLICATION STARTED... | APP-LOAD-TIME: {app_load_time} s')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
