import sys, subprocess
from tts import tts
# (start, end, text) — тайминги сцен из ad_template.html
SEG=[(0.3,5.8,"Гамбит! Хиты и новинки — уже у нас!"),
 (6.4,14.7,"Холодильник Босфор! Компактный, всего сто сорок три сантиметра, класс А плюс. Цена — двадцать пять тысяч девятьсот рублей!"),
 (15.3,23.7,"Хит продаж — холодильник Леран! Двести семьдесят три литра. Всего двадцать девять тысяч девятьсот!"),
 (24.3,32.2,"Смарт-телевизор Разз, тридцать два дюйма! Салют ТВ, вай-фай и блютуз."),
 (32.8,42.2,"Шкаф Феникс! Четыре двери, три ящика, ширина метр шестьдесят. Порядок — легко!"),
 (42.8,53.8,"Кровать Касли — с подъёмным механизмом и вместительной нишей. А к ней — матрас Прайм Хит!"),
 (54.4,60.0,"Ждём вас в Гамбите! Улица Торговая, три. Звоните: два — восемнадцать — шестнадцать!")]
name, model, voice, fmt = sys.argv[1:5]
extra={'provider':{'options':{'google':{'style':'Энергичный, бодрый голос ведущего радиорекламы, с улыбкой и напором'}}}} if 'gemini' in model else None
parts=[]
for i,(a,b,t) in enumerate(SEG):
    out=f'{name}_{i}'; d=tts(model,t,voice,out,fmt,extra)
    # убрать тишину по краям
    subprocess.run(['ffmpeg','-loglevel','error','-y','-i',out+'.wav','-af','silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse','-ar','44100','-ac','1',out+'_t.wav'],check=True)
    d=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',out+'_t.wav']))
    slot=b-a; f=''
    if d>slot: f=f',atempo={min(d/slot,1.35):.3f}'; print(f'  seg{i} {d:.2f}s > {slot:.2f}s, ускоряю')
    parts.append((a,out+'_t.wav',f))
inp=[];fl=[]
for k,(a,p,f) in enumerate(parts):
    inp+=['-i',p]; fl.append(f'[{k}]adelay={int(a*1000)}:all=1{f}[v{k}]')
fl.append(''.join(f'[v{k}]' for k in range(len(parts)))+f'amix=inputs={len(parts)}:normalize=0,apad=whole_dur=60[out]')
subprocess.run(['ffmpeg','-loglevel','error','-y',*inp,'-filter_complex',';'.join(fl),'-map','[out]','-t','60',name+'_voice.wav'],check=True)
print('ok',name+'_voice.wav')
