"""Render cards. python3 render.py posts.json outdir. Each post: {id, lane, text}. Writes <id>.jpg, <id>.mp4 and report.json. A card that fails its layout check is not written."""
import json,sys,subprocess,pathlib,urllib.request,hashlib
from playwright.sync_api import sync_playwright
H=pathlib.Path(__file__).resolve().parent;posts=json.load(open(sys.argv[1]));O=pathlib.Path(sys.argv[2]);O.mkdir(parents=True,exist_ok=True);FPS=30
TRACKS=[282,135,173,131,872]  # Mixkit, fetched at build time, never stored here
def music(pid):
    t=TRACKS[int(hashlib.sha1(pid.encode()).hexdigest(),16)%len(TRACKS)];f=O/f"m{t}.mp3"
    if not f.exists():
        r=urllib.request.Request(f"https://assets.mixkit.co/music/{t}/{t}.mp3",headers={"User-Agent":"Mozilla/5.0"});f.write_bytes(urllib.request.urlopen(r,timeout=60).read())
    assert f.stat().st_size>200000,("music too small",f);return f
rep=[]
with sync_playwright() as p:
    b=p.chromium.launch(channel="chrome")
    for x in posts:
        r={"id":x["id"],"lane":x["lane"]}
        try:
            g=b.new_page(viewport={"width":1080,"height":1350});g.goto((H/"card.html").as_uri());s=g.evaluate("p=>setup(p,false)",x);r["still"]=s
            g.evaluate("()=>document.querySelector('#bar').remove()")
            if not s["ok"] or not s["font"]: raise ValueError("still: "+", ".join(s["why"] or ["font missing"]))
            g.screenshot(path=str(O/f"{x['id']}.jpg"),type="jpeg",quality=93);g.close()
            g=b.new_page(viewport={"width":1080,"height":1920});g.goto((H/"card.html").as_uri());s=g.evaluate("p=>setupMove(p)",x);r["video"]=s
            if not s["ok"] or not s["font"]: raise ValueError("video: "+", ".join(s["why"] or ["font missing"]))
            D=round(s["secs"],2);assert 5<=D<=28,("length",D);n=int(D*FPS);out=O/f"{x['id']}.mp4"
            ff=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","image2pipe","-framerate",str(FPS),"-c:v","mjpeg","-i","-","-ss","4","-i",str(music(x["id"])),"-t",str(D),"-map","0:v","-map","1:a","-af",f"loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:d=0.2,afade=t=out:st={D-.9}:d=0.9","-c:v","libx264","-preset","medium","-crf","18","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-ar","44100","-movflags","+faststart",str(out)],stdin=subprocess.PIPE)
            for i in range(n):
                g.evaluate("t=>seek(t)",i/FPS);ff.stdin.write(g.screenshot(type="jpeg",quality=95))
            ff.stdin.close();assert ff.wait()==0,"ffmpeg failed";g.close()
            q=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(out)]))
            kinds={y["codec_type"] for y in q["streams"]};assert kinds>={"video","audio"},kinds
            r.update(ok=True,secs=round(float(q["format"]["duration"]),2),bytes=out.stat().st_size)
        except Exception as e:
            r.update(ok=False,error=str(e)[:200])
            for f in (O/f"{x['id']}.jpg",O/f"{x['id']}.mp4"): f.unlink(missing_ok=True)
        rep.append(r);print(r["id"],r.get("ok"),r.get("secs"),r.get("error",""),flush=True)
    b.close()
for f in O.glob("m*.mp3"): f.unlink()
json.dump(rep,open(O/"report.json","w"),indent=1);sys.exit(0 if any(r["ok"] for r in rep) else 1)
