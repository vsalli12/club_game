import os
import time
import numpy as np
import soundfile as sf  # pip install soundfile
import pyaudio
from pygame.math import Vector2 as v2
import numba as nb
import random
# -----------------------
# Numba kernels
# -----------------------


def map_cutoff(dist, maxDist):

    tert = maxDist / 3

    if dist < tert:
        return 20000.0
    elif dist < 2*tert:
        # log mapping between 20000 → 100
        t = (dist - tert) / tert
        return 20000.0 * (100.0/20000.0) ** t
    else:
        return 100.0

def map_volume(dist, maxDist):

    return max(0, 1 - (dist/maxDist)**3)

    tert = maxDist / 3
    if dist < tert:
        return 1.0
    elif dist < maxDist:
        t = (dist - tert) / (2*tert)  # normalized [0,1]
        return 1.0 - t**2
    else:
        return 0.0



@nb.njit(fastmath=True)
def get_next_chunk_slowmo(data, position, frame_count, slowmo, loop, prev0, prev1, cutoff, fs):
    N = frame_count
    out = np.zeros((N, 2), dtype=np.float32)
    length = data.shape[0]

    # compute lowpass alpha if needed
    if cutoff is not None and fs is not None:
        omega = np.float32(2.0 * np.pi * cutoff)
        alpha = omega / (omega + np.float32(fs))
    else:
        alpha = np.float32(0.0)

    pos = np.float32(position)

    if loop and pos >= length:
        pos %= length

    slowmo = np.float32(slowmo)

    for i in range(N):
        i0 = int(pos)
        if i0 >= length:
            if loop:
                i0 %= length
            else:
                break
        i1 = i0 + 1
        i1 = i0 + 1
        if i1 >= length:
            if loop:
                i1 = 0
            else:
                i1 = length - 1

        frac = np.float32(pos - i0)

        # linear interpolation
        s0 = data[i0]
        s1 = data[i1]

        

        sample = np.empty(2, dtype=np.float32)
        sample[0] = s0[0] * (1.0 - frac) + s1[0] * frac
        sample[1] = s0[1] * (1.0 - frac) + s1[1] * frac


        # lowpass filter
        if alpha > 0.0:
            prev0 = prev0 + alpha * (sample[0] - prev0)
            prev1 = prev1 + alpha * (sample[1] - prev1)
            sample[0] = prev0
            sample[1] = prev1

        out[i, 0] = sample[0]
        out[i, 1] = sample[1]

        pos += slowmo

        if loop:
            if pos >= length:
                pos -= length


    return out, pos, prev0, prev1




@nb.njit(fastmath=True)
def lowpass_1ch_nb(x, prev, alpha):
    out = np.empty(x.shape[0], dtype=x.dtype)
    y = prev
    for i in range(x.shape[0]):
        y = y + alpha * (x[i] - y)
        out[i] = y
    return out, y

@nb.njit(fastmath=True)
def lowpass_2ch_nb(x, prev0, prev1, alpha):
    out = np.empty((x.shape[0], 2), dtype=x.dtype)
    y0 = prev0
    y1 = prev1
    for i in range(x.shape[0]):
        y0 = y0 + alpha * (x[i, 0] - y0)
        y1 = y1 + alpha * (x[i, 1] - y1)
        out[i, 0] = y0
        out[i, 1] = y1
    return out, y0, y1

@nb.njit(fastmath=True)
def mix_chunk_nb(mixed, chunk, volume, left_gain, right_gain):
    # mixed and chunk are (N,2) float32
    N = chunk.shape[0]
    vlg = volume * left_gain
    vrg = volume * right_gain
    for i in range(N):
        mixed[i, 0] += chunk[i, 0] * vlg
        mixed[i, 1] += chunk[i, 1] * vrg
    return mixed

@nb.njit(fastmath=True)
def auto_gain_nb(signal, target_level):
    # signal is (N,2)
    peak = 0.0
    N = signal.shape[0]
    for i in range(N):
        a0 = signal[i, 0]
        if a0 < 0.0:
            a0 = -a0
        a1 = signal[i, 1]
        if a1 < 0.0:
            a1 = -a1
        if a0 > peak:
            peak = a0
        if a1 > peak:
            peak = a1
    if peak > target_level and peak > 0.0:
        scale = target_level / peak
        for i in range(N):
            signal[i, 0] *= scale
            signal[i, 1] *= scale
    return signal

