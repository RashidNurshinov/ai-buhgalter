import json,os,sys,time,subprocess,urllib.request
T=os.environ['MAX_BOT_TOKEN'];B='https://platform-api.max.ru';CHAT=sys.argv[1]
def api(method,path,body=None):
    req=urllib.request.Request(B+path,json.dumps(body).encode() if body else None,{'Authorization':T,'Content-Type':'application/json'},method=method)
    try: return json.load(urllib.request.urlopen(req,timeout=60))
    except urllib.error.HTTPError as e: return json.loads(e.read() or b'{}')
def send_video(path,text):
    up=api('POST','/uploads?type=video'); print('upload slot',{k:v for k,v in up.items() if k!='url'})
    r=subprocess.run(['curl','-sS','--retry','3','-F','data=@'+path,up['url']],capture_output=True,text=True); print('upload resp',r.stdout[:200],r.stderr[:200])
    tok=up.get('token') or json.loads(r.stdout).get('token')
    for i in range(20):
        res=api('POST',f'/messages?chat_id={CHAT}',{'text':text,'attachments':[{'type':'video','payload':{'token':tok}}]})
        if res.get('code')=='attachment.not.ready': time.sleep(3); continue
        print('send',str(res)[:200]); return
send_video(sys.argv[2],sys.argv[3])
