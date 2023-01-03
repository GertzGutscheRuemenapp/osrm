import os
import glob
from flask import Flask, request, make_response
import subprocess
import logging
from waitress import serve

DEBUG = os.environ.get('DEBUG', False)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

app = Flask(__name__)


app.config['DATA_FOLDER'] = os.environ.get('DATA_FOLDER',
                                           os.path.join(os.getcwd(), 'data'))
app.config['LUA_FOLDER'] = '/opt'
app.process = {}

MODES = ['car', 'foot', 'bicycle']
PORTS_CH = {
    'car': os.environ.get('MODE_CAR_PORT', 5001),
    'bicycle': os.environ.get('MODE_BIKE_PORT', 5002),
    'foot': os.environ.get('MODE_FOOT_PORT', 5003),
}
PORTS_MLD = {
    'car': os.environ.get('MODE_CAR_PORT', 5004),
    'bicycle': os.environ.get('MODE_BIKE_PORT', 5005),
    'foot': os.environ.get('MODE_FOOT_PORT', 5006),
}


@app.route("/", methods=['GET'])
def home():
    return '''
    <h2>OSRM Wrapper</h2>
    <b>modes</b>: 'car' / 'bicycle' / 'foot'
    <br>
    POST <b>/build/{mode}</b> to build network (pbf-file in body) <br>
    POST <b>/run/{mode}</b> to run router <br>
    POST <b>/remove/{mode}</b> to remove network physically <br>
    POST <b>/stop/{mode}</b> to stop router <br>
    '''


@app.route("/build/<mode>", methods=['POST'])
def build(mode):
    if mode not in MODES:
        return make_response(({f'error': "mode '{mode}' unknown"}, 400))
    file = request.files.get('file')
    if not file or not file.filename:
        return make_response(({'error': 'no file provided'}, 400))

    algorithms = ('ch', 'mld')
    for algorithm in algorithms:
        if app.process.get((mode, algorithm)):
            app.process[(mode, algorithm)].kill()
            msg = f'router "{mode}" for "{algorithm}" stopped'
        else:
            msg = f'router "{mode}" for "{algorithm}" not running'
    data_folder = app.config['DATA_FOLDER']
    if not os.path.exists(data_folder):
        os.mkdir(data_folder)
    for fn in glob.glob(os.path.join(data_folder, f'{mode}*')):
        print(fn)
        os.remove(fn)

    algorithm_label = 'Contraction Hierarchies and Multi-Level Dijkstra'
    print(
        f'Building router for mode "{mode}" with {algorithm_label} algorithm')
    fp_pbf = os.path.join(data_folder, mode + '.pbf')
    fp_osrm = os.path.join(data_folder, mode + '.osrm')
    fp_lua = os.path.join(app.config['LUA_FOLDER'], mode + '.lua')
    file.save(fp_pbf)
    commands = [['osrm-extract', '-p', fp_lua, fp_pbf]]
    commands.append(['osrm-partition', fp_osrm])
    commands.append(['osrm-customize', fp_osrm])
    commands.append(['osrm-contract', fp_osrm])
    for cmd in commands:
        print('running "{}"'.format(cmd[0]))
        process = subprocess.run(cmd)
        if process.returncode != 0:
            return ({'error': 'Command "{}" failed'.format(cmd[0])}, 400)
    msg = 'router "{}" successfully built'.format(mode)
    print(msg)
    return make_response(({'message': msg}, 200))


@app.route("/run/<mode>", methods=['POST'])
def run(mode):
    if mode not in MODES:
        msg = f"mode '{mode}' unknown"
        logger.error(msg)
        return make_response(({'error': msg}, 400))
    fp_osrm = os.path.join(app.config['DATA_FOLDER'], mode)

    algorithm = request.form.get('algorithm', 'ch')
    if algorithm == 'ch':
        PORTS = PORTS_CH
    else:
        PORTS = PORTS_MLD

    if not os.path.exists(f'{fp_osrm}.osrm.edges'):
        msg = f'error: mode "{mode}" not built yet'
        logger.error(msg)
        return make_response(({'error': msg}, 400))

    process = app.process.get((mode, algorithm))
    if process and process.poll() is None:
        msg = 'Router is already running. Please stop it first.'
        logger.error(msg)
        return ({'message': msg}, 400)
    body = request.get_json(silent=True) or {}
    port = body.get('port', PORTS.get(mode, 5000))
    max_table_size = body.get('max_table_size',
                              os.environ.get('MAX_TABLE_SIZE', 65535))
    app.process[(mode, algorithm)] = subprocess.Popen(
        ['osrm-routed', '--port', str(port),
         '--algorithm', algorithm,
         '--verbosity', 'DEBUG' if DEBUG else 'INFO',
         '--max-table-size', str(max_table_size),
         f'{fp_osrm}.osrm',
         ],
    )

    algorithm_label = 'Contraction Hierarchies' if algorithm =='ch' \
        else 'Multi-Level Dijkstra'
    msg = f'router "{mode}" started at port {port} with {algorithm_label} algorithm'
    print(msg)
    return make_response(({'message': msg}, 200))


@app.route("/remove/<mode>", methods=['POST'])
def remove(mode):
    for algorithm in ('ch', 'mld'):
        if app.process.get((mode, algorithm)):
            app.process[(mode, algorithm)].kill()
    fp_osrm = os.path.join(app.config['DATA_FOLDER'], mode)
    for fp in glob.glob(f'{fp_osrm}.osrm*'):
        os.remove(fp)
    msg = f'router "{fp_osrm}" removed'
    print(msg)
    return make_response(({'message': msg}, 200))


@app.route("/stop/<mode>", methods=['POST'])
def stop(mode):
    algorithm = request.form.get('algorithm')
    algorithms = [algorithm] if algorithm else ('ch', 'mld')
    for algorithm in algorithms:
        if app.process.get((mode, algorithm)):
            app.process[(mode, algorithm)].kill()
            msg = f'router "{mode}" for "{algorithm}" stopped'
        else:
            msg = f'router "{mode}" for "{algorithm}" not running'
    logging.info(msg)
    return make_response(({'message': msg}, 200))


if __name__ == "__main__":
    port = os.environ.get('SERVICE_PORT', 8001)
    if DEBUG:
        app.run(host="0.0.0.0", port=port, use_reloader=True)
    else:
        serve(app, host="0.0.0.0", port=8001)
