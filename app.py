from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
import subprocess
import os
import urllib.parse
import time

app = FastAPI()
os.makedirs("downloads", exist_ok=True)

# global dict to hold live logs for each job
job_logs = {}

class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"

def get_clean_name(url):
    parsed = urllib.parse.urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    slug = path_parts[-1] if len(path_parts) > 0 else "video"
    query = urllib.parse.parse_qs(parsed.query)
    ep = query.get('ep', ['1'])[0]
    return f"{slug}_ep_{ep}"

def run_ripper(url, filename, quality):
    job_logs[filename] = []
    output_path = f"downloads/{filename}"
    
    # run the ripper and capture stdout live
    process = subprocess.Popen(
        ["python3", "-u", "miruro_dom.py", url, output_path, quality],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    for line in process.stdout:
        job_logs[filename].append(line.strip())
    process.wait()

@app.get("/")
def index():
    return HTMLResponse("""
    <html>
        <head>
            <title>PENGUIN Miruro Ripper</title>
            <style>
                body { background-color: #111; color: #fff; font-family: monospace; text-align: center; padding-top: 50px; }
                .container { max-width: 600px; margin: auto; }
                input { width: 80%; padding: 10px; background: #222; color: #fff; border: 1px solid #444; margin-bottom: 10px; }
                select { padding: 10px; background: #222; color: #fff; border: 1px solid #444; margin-bottom: 10px; }
                button { padding: 10px 20px; background: #e50914; color: #fff; border: none; cursor: pointer; width: 80%; }
                button:hover { background: #f6121d; }
                #status { margin-top: 20px; color: #4caf50; white-space: pre-wrap; text-align: left; padding: 15px; background: #000; border: 1px solid #333; height: 200px; overflow-y: auto; }
                a { color: #fff; text-decoration: none; padding: 10px 20px; background: #333; display: inline-block; margin: 5px; border: 1px solid #555; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Miruro Downloader</h1>
                <input type="text" id="url" placeholder="Paste Miruro Episode URL">
                <br>
                <select id="quality">
                    <option value="best">Auto/Best</option>
                    <option value="1080">1080p</option>
                    <option value="720">720p</option>
                    <option value="480">480p</option>
                </select>
                <br>
                <button onclick="startDownload()">RIP IT</button>
                <div id="status">Waiting for job...</div>
            </div>

            <script>
                async function startDownload() {
                    const url = document.getElementById('url').value;
                    const quality = document.getElementById('quality').value;
                    if (!url) return;
                    
                    const statusDiv = document.getElementById('status');
                    statusDiv.innerText = 'Starting...';
                    
                    const res = await fetch('/download', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({url: url, quality: quality})
                    });
                    const data = await res.json();
                    statusDiv.innerText = 'Job started. File: ' + data.filename + '\\n';
                    
                    // start listening to the live stream
                    const eventSource = new EventSource('/stream/' + data.filename);
                    eventSource.onmessage = function(event) {
                        if (event.data === '[COMPLETED]') {
                            eventSource.close();
                            statusDiv.innerHTML += '\\n[+] DOWNLOAD COMPLETE!\\n<a href="/file/' + data.filename + '.mp4" download>DOWNLOAD MP4</a>';
                            statusDiv.scrollTop = statusDiv.scrollHeight;
                        } else {
                            statusDiv.innerText += event.data + '\\n';
                            statusDiv.scrollTop = statusDiv.scrollHeight;
                        }
                    };
                }
            </script>
        </body>
    </html>
    """)

@app.post("/download")
def download_video(req: DownloadRequest, background_tasks: BackgroundTasks):
    filename = get_clean_name(req.url)
    background_tasks.add_task(run_ripper, req.url, filename, req.quality)
    return {"status": "started", "filename": filename}

@app.get("/stream/{filename}")
def stream_logs(filename: str):
    def event_generator():
        last_idx = 0
        while True:
            if filename in job_logs:
                logs = job_logs[filename]
                while last_idx < len(logs):
                    yield f"data: {logs[last_idx]}\n\n"
                    last_idx += 1
                
                # check if file is done
                mp4_file = f"downloads/{filename}.mp4"
                if os.path.exists(mp4_file):
                    yield "data: [COMPLETED]\n\n"
                    break
            time.sleep(0.5) # poll every half second
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/file/{filename}")
def get_file(filename: str):
    return FileResponse(f"downloads/{filename}")
