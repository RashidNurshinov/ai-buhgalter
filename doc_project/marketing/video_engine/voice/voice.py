# python3 voice.py <name> <model> <voice> <pcm|mp3> <script.json> [длительность]
# script.json: [[старт, конец, "текст"], ...] — тайминги сцен из html ролика.
# Ударение ставим явно: гласная + U+0301 (Гамби́т), без этого модель говорит «гАмбит».
import sys, json, subprocess
from tts import tts
name, model, voice, fmt, script = sys.argv[1:6]
DUR = float(sys.argv[6]) if len(sys.argv) > 6 else 60
SEG = json.load(open(script))
extra={'provider':{'options':{'google':{'style':'Энергичный, бодрый голос ведущего радиорекламы, с улыбкой и напором'}}}} if 'gemini' in model else None
dur = lambda f: float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f]))
parts=[]
for i,(a,b,t) in enumerate(SEG):
    out=f'{name}_{i}'; tts(model,t,voice,out,fmt,extra)
    # обрезать тишину по краям + fade 30 мс (иначе на стыках щелчок/шипение)
    subprocess.run(['ffmpeg','-loglevel','error','-y','-i',out+'.wav','-af','silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse','-ar','44100','-ac','1',out+'_t.wav'],check=True)
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