@nb.njit(fastmath=True)
def resample_1ch_nb(data, new_len):
    out = np.empty(new_len, dtype=data.dtype)
    old_len = data.shape[0]
    if old_len == 0:
        return out
    ratio = (old_len - 1) / (new_len - 1) if new_len > 1 else 1.0
    for i in range(new_len):
        pos = i * ratio
        i0 = int(pos)
        i1 = i0 + 1
        if i1 >= old_len:
            out[i] = data[old_len - 1]
        else:
            frac = pos - i0
            out[i] = data[i0] * (1.0 - frac) + data[i1] * frac
    return out

@nb.njit(fastmath=True)
def resample_2ch_nb(data, new_len):
    out = np.empty((new_len, 2), dtype=data.dtype)
    old_len = data.shape[0]
    if old_len == 0:
        return out
    ratio = (old_len - 1) / (new_len - 1) if new_len > 1 else 1.0
    for i in range(new_len):
        pos = i * ratio
        i0 = int(pos)
        i1 = i0 + 1
        if i1 >= old_len:
            out[i, 0] = data[old_len - 1, 0]
            out[i, 1] = data[old_len - 1, 1]
        else:
            frac = pos - i0
            out[i, 0] = data[i0, 0] * (1.0 - frac) + data[i1, 0] * frac
            out[i, 1] = data[i0, 1] * (1.0 - frac) + data[i1, 1] * frac
    return out

# -----------------------
# AudioSource
# -----------------------

class AudioSource:
    def __init__(self, audio_data, sample_rate, mixer_sample_rate):
        # ensure float32
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        # resample if needed
        self.data = self._resample_if_needed(audio_data, sample_rate, mixer_sample_rate)
        # Guarantee 2D stereo shape (N,2)
        if self.data.ndim == 1:
            self.data = np.column_stack([self.data, self.data]).astype(np.float32)
        elif self.data.ndim == 2 and self.data.shape[1] == 1:
            self.data = np.column_stack([self.data[:,0], self.data[:,0]]).astype(np.float32)
        elif self.data.ndim == 2 and self.data.shape[1] >= 2:
            self.data = self.data[:, :2].astype(np.float32)

        self.length = self.data.shape[0]
        self.position = 0
        self.volume = 1.0
        self.pan = 0.0  # -1.0 = left, 1.0 = right
        self.left_gain = np.float32(np.sqrt(2) / 2)
        self.right_gain = np.float32(np.sqrt(2) / 2)
        self.active = True
        self.loop = False

        self.pitch = random.uniform(0.9, 1.1)

        # Low-pass filter state (stereo)
        self.cutoff = None   # Hz, None = bypass
        self.prev0 = np.float32(0.0)
        self.prev1 = np.float32(0.0)

        # Positional audio support
        self.positional = False      # whether this source is positional
        self.pos = None              # expected to be a pygame.Vector2 or (x,y)
        self.falloff_max_dist = None
        self.base_volume = 1.0       # base volume multiplier applied before distance falloff

        # Optional playback length limiter (seconds)
        self.max_duration = None

    def set_lowpass(self, cutoff_hz):
        self.cutoff = float(cutoff_hz)

    def set_pan(self, pan):
        self.pan = float(np.clip(pan, -1.0, 1.0))
        # convert pan to left/right scalar gains (constant-power-ish)
        self.left_gain = np.float32((1.0 - max(0.0, self.pan)) * np.sqrt(2) / 2.0)
        self.right_gain = np.float32((1.0 + min(0.0, self.pan)) * np.sqrt(2) / 2.0)

    def _resample_if_needed(self, data, original_rate, target_rate):
        if original_rate == target_rate:
            # return a copy to ensure dtype
            return data.astype(np.float32, copy=True)
        ratio = target_rate / original_rate
        new_length = int(round(len(data) * ratio))
        if new_length < 1:
            new_length = 1
        # call appropriate resampler
        if data.ndim == 1:
            data32 = data.astype(np.float32)
            return resample_1ch_nb(data32, new_length)
        else:
            data32 = data.astype(np.float32)
            return resample_2ch_nb(data32, new_length)

    def get_next_chunk(self, frame_count, fs=None, slowmo=0.3):
        chunk, new_pos, self.prev0, self.prev1 = get_next_chunk_slowmo(
            self.data, self.position, frame_count, slowmo * self.pitch, self.loop,
            self.prev0, self.prev1, self.cutoff, fs
        )
        self.position = new_pos

        if not self.loop and self.position >= self.data.shape[0]:
            self.active = False

        if self.loop and self.position >= self.data.shape[0]:
            self.position = 0
        

        return chunk


