import asyncio
from playwright.async_api import async_playwright
import subprocess
import sys

async def get_streams_with_playwright(url):
    print(f"[*] launching headless firefox (render cloud)...")
    streams = {"video": None, "sub": None}
    
    async with async_playwright() as p:
        # added low-memory args for render's 512MB limit
        browser = await p.firefox.launch(
            headless=True,
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--single-process'
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        # intercept network requests
        def handle_request(request):
            req_url = request.url
            if '.m3u8' in req_url and not streams["video"]:
                print(f"[+] 🚨 CAUGHT VIDEO STREAM")
                streams["video"] = req_url
            if ('.vtt' in req_url or '.srt' in req_url) and not streams["sub"]:
                print(f"[+] 📝 CAUGHT SUBTITLE TRACK")
                streams["sub"] = req_url

        page.on('request', handle_request)
        
        print(f"[*] hitting {url}...")
        try:
            # strict 30-second timeout
            await page.goto(url, {'wait_until': 'domcontentloaded', 'timeout': 30000})
            
            # inject stealth script to bypass cloudflare
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
            """)
            
            # wait up to 15 seconds for the stream to fire
            for _ in range(15):
                if streams["video"]:
                    break
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"[-] error: {e}")
        finally:
            await browser.close()
            
    return streams

# ... keep the rest of the file the same (download_video, etc)

def download_video(streams, output_base, quality="best"):
    print(f"[*] passing to yt-dlp with aria2c (MAX SPEED)...")
    
    if quality == "1080":
        fmt = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    elif quality == "720":
        fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]"
    elif quality == "480":
        fmt = "bestvideo[height<=480]+bestaudio/best[height<=480]"
    else:
        fmt = "best"
    
    cmd = [
        "yt-dlp",
        "-N", "32",               # 32 parallel workers (double the previous)
        "--downloader", "aria2c",
        "--downloader-args", "aria2c:-x 16 -s 32 -k 1M -j 16", # maxed out aria2c config
        "--http-chunk-size", "1M", # break fragments into 1MB pieces for more threads
        "-f", fmt,
        "-o", f"{output_base}.mp4",
        "--no-warnings",
        "--newline",
        "--progress-template", "download:[%(progress._percent_str)s] Speed: %(progress._speed_str)s | ETA: %(progress._eta_str)s | Frag: %(progress.fragment_index)s/%(progress.fragment_count)s",
        "--referer", "https://strm.cx/",
        streams["video"]
    ]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in process.stdout:
        print(line.strip(), flush=True)
        
    if streams["sub"]:
        print(f"[*] downloading subtitle...")
        sub_cmd = ["wget", "-q", "-O", f"{output_base}.vtt", streams["sub"]]
        subprocess.run(sub_cmd)
        print(f"[+] subtitle saved.")

if __name__ == "__main__":
    url = sys.argv[1]
    output_base = sys.argv[2] if len(sys.argv) > 2 else url.split("/")[-1].replace("?ep=", "_ep_")
    quality = sys.argv[3] if len(sys.argv) > 3 else "best"
    
    # run the async function properly
    streams = asyncio.get_event_loop().run_until_complete(get_streams_with_playwright(url))
    
    if streams["video"]:
        download_video(streams, output_base, quality)
    else:
        print("[-] no m3u8 stream caught.")
