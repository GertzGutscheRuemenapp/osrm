import os, random
from flask import abort, Flask, request
from markupsafe import escape
import subprocess

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


@app.route("/", methods = ['GET'])
def home():
    return "OSRM Wrapper"

@app.route("/build/<mode>", methods = ['POST'])
def build(mode):
    if mode not in MODES:
        return ({ 'error': "mode '{}' unknown".format(mode) }, 400)
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
        ['osrm-customize', fp_osrm]
    ):
        process = subprocess.run(cmd)
        if process.returncode != 0:
            return ({ 'error': 'Command "{}" failed'.format(cmd[0]) }, 400)
    return ({ 'message': 'successfully built' }, 200)

@app.route("/run/<mode>", methods = ['POST'])
def run(mode):
    if mode not in MODES:
        return ({ 'error': "mode '{}' unknown".format(mode) }, 400)
    # ports
    fp_osrm = os.path.join(app.config['DATA_FOLDER'], mode + '.osrm')
    if not os.path.exists(fp_osrm):
        return ({ 'error': "mode '{}' not built yet".format(mode) }, 400)
    if app.process.get(mode):
        app.process[mode].kill()
    body = request.get_json() or {}
    port = body.get('port', PORTS.get(mode, 5000))
    app.process[mode] = subprocess.Popen(
        ['osrm-routed', '--algorithm', 'mld', '--port', str(port), fp_osrm])
    return ({ 'message': 'mode "{}" started at port {}'.format(mode, port) }, 200)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, use_reloader=True)
    for mode in MODES:
        run(mode)


