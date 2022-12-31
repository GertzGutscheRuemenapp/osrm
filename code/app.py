import os
import glob
from flask import Flask, request, make_response
import subprocess
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)

DEBUG = True

app.config['DATA_FOLDER'] = os.environ.get('DATA_FOLDER',
                                           os.path.join(os.getcwd(), 'data'))
app.config['LUA_FOLDER'] = '/opt'
app.process = {}

MODES = ['car', 'foot', 'bicycle']
PORTS = {
    'car': os.environ.get('MODE_CAR_PORT', 5001),
    'bicycle': os.environ.get('MODE_BIKE_PORT', 5002),
    'foot': os.environ.get('MODE_FOOT_PORT', 5003),
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
        return make_response(({'error': "mode '{}' unknown".format(mode)}, 400))
    file = request.files.get('file')
    if not file or not file.filename:
        return make_response(({'error': 'no file provided'}, 400))
    if app.process.get(mode):
        app.process[mode].kill()
    data_folder = app.config['DATA_FOLDER']
    if not os.path.exists(data_folder):
        os.mkdir(data_folder)
    fp_pbf = os.path.join(data_folder, mode + '.pbf')
    fp_osrm = os.path.join(data_folder, mode + '.osrm')
    fp_lua = os.path.join(app.config['LUA_FOLDER'], mode + '.lua')
    file.save(fp_pbf)
    for cmd in (
        ['osrm-extract', '-p', fp_lua, fp_pbf],
        ['osrm-partition', fp_osrm],
        ['osrm-customize', fp_osrm],
        ['osrm-contract', fp_osrm]
    ):
        process = subprocess.run(cmd)
        if process.returncode != 0:
            return ({'error': 'Command "{}" failed'.format(cmd[0])}, 400)
    msg = 'router "{}" successfully built'.format(mode)
    logger.info(msg)
    return make_response(({'message': msg}, 200))


@app.route("/run/<mode>", methods=['POST'])
def run(mode):
    if mode not in MODES:
        msg = f"mode '{mode}' unknown"
        logger.error(msg)
        return make_response(({'error': msg}, 401))
    fp_osrm = os.path.join(app.config['DATA_FOLDER'], mode)
    if not os.path.exists(f'{fp_osrm}.osrm.edges'):
        msg = f'error: mode "{mode}" not built yet'
        logger.error(msg)
        return make_response(({'error': msg}, 402))
    if app.process.get(mode):
        app.process[mode].kill()
    body = request.get_json(silent=True) or {}
    port = body.get('port', PORTS.get(mode, 5000))
    max_table_size = body.get('max_table_size',
                              os.environ.get('MAX_TABLE_SIZE', 65535))
    app.process[mode] = subprocess.Popen(
        ['osrm-routed', '--port', str(port),
         #'--algorithm', 'mld',
         '--verbosity', 'DEBUG' if DEBUG else 'INFO',
         '--max-table-size', str(max_table_size), f'{fp_osrm}.osrm'])
    msg = f'router "{mode}" started at port {port}'
    logger.info(msg)
    return make_response(({'message': msg}, 200))


@app.route("/remove/<mode>", methods=['POST'])
def remove(mode):
    if app.process.get(mode):
        app.process[mode].kill()
    fp_osrm = os.path.join(app.config['DATA_FOLDER'], mode)
    for fp in glob.glob(f'{fp_osrm}.osrm*'):
        os.remove(fp)
    msg = f'router "{fp_osrm}" removed'
    logging.info(msg)
    return make_response(({'message': msg}, 200))


@app.route("/stop/<mode>", methods=['POST'])
def stop(mode):
    if app.process.get(mode):
        app.process[mode].kill()
        msg = f'router "{mode}" stopped'
    else:
        msg = f'router "{mode}" not running'
    logging.info(msg)
    return make_response(({'message': msg}, 200))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, use_reloader=True)
    for mode in MODES:
        run(mode)


