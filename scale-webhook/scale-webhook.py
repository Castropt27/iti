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
MAX_REPLICAS = int(os.environ.get('MAX_REPLICAS', '3'))
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
    # list containers that are either managed by docker-compose (label)
    # or created by this webhook (label managed_by=scale-webhook)
    result = []
    for c in client.containers.list(all=False):
        labels = c.labels or c.attrs.get('Config', {}).get('Labels') or {}
        if labels is None:
            labels = {}
        if labels.get('com.docker.compose.service') == SERVICE_LABEL or labels.get('managed_by') == 'scale-webhook':
            result.append(c)
    return result


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
            labels={**LABELS, 'managed_by': 'scale-webhook'},
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


def run_compose_scale(desired):
    """Try to scale using docker-compose or `docker compose` plugin. Raise on failure."""
    compose_bin = shutil.which('docker-compose')
    if compose_bin:
        cmd = ['docker-compose', 'up', '-d', '--scale', f'flask-app={desired}']
    else:
        docker_bin = shutil.which('docker')
        if docker_bin:
            cmd = ['docker', 'compose', 'up', '-d', '--scale', f'flask-app={desired}']
        else:
            raise FileNotFoundError('docker-compose or docker not found')
    subprocess.run(cmd, check=True, cwd=os.getcwd())


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
                try:
                    run_compose_scale(desired)
                    results.append({'alert': alertname, 'action': 'scaled_up_compose', 'from': cur, 'to': desired})
                except Exception:
                    # fallback: create containers via SDK (labelled)
                    for i in range(desired - cur):
                        try:
                            c = create_container()
                            created.append(c.name)
                        except Exception as e:
                            results.append({'alert': alertname, 'error': str(e)})
                    results.append({'alert': alertname, 'action': 'scaled_up', 'from': cur, 'to': desired, 'created': created})
        elif alertname == 'ScaleDownNetworkThroughput':
            cur = current_replicas()
            # try to read numeric value sent in alert annotations (added in rules as {{ $value }})
            annotations = a.get('annotations', {}) or {}
            value_str = annotations.get('value') or a.get('value')
            value = None
            try:
                if value_str is not None:
                    # Prometheus $value may include scientific notation - parse as float
                    value = float(value_str)
            except Exception:
                value = None

            # Safety: never remove the very last instance
            if cur <= MIN_REPLICAS:
                results.append({'alert': alertname, 'action': 'min_reached', 'current': cur})
            else:
                # If only one instance left, and measured throughput is very low (<500), do not scale down
                if cur == 1 and value is not None and value < 500:
                    results.append({'alert': alertname, 'action': 'keep_last_low_throughput', 'current': cur, 'value': value})
                else:
                    desired = max(cur - SCALE_STEP, MIN_REPLICAS)
                    if desired >= cur:
                        results.append({'alert': alertname, 'action': 'no_change', 'current': cur})
                    else:
                        # Prefer docker-compose scale if available
                        try:
                            run_compose_scale(desired)
                            results.append({'alert': alertname, 'action': 'scaled_down_compose', 'from': cur, 'to': desired})
                        except Exception:
                            removed = []
                            for i in range(cur - desired):
                                ok, info = remove_one_container()
                                removed.append({'ok': ok, 'info': info})
                            results.append({'alert': alertname, 'action': 'scaled_down', 'from': cur, 'to': desired, 'removed': removed})
        else:
            results.append({'alert': labels.get('alertname'), 'action': 'ignored'})

    return jsonify({'result': results}), 200


@app.route('/', methods=['GET'])
def index():
    return jsonify({'status': 'ok', 'service': 'scale-webhook'}), 200


if __name__ == '__main__':
    # ensure at least MIN_REPLICAS exist
    time.sleep(1)
    try:
        try:
            # prefer compose scaling on startup
            run_compose_scale(MIN_REPLICAS)
        except Exception:
            cur = current_replicas()
            while cur < MIN_REPLICAS:
                create_container()
                cur = current_replicas()
    except Exception:
        pass
    app.run(host='0.0.0.0', port=5001)