# -----------------------
# AudioMixer
# -----------------------

class AudioMixer:
    def __init__(self, app, sample_rate=44100, chunk_size=1024):
        self.app = app
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio_sources = []
        self.output_stream = None
        self.cachedAudio = {}

        self.callBackTime = 0
        self.minVolume = 1
        

        # Prime Numba kernels to avoid runtime JIT pause
        dummy_len = max(8, chunk_size)
        dummy_chunk = np.zeros((dummy_len, 2), dtype=np.float32)
        dummy_1ch = np.zeros(dummy_len, dtype=np.float32)
        # lowpass
        _ , _ = lowpass_1ch_nb(dummy_1ch, np.float32(0.0), np.float32(0.5))
        _ , _ , _ = lowpass_2ch_nb(dummy_chunk, np.float32(0.0), np.float32(0.0), np.float32(0.5))
        # mix
        _ = mix_chunk_nb(dummy_chunk.copy(), dummy_chunk, np.float32(1.0), np.float32(1.0), np.float32(1.0))
        # gain
        _ = auto_gain_nb(dummy_chunk.copy(), np.float32(0.7))
        # resample
        _ = resample_1ch_nb(dummy_1ch, 16)
        _ = resample_2ch_nb(dummy_chunk, 16)

    def playPositionalAudio(self, audio, pos = None, volume=1.0, loop = False):
        audioFallOffMaxDist = 6000.0
        if isinstance(audio, str):
            if "waddle" in audio:
                audioFallOffMaxDist *= 0.5
            elif "explosion" in audio:
                audioFallOffMaxDist *= 1.5


        ## HERE, WE CAN PASS self.app to the AudioClips, so they can always calculate the cameraCenter with self.app.deltaCameraPos + self.res/2 as the cameraCenter

        if pos is not None:
            # load source but DO NOT set static volume/pan/filter permanently
            if not isinstance(audio, AudioSource):
                source = self.load_audio(audio)
            else:
                source = audio
            source.positional = True
            source.pos = v2(pos) if not isinstance(pos, v2) else pos
            source.falloff_max_dist = audioFallOffMaxDist
            source.base_volume = volume * self.app.AUDIOVOLUME # your previous scaling: volume * 0.3 (you can pass a param instead)
            source.loop = loop
            source.position = 0
            source.active = True

            # add to mixer list
            self.audio_sources.append(source)
            return source
        else:
            # non-positional: behave as before
            # volume = 1.0
            panning = 0.0
            cutoff = None
            sound = self.load_and_play(audio, volume=volume * 0.3, pan=panning)
            if cutoff is not None:
                sound.set_lowpass(cutoff)
            return sound

    def load_audio(self, filename):
        if filename in self.cachedAudio:
            data, sample_rate = self.cachedAudio[filename]
        else:
            data, sample_rate = sf.read(filename, dtype='float32')
            self.cachedAudio[filename] = [data, sample_rate]
        source = AudioSource(data, sample_rate, self.sample_rate)
        return source
    
    



    def play_audio(self, source):
        source.active = True
        source.position = 0
        self.audio_sources.append(source)

    def load_and_play(self, filename, volume=1.0, pan=0.0, loop=False):
        source = self.load_audio(filename)
        source.volume = float(volume)
        source.set_pan(pan)
        source.loop = bool(loop)
        self.play_audio(source)
        return source
    
    def changeChunkSize(self, newChunkSize):
        self.app.log(f"Changing audio chunk size from {self.chunk_size} to {newChunkSize}")
        self.chunk_size = newChunkSize
        self.output_stream.close()
        self.start_stream()

    def start_stream(self):
        pa = pyaudio.PyAudio()
        self.output_stream = pa.open(
            format=pyaudio.paFloat32,
            channels=2,  # stereo
            rate=self.sample_rate,
            output=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._audio_callback
        )
        # ensure stream is running
        try:
            self.output_stream.start_stream()
        except Exception:
            pass

    def _get_camera_center(self, sourcePos):
        return self.app.camPD + self.app.res / 2


    def _audio_callback(self, in_data, frame_count, time_info, status):

        t = time.perf_counter()

        # mix into this buffer
        mixed = np.zeros((frame_count, 2), dtype=np.float32)

        

        # iterate copy of list to avoid modification during iteration
        sources = list(self.audio_sources)
        self.minVolume = 1
        for source in sources:
            if not source.active:
                try:
                    self.audio_sources.remove(source)
                except ValueError:
                    pass
                continue
            self.minVolume = min(self.minVolume, source.volume)
            # If source is positional, update volume, pan and lowpass each callback
            if getattr(source, "positional", False) and source.pos is not None:
                # compute delta and distance (v2 supports length())
                try:
                    camera_center = self._get_camera_center(source.pos)
                    delta = v2(source.pos) - camera_center
                    dist = float(delta.length())
                except Exception:
                    # if anything fails, fall back to not updating
                    dist = 0.0
                    delta = v2(0, 0)

                maxDist = source.falloff_max_dist if source.falloff_max_dist is not None else 6000.0

                # if out of range, optionally deactivate or skip mixing
                if dist > maxDist and not source.loop:
                    # mark inactive so it will be removed and not consume CPU
                    source.active = False
                    try:
                        self.audio_sources.remove(source)
                    except ValueError:
                        pass
                    continue

                # compute continuous parameters
                vol_fall = map_volume(dist, maxDist)
                panning = float(np.clip(delta.x / 2000.0, -1.0, 1.0))
                cutoff = map_cutoff(dist, maxDist)

                # apply to source for this callback
                source.volume = float(source.base_volume * vol_fall)
                source.set_pan(panning)
                source.set_lowpass(cutoff)

            # get chunk with current per-source parameters
            chunk = source.get_next_chunk(frame_count, fs=self.sample_rate, slowmo=self.app.TOTAL_TIME_ADJUSTMENT)
            # mix into master buffer
            mix_chunk_nb(mixed, chunk, np.float32(source.volume), np.float32(source.left_gain), np.float32(source.right_gain))

        # auto gain (in-place)
        auto_gain_nb(mixed, np.float32(0.7))

        self.callBackTime = 0.01 * (time.perf_counter() - t) + 0.99 * self.callBackTime

        return (mixed.tobytes(), pyaudio.paContinue)

