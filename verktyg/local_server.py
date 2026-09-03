#!/usr/bin/env python3
"""Lokal server for sajtredigeraren.

Serverar sajtens filer precis som "python3 -m http.server", men lagger ocksa
till en /convert-rutt: tar emot en videofil som POST-kropp och konverterar
den till H.264 mp4 med ffmpeg, for klipp webblasaren inte kan avkoda sjalv
(t.ex. Apple ProRes). Anvands automatiskt av verktyget som fallback nar den
inbyggda WebCodecs-konverteringen i webblasaren misslyckas.
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


if __name__ == '__main__':
    http.server.ThreadingHTTPServer(('', PORT), Handler).serve_forever()
