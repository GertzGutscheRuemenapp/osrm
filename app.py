import os, random
from flask import abort, Flask, request
from markupsafe import escape
import subprocess
import logging

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


@app.route("/", methods = ['GET'])
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

@app.route("/build/<mode>", methods = ['POST'])
def build(mode):
    if mode not in MODES:
        return ({'error': "mode '{}' unknown".format(mode)}, 400)
    file = request.files.get('file')
    if not file or not file.filename:
        return ({ 'error': 'no file provided' }, 400)
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
    logging.info(msg)
    return ({'message': msg}, 200)

@app.route("/run/<mode>", methods = ['POST'])
def run(mode):
    if mode not in MODES:
        return ({ 'error': "mode '{}' unknown".format(mode) }, 400)
    fp_osrm = os.path.join(app.config['DATA_FOLDER'], mode + '.osrm')
    if not os.path.exists(fp_osrm):
        msg = 'error: mode "{}" not built yet'.format(mode)
        logging.error(msg)
        return ({'error': msg}, 400)
    if app.process.get(mode):
        app.process[mode].kill()
    body = request.get_json() or {}
    port = body.get('port', PORTS.get(mode, 5000))
    max_table_size = body.get('max_table_size',
                              os.environ.get('MAX_TABLE_SIZE', 65535))
    app.process[mode] = subprocess.Popen(
        ['osrm-routed', '--port', str(port),
         #'--algorithm', 'mld',
         '--verbosity', 'DEBUG' if DEBUG else 'INFO',
         '--max-table-size', str(max_table_size), fp_osrm])
    msg = 'router "{}" started at port {}'.format(mode, port)
    logging.info(msg)
    return ({'message': msg}, 200)

@app.route("/remove/<mode>", methods = ['POST'])
def remove(mode):
    if app.process.get(mode):
        app.process[mode].kill()
    fp_osrm = os.path.join(app.config['DATA_FOLDER'], mode + '.osrm')
    if os.path.exists(fp_osrm):
        os.remove(fp_osrm)
    msg = 'router "{}" removed'.format(fp_osrm)
    logging.info(msg)
    return ({'message': msg}, 200)

@app.route("/stop/<mode>", methods = ['POST'])
def stop(mode):
    if app.process.get(mode):
        app.process[mode].kill()
        msg = 'router "{}" stopped'.format(mode)
    else:
        msg = 'router "{}" not running'.format(mode)
    logging.info(msg)
    return ({'message': msg}, 200)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, use_reloader=True)
    for mode in MODES:
        run(mode)


