import sys
def hf(n,issue='№ 1 · НОЯБРЬ 2026'):
    return (f'<div class="a hdr mask" data-t="0.2" data-a="rise"><span>ГАМБИТ</span></div><div class="a hdr2" data-t="0.3" data-a="fade">{issue}</div>'
            f'<div class="a hrule" data-t="0.2" data-a="line"></div><div class="a frule"></div><div class="a fl">ГАМБИТ — ТЕХНИКА И МЕБЕЛЬ</div><div class="a fr">СТР. {n:02d}</div>')
def spec(x,y,v,l,t): return f'<div class="a spec" style="left:{x}px;top:{y}px" data-t="{t}" data-a="slideL"><div class="v">{v}</div><div class="l">{l}</div></div>'
def price(x,y,p,t,fs=64): return f'<div class="a price" style="left:{x}px;top:{y}px" data-t="{t}" data-a="slideR" data-r="-3"><div class="p1">ЦЕНА</div><div class="p2" style="font-size:{fs}px">{p}</div></div>'
def img(src,x,y,w,h,t,a='zoom',z=1): return f'<img class="a" src="{src}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;object-fit:contain;z-index:{z};filter:drop-shadow(0 24px 24px rgba(0,0,0,.22))" data-t="{t}" data-a="{a}">'
def blob(x,y,s,c,t): return f'<div class="a blob" style="left:{x}px;top:{y}px;width:{s}px;height:{s}px;background:{c}" data-t="{t}" data-a="pop"></div>'
def head(kick,col,ttl,sub,tsize=116):
    return (f'<div class="a kick" style="color:{col}" data-t="0.5" data-a="fade">{kick}</div>'
            f'<div class="a ttl mask" style="font-size:{tsize}px" data-t="0.6" data-a="rise"><span>{ttl}</span></div>'
            f'<div class="a sub" data-t="1.0" data-a="fade">{sub}</div>')
def page(t0,inner,style=''):
    return f'<div class="leaf" data-t0="{t0}"><div class="face front" style="{style}">{inner}</div></div>\n'
P=[]
# 0 обложка
lines=[('СТР. 02','УЖЕ РАЗОБРАЛИ','что ушло за неделю'),('СТР. 03','GORENJE','полный No Frost'),('СТР. 04','TCL','стирка за 15 минут'),('СТР. 05','ЗАПАСЫ НА ЗИМУ','компактный ларь'),('СТР. 06','ШКАФЫ','для порядка в доме')]
cov=('<div class="a mask" style="left:36px;top:46px;font:800 150px Unb;color:#e30613;letter-spacing:-3px;line-height:1.05" data-t="0.7" data-a="rise"><span>ГАМБИТ</span></div>'
     '<div class="a" style="left:50px;top:250px;font:800 24px Man;letter-spacing:5px;color:#141414" data-t="1.1" data-a="fade">ЖУРНАЛ О ТЕХНИКЕ И МЕБЕЛИ · № 1 · НОЯБРЬ 2026</div>'
     '<div class="a hrule" style="top:300px" data-t="1.0" data-a="line"></div>'
     + blob(380,420,640,'#f2d6c9',1.0)
     + img('img/fenix1b_cut.png',650,360,372,640,1.3,z=1) + img('img/gor61_cut.png',430,380,309,800,1.5,z=2) + img('img/tcl606g_cut.png',640,840,268,380,1.7,z=3))
for i,(a,b,c) in enumerate(lines):
    y=380+i*150;t=1.6+i*.25
    cov+=(f'<div class="a" style="left:50px;top:{y}px;width:380px;z-index:4" data-t="{t}" data-a="slideL"><div style="font:800 22px Man;color:#e30613;letter-spacing:4px">{a}</div>'
          f'<div style="font:800 {34 if len(b)<11 else 28}px Unb;color:#141414;margin-top:6px;white-space:nowrap">{b}</div><div style="font:500 24px Man;color:#6b645c;margin-top:4px">{c}</div></div>')
