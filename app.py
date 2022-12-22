import os, random, glob
from flask import abort, Flask, request
from markupsafe import escape
import subprocess
import logging

DEBUG = True

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

app = Flask(__name__)


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

def log_subprocess_output(pipe):
    for line in iter(pipe.readline, b''):
        logger.info('got line from subprocess: %r', line)

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
    # ToDo: how to read body param (form multipart?)
    #do_contract = request.data.json.get('contract')
    do_contract = False
    if app.process.get(mode):
        app.process[mode].kill()
    data_folder = app.config['DATA_FOLDER']
    if not os.path.exists(data_folder):
        os.mkdir(data_folder)
    for fn in glob.glob(os.path.join(data_folder, '{}*'.format(mode))):
        logger.info(fn)
        os.remove(fn)
    algorithm_label = 'Contraction Hierarchies' if do_contract \
        else 'Multi-Level Dijkstra'
    logger.info('Building router for mode "{}" with {} algorithm'.format(
        mode, algorithm_label))
    fp_pbf = os.path.join(data_folder, mode + '.pbf')
    fp_osrm = os.path.join(data_folder, mode + '.osrm')
    fp_lua = os.path.join(app.config['LUA_FOLDER'], mode + '.lua')
    file.save(fp_pbf)
    commands = [['osrm-extract', '-p', fp_lua, fp_pbf]]
    if do_contract:
        commands.append(['osrm-contract', fp_osrm])
    else:
        commands.append(['osrm-partition', fp_osrm])
        commands.append(['osrm-customize', fp_osrm])
    for cmd in commands:
        logger.info('running "{}"'.format(cmd[0]))
        process = subprocess.run(cmd)
        if process.returncode != 0:
            return ({'error': 'Command "{}" failed'.format(cmd[0])}, 400)
    msg = 'router "{}" successfully built'.format(mode)
    logger.info(msg)
    return ({'message': msg}, 200)

@app.route("/run/<mode>", methods = ['POST'])
def run(mode):
    if mode not in MODES:
        return ({ 'error': "mode '{}' unknown".format(mode) }, 400)
    fp_osrm = os.path.join(app.config['DATA_FOLDER'], mode + '.osrm')
    # ToDo: how to read body param (form multipart?)
    #do_contract = request.data.json.get('contract')
    do_contract = False
    if not os.path.exists(fp_osrm):
        msg = 'error: mode "{}" not built yet'.format(mode)
        logger.error(msg)
        return ({'error': msg}, 400)
    if app.process.get(mode):
        app.process[mode].kill()
    body = request.get_json() or {}
    port = body.get('port', PORTS.get(mode, 5000))
    max_table_size = body.get('max_table_size',
                              os.environ.get('MAX_TABLE_SIZE', 65535))
    algorithm_label = 'Contraction Hierarchies' if do_contract \
        else 'Multi-Level Dijkstra'
    msg = 'router "{}" started at port {} with {} algorithm'.format(mode, port, algorithm_label)
    app.process[mode] = subprocess.Popen(
        ['osrm-routed', '--port', str(port),
         '--algorithm', 'ch' if do_contract else 'mld',
         '--verbosity', 'DEBUG' if DEBUG else 'INFO',
         '--max-table-size', str(max_table_size), fp_osrm],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with app.process[mode].stdout:
        log_subprocess_output(app.process[mode].stdout)
    logger.info(msg)
    return ({'message': msg}, 200)

@app.route("/remove/<mode>", methods = ['POST'])
def remove(mode):
    if app.process.get(mode):
        app.process[mode].kill()
    fp_osrm = os.path.join(app.config['DATA_FOLDER'], mode + '.osrm')
    if os.path.exists(fp_osrm):
        os.remove(fp_osrm)
    msg = 'router "{}" removed'.format(fp_osrm)
    logger.info(msg)
    return ({'message': msg}, 200)

@app.route("/stop/<mode>", methods = ['POST'])
def stop(mode):
    if app.process.get(mode):
        app.process[mode].kill()
        msg = 'router "{}" stopped'.format(mode)
    else:
        msg = 'router "{}" not running'.format(mode)
    logger.info(msg)
    return ({'message': msg}, 200)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, use_reloader=True)
    for mode in MODES:
        run(mode)


