# python3 voice.py <name> <model> <voice> <pcm|mp3> <script.json> [длительность]
# script.json: [[старт, конец, "текст"], ...] — тайминги сцен из html ролика.
# Ударение ставим явно: гласная + U+0301 (Гамби́т), без этого модель говорит «гАмбит».
import sys, os, json, subprocess
from tts import tts
name, model, voice, fmt, script = sys.argv[1:6]
DUR = float(sys.argv[6]) if len(sys.argv) > 6 else 60
SEG = json.load(open(script))
STYLE=os.environ.get('STYLE','Энергичный, бодрый голос ведущего радиорекламы, с улыбкой и напором')  # STYLE=... — другая подача
extra={'provider':{'options':{'google':{'style':STYLE}}}} if 'gemini' in model else None
dur = lambda f: float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f]))
def strip_bursts(src, dst):
    """Gemini TTS добавляет в начало и конец отрезка короткий всплеск белого шума
    (на слух — «шипение рации» между сценами). Отрезаем всё, что отделено от речи
    паузой ≥ 0,12 с в первых/последних 0,6 с."""
    import numpy as np
    raw = subprocess.run(['ffmpeg','-loglevel','error','-i',src,'-ac','1','-ar','24000','-f','f32le','-'],capture_output=True,check=True).stdout
    x = np.frombuffer(raw, np.float32).copy(); sr = 24000; w = sr // 100
    rms = np.sqrt(np.convolve(x ** 2, np.ones(w) / w, 'same')); quiet = rms < 10 ** (-55 / 20)
    def runs(m):
        r = []; st = None
        for i, q in enumerate(list(m) + [False]):
            if q and st is None: st = i
            if not q and st is not None: r.append((st, i)); st = None
        return r
    gap = int(.12 * sr); edge = int(.6 * sr)
    tail = [r for r in runs(quiet) if r[1] - r[0] >= gap and r[0] > len(x) - edge]
    if tail: x = x[:tail[-1][0] + int(.03 * sr)]
    head = [r for r in runs(quiet) if r[1] - r[0] >= gap and r[1] < edge]
    if head: x = x[max(0, head[0][1] - int(.03 * sr)):]
    subprocess.run(['ffmpeg','-loglevel','error','-y','-f','f32le','-ar','24000','-ac','1','-i','-',dst], input=x.tobytes(), check=True)
parts=[]
for i,(a,b,t) in enumerate(SEG):
    out=f'{name}_{i}'
    if not (os.environ.get('REUSE') and os.path.exists(out+'.wav')): tts(model,t,voice,out,fmt,extra)  # REUSE=1 — не генерировать заново
    # обрезать тишину по краям + fade 30 мс (иначе на стыках щелчок/шипение)
    strip_bursts(out+'.wav', out+'_c.wav')
    subprocess.run(['ffmpeg','-loglevel','error','-y','-i',out+'_c.wav','-af','silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse','-ar','44100','-ac','1',out+'_t.wav'],check=True)
    d=dur(out+'_t.wav'); slot=b-a; f=''
    if d>slot: f=f'atempo={min(d/slot,1.35):.3f},'; print(f'  seg{i} {d:.2f}s > {slot:.2f}s, ускоряю')
    d2=d/max(1,d/slot) if d>slot else d
    # atempo строго ДО adelay, иначе ускорение сжимает и задержку → наложение сцен
    parts.append((a,out+'_t.wav',f+f'afade=t=in:d=0.03,afade=t=out:st={max(0,d2-0.04):.3f}:d=0.04,'))
inp=[];fl=[]
for k,(a,p,f) in enumerate(parts):
    inp+=['-i',p]; fl.append(f'[{k}]{f}adelay={int(a*1000)}:all=1[v{k}]')
fl.append(''.join(f'[v{k}]' for k in range(len(parts)))+f'amix=inputs={len(parts)}:normalize=0,apad=whole_dur={DUR}[out]')
subprocess.run(['ffmpeg','-loglevel','error','-y',*inp,'-filter_complex',';'.join(fl),'-map','[out]','-t',str(DUR),name+'_voice.wav'],check=True)
print('ok',name+'_voice.wav')