cov+=('<div class="a" style="left:80px;top:1110px;width:220px;height:220px;border-radius:50%;background:#e30613;color:#fff;display:flex;align-items:center;justify-content:center;text-align:center;font:800 34px Unb;line-height:1.15;z-index:5" data-t="2.8" data-a="stamp" data-r="-12">ЦЕНЫ<br>ВНУТРИ</div>'
      '<div class="a" style="left:380px;top:1262px;font:800 24px Man;color:#141414;letter-spacing:3px" data-t="2.0" data-a="fade">ул. Торговая, 3 · (35366) 2-18-16</div>')
P.append(page(0,cov))
# 1 новости
news=hf(2)+('<div class="a kick" style="color:#e30613" data-t="0.5" data-a="fade">НОВОСТИ НЕДЕЛИ</div>'
  '<div class="a ttl mask" data-t="0.6" data-a="rise"><span>УЖЕ</span></div><div class="a ttl mask" style="top:300px;font-size:100px" data-t="0.8" data-a="rise"><span>РАЗОБРАЛИ</span></div>'
  '<div class="a sub" style="top:430px" data-t="1.1" data-a="fade">из наших прошлых выпусков — уже нашли хозяев</div>')
cards=[('img/sbs_cut.png','LERAN SBS 300',4.8),('img/pozis_cut.png','POZIS RK-149',6.1),('img/sber43_cut.png','SBER 43″ 4K',6.7),('img/leran182_cut.png','LERAN FSF 182',7.9)]
for i,(src,nm,ts) in enumerate(cards):
    x=50+(i%2)*440;y=500+(i//2)*340
    news+=(f'<div class="a card" style="left:{x}px;top:{y}px;height:320px" data-t="{1.2+i*.2}" data-a="fade"><img src="{src}" style="width:340px;height:200px;bottom:80px"><div class="cn">{nm}</div></div>'
           f'<div class="a stamp" style="left:{x+170}px;top:{y+30}px" data-t="{ts}" data-a="stamp" data-r="-10">ПРОДАНО</div>')
news+='<div class="a" style="left:50px;top:1180px;font:800 32px Man;color:#e30613" data-t="9.1" data-a="fade">Новинки разбирают быстро — не откладывайте!</div>'
P.append(page(4.8,news))
# 2 GORENJE
g=hf(3)+head('ХОЛОДИЛЬНИКИ','#2a6f97','GORENJE','NRKP61EA2XL4 · полный No Frost · 185 см')+blob(20,440,470,'#dbe8f0',0.9)+img('img/gor61_cut.png',110,400,300,780,1.1)
g+=('<div class="a" style="left:300px;top:860px;width:190px;height:300px;border-radius:20px;background:#fff;box-shadow:0 14px 30px rgba(0,0,0,.2);overflow:hidden;z-index:3" data-t="8.4" data-a="pop" data-r="4">'
    '<img src="img/gor61_open_cut.png" style="position:absolute;left:10px;top:8px;width:170px;height:284px;object-fit:contain"></div>')
for i,(v,l,t) in enumerate([('302 л','полезный объём',4.3),('99 л','морозилка',5.6),('0 °C','зона свежести',8.4),('A++','класс энергии',10.2),('38 дБ','тихая работа',11.6)]): g+=spec(500,410+i*108,v,l,t)
g+='<div class="a quote" style="left:500px;top:965px;width:400px" data-t="12.4" data-a="fade">«Европейский бренд — для тех, кто ценит порядок»</div>'+price(500,1100,'42 600 ₽',13.8)
P.append(page(17.6,g))
# 3 TCL
c=hf(4)+head('СТИРКА','#2f8a57','TCL','W-SF606G · узкая, глубина 40 см')+blob(460,450,460,'#e3eedd',0.9)+img('img/tcl606g_cut.png',480,520,410,580,1.1)
for i,(v,l,t) in enumerate([('6 кг','загрузка',2.1),('ИНВЕРТОР','тихий мотор',3.2),('A+++','класс энергии',4.4),('40 см','глубина',5.5),('16','программ',7.4),('15 мин','быстрая стирка',8.9)]): c+=spec(50,410+i*104,v,l,t)
c+=price(520,1110,'26 750 ₽',11.0)
P.append(page(34.9,c))
# 4 KRAFT
k=hf(5)+head('ЗАПАСЫ НА ЗИМУ','#2a6f97','KRAFT','BD(W)-102QX · морозильный ларь')+blob(20,460,480,'#dfe9f2',0.9)+img('img/kraft102_cut.png',70,500,400,580,1.1)
for i,(v,l,t) in enumerate([('105 л','объём',3.3),('6 кг','заморозка в сутки',4.3),('54 см','ширина — встанет в кладовку',6.6),('40 дБ','тихая работа',7.4)]): k+=spec(500,420+i*108,v,l,t)
k+='<div class="a quote" style="left:500px;top:880px;width:400px" data-t="7.8" data-a="fade">«Ягоды, мясо и заготовки — всё под рукой»</div>'+price(500,1100,'18 990 ₽',8.7)
P.append(page(49.4,k))
# 5 шкафы
w=hf(6)+head('ДЛЯ ПОРЯДКА · ИМПЕРИАЛ','#8a6a4a','ШКАФЫ','мебель фабрики «Империал»')+blob(40,470,420,'#ece4da',0.9)+blob(500,470,400,'#e6e9ee',1.0)
w+=img('img/fenix1b_cut.png',70,400,360,620,3.4)+img('img/inter_cut.png',610,400,206,620,9.2)
w+=('<div class="a" style="left:50px;top:1035px;font:800 44px Unb;color:#141414" data-t="3.6" data-a="fade">ФЕНИКС-1</div><div class="a" style="left:50px;top:1092px;font:500 26px Man;color:#6b645c" data-t="5.4" data-a="fade">бетон · 3 двери · 120 × 220 см</div>'
    '<div class="a" style="left:500px;top:1035px;font:800 44px Unb;color:#141414" data-t="9.4" data-a="fade">ИНТЕР</div><div class="a" style="left:500px;top:1092px;font:500 26px Man;color:#6b645c" data-t="11.8" data-a="fade">узкий, 56 см · для прихожей</div>')
w+=price(50,1135,'22 200 ₽',7.4,44)+price(500,1135,'8 320 ₽',13.9,44)
P.append(page(61.4,w))
# 6 задняя обложка
b=('<div class="a mask" style="left:0;width:940px;text-align:center;top:230px;font:800 120px Unb;color:#fff;letter-spacing:-2px" data-t="0.6" data-a="rise"><span>ЖДЁМ ВАС</span></div>'
   '<div class="a" style="left:320px;top:420px;width:300px;height:250px;background:#fff;border-radius:40px;box-shadow:0 20px 40px rgba(0,0,0,.25)" data-t="1.0" data-a="pop"><img src="img/logo_full.png" style="position:absolute;left:30px;top:20px;width:240px"></div>'
   '<div class="a mask" style="left:0;width:940px;text-align:center;top:760px;font:800 68px Unb;color:#fff" data-t="1.6" data-a="rise"><span>ул. Торговая, 3</span></div>'
   '<div class="a" style="left:110px;top:900px;width:720px;height:150px;border-radius:75px;background:#fff;color:#141414;display:flex;align-items:center;justify-content:center;font:800 66px Unb" data-t="2.9" data-a="pop">(35366) 2-18-16</div>'
   '<div class="a" style="left:0;width:940px;text-align:center;top:1120px;font:800 30px Man;color:#ffd9d6;letter-spacing:4px" data-t="5.6" data-a="fade">СЛЕДУЮЩИЙ ВЫПУСК — СКОРО</div>')
P.append(page(78.1,b,'background:#e30613'))
src=open(sys.argv[1]).read().replace('<!-- PAGES -->',''.join(P))
open(sys.argv[2],'w').write(src)