# -----------------------
# Example usage
# -----------------------

def testAudio():

    class testApp:
        def __init__(self):
            self.cameraPosDelta = v2(0,0)
            self.res = v2(1920, 1080)
            self.SLOWMO = 1

        def moveCam(self):
            self.cameraPosDelta.x += 250

    app = testApp()

    mixer = AudioMixer(app)

    mixer.start_stream()
    print("Mixer init")
    import random

    explosion = mixer.playPositionalAudio("audio/explosion1.wav", v2(0,0))
    time.sleep(4)

    explosion = mixer.playPositionalAudio("audio/minigun1.wav", v2(0,0))

    # spawn many explosions quickly to test performance
    for i in range(0, 6000, 300):
        app.moveCam()
        time.sleep(0.1)

    time.sleep(3.0)

def plot_map_volume(maxDist=10.0, n_points=500):
    import matplotlib.pyplot as plt



    x = np.linspace(0, maxDist*1.2, n_points)  # go a bit beyond maxDist
    y = [map_volume(d, maxDist) for d in x]

    plt.figure(figsize=(6,4))
    plt.plot(x, y, label=f"maxDist={maxDist}")
    plt.axvline(maxDist/3, color='gray', linestyle='--', alpha=0.5, label="tert")
    plt.axvline(maxDist, color='red', linestyle='--', alpha=0.5, label="maxDist")
    plt.xlabel("Distance")
    plt.ylabel("Volume")
    plt.title("map_volume function")
    plt.legend()
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    testAudio()
    


    
