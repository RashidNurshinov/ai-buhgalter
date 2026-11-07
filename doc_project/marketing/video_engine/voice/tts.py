import json, os, sys, subprocess, urllib.request, time
KEY=os.environ['ROUTERAI_API_KEY']
def tts(model, text, voice, out, fmt='pcm', extra=None):
    body={'model':model,'input':text,'voice':voice,'response_format':fmt}
    if extra: body.update(extra)
    for i in range(5):
        try:
            req=urllib.request.Request('https://routerai.ru/api/v1/audio/speech',json.dumps(body).encode(),
                {'Authorization':'Bearer '+KEY,'Content-Type':'application/json'})
            data=urllib.request.urlopen(req,timeout=120).read(); break
        except Exception as e:
            print('retry',e,file=sys.stderr); time.sleep(2**i)
    else: raise SystemExit('failed')
    if fmt=='pcm':
        open(out+'.pcm','wb').write(data)
        subprocess.run(['ffmpeg','-loglevel','error','-y','-f','s16le','-ar','24000','-ac','1','-i',out+'.pcm',out+'.wav'],check=True)
    else:
        open(out+'.mp3','wb').write(data)
        subprocess.run(['ffmpeg','-loglevel','error','-y','-i',out+'.mp3',out+'.wav'],check=True)
    d=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',out+'.wav']))
    print(out, round(d,2)); return d
