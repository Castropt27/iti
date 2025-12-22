from flask import Flask, request, jsonify
import docker
import os
import time
import shutil
import subprocess

app = Flask(__name__)
client = docker.from_env()

# configuration
SERVICE_LABEL = os.environ.get('SERVICE_LABEL', 'flask-app')
MIN_REPLICAS = int(os.environ.get('MIN_REPLICAS', '1'))
MAX_REPLICAS = int(os.environ.get('MAX_REPLICAS', '10'))
SCALE_STEP = int(os.environ.get('SCALE_STEP', '1'))
DATA_VOLUME_HOST = os.environ.get('DATA_VOLUME_HOST', '/home/valdemarcastro/projetocliente')
DATA_VOLUME_CONTAINER = os.environ.get('DATA_VOLUME_CONTAINER', '/data')
IMAGE_FALLBACK = os.environ.get('IMAGE_FALLBACK', 'projeto_flask-app:latest')
LABELS = {
    'traefik.enable': 'true',
    'traefik.http.routers.flask.rule': 'Host(`localhost`)',
    'traefik.http.routers.flask.entrypoints': 'web',
    'traefik.http.services.flask.loadbalancer.server.port': '8000',
    'com.docker.compose.service': SERVICE_LABEL,
}
NETWORKS = ['monitoring', 'traefik_net']


def get_service_containers():
    # list containers that have the compose service label
    return client.containers.list(all=False, filters={'label': f'com.docker.compose.service={SERVICE_LABEL}'})


def current_replicas():
    return len(get_service_containers())


def choose_image():
    # try to infer image from an existing container
    ctrs = get_service_containers()
    if ctrs:
        try:
            tags = ctrs[0].image.tags
            if tags:
                return tags[0]
        except Exception:
            pass
    return IMAGE_FALLBACK


def create_container():
    image = choose_image()
    env = {'FILES_STORAGE_PATH': f'{DATA_VOLUME_CONTAINER}/files.json'}
    volumes = {DATA_VOLUME_HOST: {'bind': DATA_VOLUME_CONTAINER, 'mode': 'rw'}}
    # create container attached to first network, then connect others
    try:
        container = client.containers.run(
            image,
            detach=True,
            labels=LABELS,
            environment=env,
            volumes=volumes,
            restart_policy={"Name": "always"},
            network=NETWORKS[0],
        )
    except Exception:
        # fallback: create container without mounting host volume (some hosts/NFS prevent bind)
        container = client.containers.run(
            image,
            detach=True,
            labels=LABELS,
            environment=env,
            restart_policy={"Name": "always"},
            network=NETWORKS[0],
        )
    # connect to other networks if any
    for net in NETWORKS[1:]:
        try:
            network = client.networks.get(net)
            network.connect(container)
        except Exception:
            pass
    return container


def remove_one_container():
    ctrs = get_service_containers()
    if len(ctrs) <= MIN_REPLICAS:
        return False, 'min_reached'
    # pick the newest created container to remove
    ctrs_sorted = sorted(ctrs, key=lambda c: c.attrs.get('Created', ''), reverse=True)
    target = ctrs_sorted[0]
    try:
        target.stop(timeout=5)
        target.remove()
        return True, target.name
    except Exception as e:
        return False, str(e)


@app.route('/alert', methods=['POST'])
def alert():
    payload = request.get_json()
    if not payload:
        return jsonify({'error': 'bad payload'}), 400

    results = []
    alerts = payload.get('alerts') or []
    for a in alerts:
        labels = a.get('labels', {})
        alertname = labels.get('alertname')
        state = a.get('status') or a.get('state') or a.get('status')
        if not state:
            state = a.get('state', 'firing')

        # Only act on firing alerts
        if a.get('status', a.get('state')) == 'resolved' or a.get('status') == 'resolved':
            # If resolved, do nothing (could scale down policy)
            results.append({'alert': alertname, 'action': 'ignored_resolved'})
            continue

        if alertname == 'ScaleUpNetworkThroughput':
            cur = current_replicas()
            desired = min(cur + SCALE_STEP, MAX_REPLICAS)
            if desired <= cur:
                results.append({'alert': alertname, 'action': 'no_change', 'current': cur})
            else:
                # Prefer invoking docker-compose on host if available (simpler/mount-safe)
                created = []
                compose_bin = shutil.which('docker-compose') or shutil.which('docker')
                if compose_bin and shutil.which('docker-compose'):
                    # use `docker-compose up -d --scale flask-app=desired`
                    try:
                        subprocess.run(['docker-compose', 'up', '-d', f'--scale', f'flask-app={desired}'], check=True, cwd=os.getcwd())
                        results.append({'alert': alertname, 'action': 'scaled_up_compose', 'from': cur, 'to': desired})
                    except Exception as e:
                        results.append({'alert': alertname, 'error': str(e)})
                else:
                    for i in range(desired - cur):
                        try:
                            c = create_container()
                            created.append(c.name)
                        except Exception as e:
                            results.append({'alert': alertname, 'error': str(e)})
                    results.append({'alert': alertname, 'action': 'scaled_up', 'from': cur, 'to': desired, 'created': created})
        elif alertname == 'ScaleDownNetworkThroughput':
            cur = current_replicas()
            desired = max(cur - SCALE_STEP, MIN_REPLICAS)
            if desired >= cur:
                results.append({'alert': alertname, 'action': 'no_change', 'current': cur})
            else:
                # Prefer docker-compose scale if available
                if shutil.which('docker-compose'):
                    try:
                        subprocess.run(['docker-compose', 'up', '-d', f'--scale', f'flask-app={desired}'], check=True, cwd=os.getcwd())
                        results.append({'alert': alertname, 'action': 'scaled_down_compose', 'from': cur, 'to': desired})
                    except Exception as e:
                        results.append({'alert': alertname, 'error': str(e)})
                else:
                    removed = []
                    for i in range(cur - desired):
                        ok, info = remove_one_container()
                        removed.append({'ok': ok, 'info': info})
                    results.append({'alert': alertname, 'action': 'scaled_down', 'from': cur, 'to': desired, 'removed': removed})
        else:
            results.append({'alert': labels.get('alertname'), 'action': 'ignored'})

    return jsonify({'result': results}), 200


if __name__ == '__main__':
    # ensure at least MIN_REPLICAS exist
    time.sleep(1)
    try:
        cur = current_replicas()
        while cur < MIN_REPLICAS:
            create_container()
            cur = current_replicas()
    except Exception:
        pass
    app.run(host='0.0.0.0', port=5001)
