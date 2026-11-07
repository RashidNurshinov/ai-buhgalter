# python3 mix.py music.mp3 voice.wav <длительность> out.wav
# Сведение: музыка зациклена (acrossfade), под голосом ровно приглушена.
# Паузы между фразами короче 2,4 с НЕ отпускают приглушение — иначе музыка «вскакивает»
# на 0,3–0,6 с, и на стыках сцен слышно шипение/«вжух» (так было с sidechaincompress).
import sys, subprocess, numpy as np
music, voice, DUR, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
SR = 48000
def load(args):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', *args, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()
n = int(DUR * SR)
loops = int(DUR // 28) + 2
fc = ';'.join([f'[0:a][1:a]acrossfade=d=1.5[a1]'] + [f'[a{i}][{i+1}:a]acrossfade=d=1.5[a{i+1}]' for i in range(1, loops - 1)])
m = load(sum([['-i', music] for _ in range(loops)], []) + ['-filter_complex', fc, '-map', f'[a{loops-1}]'])[:n]
v = load(['-i', voice])[:n]
m = np.pad(m, (0, n - len(m))); v = np.pad(v, (0, n - len(v)))
# огибающая считается на сетке 100 Гц (быстро), потом растягивается на сэмплы
E = 100; hop = SR // E; ne = n // hop
rms = np.sqrt((v[:ne * hop] ** 2).reshape(ne, hop).mean(axis=1))
act = (rms > 10 ** (-45 / 20)).astype(np.float32)
hold = int(1.2 * E)  # удержание 1,2 с в обе стороны → щели до 2,4 с заполняются
act = (np.convolve(act, np.ones(2 * hold + 1), 'same') > 0).astype(np.float32)
target = np.where(act > 0, 0.30, 1.0).astype(np.float32)
k = int(0.35 * E); ker = np.hanning(2 * k + 1); ker /= ker.sum()  # плавность 0,35 с
ge = np.convolve(np.pad(target, (k, k), mode='edge'), ker, 'valid')
g = np.interp(np.arange(n) / hop, np.arange(len(ge)), ge).astype(np.float32)
fade = np.ones(n, np.float32); f = int(2.5 * SR); fade[-f:] = np.linspace(1, 0, f)
mix = m * 0.8 * g * fade + v * 1.6
peak = np.abs(mix).max()
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-af', 'alimiter=limit=0.95:attack=5:release=80', out], input=mix.astype(np.float32).tobytes(), check=True)
print('ok', out, f'peak {peak:.2f}')
