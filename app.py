import os, glob
from flask import Flask, request
import subprocess
DEBUG = False

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
    return '''
    <h2>OSRM Wrapper</h2>
    <b>modes</b>: 'car' / 'bicycle' / 'foot'
    <br>
    POST <b>/build/{mode}</b> to build network (pbf-file in body as 'files', body param 'contract' - true to build with Contract Hierarchies) <br>
    POST <b>/run/{mode}</b> to run router (body param 'contract' - true to run with Contract Hierarchies) <br>
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

    do_contract = request.form.get('contract', '').lower() == 'true'
    if app.process.get(mode):
        app.process[mode].kill()
    data_folder = app.config['DATA_FOLDER']
    if not os.path.exists(data_folder):
        os.mkdir(data_folder)
    for fn in glob.glob(os.path.join(data_folder, '{}*'.format(mode))):
        os.remove(fn)
    algorithm_label = 'Contraction Hierarchies' if do_contract \
        else 'Multi-Level Dijkstra'
    print('Building router for mode "{}" with {} algorithm'.format(
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
        print('running "{}"'.format(cmd[0]))
        process = subprocess.run(cmd)
        if process.returncode != 0:
            return ({'error': 'Command "{}" failed'.format(cmd[0])}, 400)
    msg = 'router "{}" successfully built'.format(mode)
    print(msg)
    return ({'message': msg}, 200)

@app.route("/run/<mode>", methods = ['POST'])
def run(mode):
    if mode not in MODES:
        return ({ 'error': "mode '{}' unknown".format(mode) }, 400)
    fp_osrm = os.path.join(app.config['DATA_FOLDER'], mode + '.osrm')
    do_contract = request.form.get('contract', '').lower() == 'true'
    if not os.path.exists(fp_osrm):
        msg = 'error: mode "{}" not built yet'.format(mode)
        print(msg)
        return ({'error': msg}, 400)
    process = app.process.get(mode)
    if process.poll() is None:
        msg = 'Router is already running. Please stop it first.'
        print(msg)
        return ({'message': msg}, 400)
    body = request.get_json() or {}
    port = body.get('port', PORTS.get(mode, 5000))
    max_table_size = body.get('max_table_size',
                              os.environ.get('MAX_TABLE_SIZE', 65535))
    algorithm_label = 'Contraction Hierarchies' if do_contract \
        else 'Multi-Level Dijkstra'
    msg = 'router "{}" started at port {} with {} algorithm'.format(
        mode, port, algorithm_label)
    app.process[mode] = subprocess.Popen(
        ['osrm-routed', '--port', str(port),
         '--algorithm', 'ch' if do_contract else 'mld',
         '--verbosity', 'DEBUG' if DEBUG else 'INFO',
         '--max-table-size', str(max_table_size), fp_osrm],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(msg)
    return ({'message': msg}, 200)

@app.route("/remove/<mode>", methods = ['POST'])
def remove(mode):
    if app.process.get(mode):
        app.process[mode].kill()
    data_folder = app.config['DATA_FOLDER']
    for fn in glob.glob(os.path.join(data_folder, '{}*'.format(mode))):
        os.remove(fn)
    msg = 'router "{}" removed'.format(mode)
    print(msg)
    return ({'message': msg}, 200)

@app.route("/stop/<mode>", methods = ['POST'])
def stop(mode):
    if app.process.get(mode):
        app.process[mode].kill()
        msg = 'router "{}" stopped'.format(mode)
    else:
        msg = 'router "{}" not running'.format(mode)
    print(msg)
    return ({'message': msg}, 200)

if __name__ == "__main__":
    if DEBUG:
        app.run(host="0.0.0.0", port=8001, use_reloader=DEBUG)
    else:
        from waitress import serve
        serve(app, host="0.0.0.0", port=8001)
    for mode in MODES:
        run(mode)


