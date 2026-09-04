#!/usr/bin/env python3
"""Lokal server for sajtredigeraren.

Serverar sajtens filer precis som "python3 -m http.server", men lagger ocksa
till tva konverteringsrutter, bada anvanda automatiskt av verktyget som
fallback nar webblasaren sjalv inte kan avkoda en fil:

- /convert: video -> H.264 mp4 med ffmpeg (t.ex. Apple ProRes, som ingen
  webblasare kan avkoda).
- /convert-image: bild -> JPEG med macOS inbyggda "sips" (t.ex. HEIC/HEIF
  fran iPhone, som Chrome inte kan avkoda).
"""
import http.server
import os
import shutil
import subprocess
import sys
import tempfile

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8743


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/convert-image':
            self.handle_convert_image()
            return
        if self.path != '/convert':
            self.send_error(404, 'Okand rutt')
            return

        if not shutil.which('ffmpeg'):
            body = ('ffmpeg saknas pa datorn. Kor "konvertera-video" en gang i Terminalen '
                     'for att installera det (via Homebrew), starta sedan om sajt.').encode('utf-8')
            self.send_response(501)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        length = int(self.headers.get('Content-Length', 0))
        if length <= 0:
            self.send_error(400, 'Tom fil')
            return

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, 'in')
            dst = os.path.join(tmp, 'out.mp4')
            with open(src, 'wb') as f:
                remaining = length
                while remaining > 0:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)

            try:
                subprocess.run(
                    ['ffmpeg', '-y', '-i', src,
                     '-vf', "scale='min(1600,iw)':-2",
                     '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                     '-b:v', '2M', '-maxrate', '2.5M', '-bufsize', '4M',
                     '-preset', 'medium', '-c:a', 'aac', '-b:a', '128k',
                     '-movflags', '+faststart', dst],
                    check=True, capture_output=True, timeout=300,
                )
            except subprocess.CalledProcessError as e:
                msg = ('Konverteringen misslyckades: ' + e.stderr.decode('utf-8', 'replace')[-2000:])
                body = msg.encode('utf-8')
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except subprocess.TimeoutExpired:
                body = 'Konverteringen tog for lang tid (over 5 minuter).'.encode('utf-8')
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            with open(dst, 'rb') as f:
                data = f.read()

        self.send_response(200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_convert_image(self):
        if not shutil.which('sips'):
            body = 'sips saknas pa datorn (ska finnas inbyggt i macOS) - kan inte konvertera bilden.'.encode('utf-8')
            self.send_response(501)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        length = int(self.headers.get('Content-Length', 0))
        if length <= 0:
            self.send_error(400, 'Tom fil')
            return

        # sips identifierar kallformatet (t.ex. HEIC) via filandelsen, inte
        # via innehallet - skicka darfor med ratt andelse pa kallfilen.
        orig_name = self.headers.get('X-Filename', '') or ''
        ext = os.path.splitext(orig_name)[1].lower()
        if not ext or len(ext) > 6 or not all(c.isalnum() for c in ext[1:]):
            ext = '.heic'

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, 'in' + ext)
            dst = os.path.join(tmp, 'out.jpg')
            with open(src, 'wb') as f:
                remaining = length
                while remaining > 0:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)

            try:
                subprocess.run(
                    ['sips', '-s', 'format', 'jpeg', src, '--out', dst],
                    check=True, capture_output=True, timeout=60,
                )
            except subprocess.CalledProcessError as e:
                msg = ('Bildkonverteringen misslyckades: '
                       + e.stderr.decode('utf-8', 'replace')[-2000:])
                body = msg.encode('utf-8')
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except subprocess.TimeoutExpired:
                body = 'Bildkonverteringen tog for lang tid.'.encode('utf-8')
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            with open(dst, 'rb') as f:
                data = f.read()

        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)



if __name__ == '__main__':
    http.server.ThreadingHTTPServer(('', PORT), Handler).serve_forever()
