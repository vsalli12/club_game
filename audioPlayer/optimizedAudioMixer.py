import numpy as np
import soundfile as sf  # pip install soundfile
from collections import deque
import pyaudio
import numpy as np
import threading
from queue import Queue
import wave
from scipy import signal

class AudioSource:
    def __init__(self, audio_data, sample_rate, mixer_sample_rate):
        self.data = self._resample_if_needed(audio_data, sample_rate, mixer_sample_rate)
        self.position = 0
        self.volume = 1.0
        self.pan = 0.0  # -1.0 = left, 1.0 = right
        self.active = True
        self.loop = False
        self.reverb_processor = None
        self.wet_level = 0.0  # 0.0 = dry, 1.0 = full reverb
        
        # Distance filtering
        self.sample_rate = mixer_sample_rate
        self.distance = 0.0
        self.max_distance = 1000.0
        self.cutoff_freq = mixer_sample_rate // 2  # No filtering initially
        self.filter_b = None
        self.filter_a = None
        self.filter_state = None
        
    def _resample_if_needed(self, data, original_rate, target_rate):
        if original_rate != target_rate:
            # Simple resampling (use scipy.signal.resample for better quality)
            ratio = target_rate / original_rate
            new_length = int(len(data) * ratio)
            return np.interp(np.linspace(0, len(data), new_length), np.arange(len(data)), data)
        return data
    def _setup_distance_filter(self):
        """Create lowpass filter based on distance"""
        if self.cutoff_freq >= self.sample_rate // 2 - 100:  # Leave some headroom
            self.filter_b = None  # No filtering
            self.filter_a = None
            self.filter_state = None
        else:
            nyquist = self.sample_rate / 2
            normalized_cutoff = min(0.99, self.cutoff_freq / nyquist)
            self.filter_b, self.filter_a = signal.butter(2, normalized_cutoff, btype='low')
            # Initialize filter state for stereo
            zi = signal.lfilter_zi(self.filter_b, self.filter_a)
            self.filter_state = np.array([zi, zi])  # One state per channel
    
    def set_distance(self, distance, max_distance=1000.0):
        """Set distance for both volume calculation and filtering"""
        old_cutoff = getattr(self, 'cutoff_freq', self.sample_rate // 2)
        self.distance = distance
        self.max_distance = max_distance
        
        # Linear cutoff frequency reduction based on distance
        if distance > 0:
            # Map distance linearly: 0 distance = 20kHz, max_distance = 1kHz
            min_cutoff = 100   # Minimum cutoff frequency (1kHz)
            max_cutoff = 20000  # Maximum cutoff frequency (20kHz)
            
            # Linear interpolation
            distance_ratio = min((distance / (max_distance)) ** 0.2, 1.0)
            self.cutoff_freq = int(max_cutoff - (max_cutoff - min_cutoff) * distance_ratio)
        else:
            self.cutoff_freq = self.sample_rate // 2  # No filtering for zero distance
        
        # Only update filter if cutoff changed significantly (avoid audio glitches)
        if abs(old_cutoff - self.cutoff_freq) > 500:
            self._setup_distance_filter()
    
    def _apply_distance_filter(self, chunk):
        """Apply distance-based lowpass filter"""
        if self.filter_b is None or self.filter_state is None:
            return chunk
        
        filtered_chunk = np.zeros_like(chunk)
        
        # Apply filter to each channel
        for ch in range(chunk.shape[1]):
            filtered_chunk[:, ch], self.filter_state[ch] = signal.lfilter(
                self.filter_b, self.filter_a, chunk[:, ch], 
                zi=self.filter_state[ch]
            )
        
        return filtered_chunk
        self.reverb_processor = reverb_processor
        self.wet_level = wet_level
    
    def set_reverb(self, reverb_processor, wet_level=0.3):
        self.reverb_processor = reverb_processor
        self.wet_level = wet_level
    
    def get_next_chunk(self, frame_count):
        if self.position >= len(self.data):
            if self.loop:
                self.position = 0
            else:
                self.active = False
                return np.zeros((frame_count, 2), dtype=np.float32)
                
        end_pos = min(self.position + frame_count, len(self.data))
        chunk = self.data[self.position:end_pos]
        
        # Convert mono to stereo if needed
        if len(chunk.shape) == 1:
            chunk = np.column_stack([chunk, chunk])
        
        # Pad if chunk is shorter than requested
        if len(chunk) < frame_count:
            padding = np.zeros((frame_count - len(chunk), 2))
            chunk = np.vstack([chunk, padding])

        # Apply distance-based filtering BEFORE reverb
        chunk = self._apply_distance_filter(chunk)

        # Apply reverb if enabled
        if self.reverb_processor and self.wet_level > 0:
            dry_signal = chunk * (1.0 - self.wet_level)
            wet_signal = self.reverb_processor.process_chunk(chunk) * self.wet_level
            chunk = dry_signal + wet_signal
            
        self.position = end_pos
        return chunk.astype(np.float32)
        
    def get_stereo_pan(self):
        # Convert pan (-1 to 1) to left/right gains
        left_gain = (1.0 - max(0, self.pan)) * np.sqrt(2) / 2
        right_gain = (1.0 + min(0, self.pan)) * np.sqrt(2) / 2
        return np.array([[left_gain, right_gain]])


class AudioMixer:
    def __init__(self, sample_rate=44100, chunk_size=1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio_sources = []
        self.output_stream = None
        self.cachedAudio = {}
        self.max_distance = 2000
        
    def load_audio(self, filename):
        if filename in self.cachedAudio:
            data, sample_rate = self.cachedAudio[filename]
        else:
            data, sample_rate = sf.read(filename, dtype=np.float32)
            self.cachedAudio[filename] = [data, sample_rate]

        source = AudioSource(data, sample_rate, self.sample_rate)
        return source
        
    def play_audio(self, source):
        source.active = True
        source.position = 0
        self.audio_sources.append(source)
        
    def load_and_play(self, filename, volume=1.0, pan=0.0, loop=False):
        source = self.load_audio(filename)
        source.volume = volume
        source.pan = pan
        source.loop = loop
        self.play_audio(source)
        return source  # Return for later manipulation
    
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

    def auto_gain(self, signal, target_level=0.7):
        peak = np.max(np.abs(signal))
        if peak > target_level:
            return signal * (target_level / peak)
        return signal
        
    def _audio_callback(self, in_data, frame_count, time_info, status):
        # Mix all active audio sources
        mixed = np.zeros((frame_count, 2), dtype=np.float32)
        
        # Filter out inactive sources
        active_sources = []
        for source in self.audio_sources:
            if source.active:
                chunk = source.get_next_chunk(frame_count)
                mixed += chunk * source.volume * source.get_stereo_pan()
                active_sources.append(source)
        
        # Update sources list to remove inactive ones
        self.audio_sources = active_sources

        mixed = self.auto_gain(mixed)
                
        return (mixed.tobytes(), pyaudio.paContinue)
    
    def stop_stream(self):
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()

def calculate_distance_volume(distance, max_distance, power=2.0):
    """
    Calculate volume based on distance with non-linear falloff
    
    Args:
        distance: Distance from listener to source
        max_distance: Maximum audible distance
        power: Falloff power (higher = faster dropoff at distance)
    
    Returns:
        Volume multiplier (0.0 to 1.0)
    """
    if distance <= 0:
        return 1.0
    
    # Normalize distance (0 to 1)
    normalized_distance = min(distance / max_distance, 1.0)
    
    # Apply power curve (inverted so close sounds are loud)
    volume = (1.0 - normalized_distance) ** power
    
    return max(0.0, volume)

def playPositionalAudio(mixer, audio, listener_pos, source_pos, max_distance=2000, volume_power=2.0, enable_filtering=True):
    """
    Play audio with 3D positioning, non-linear volume falloff, and distance filtering
    
    Args:
        mixer: AudioMixer instance
        audio: Audio filename or list of filenames
        listener_pos: 2D position of listener (numpy array or list)
        source_pos: 2D position of audio source (numpy array or list)
        max_distance: Maximum audible distance
        volume_power: Power for volume falloff curve (2.0 = quadratic, 3.0 = cubic, etc.)
        enable_filtering: Whether to apply distance-based lowpass filtering
    """
    if not isinstance(audio, str):
        import random
        audio = random.choice(audio)
    
    # Convert to numpy arrays if needed
    listener_pos = np.array(listener_pos)
    source_pos = np.array(source_pos)
    
    # Calculate distance and direction
    delta = source_pos - listener_pos
    distance = np.linalg.norm(delta)
    
    # Calculate non-linear volume falloff
    volume = calculate_distance_volume(distance, max_distance, volume_power)
    
    # Calculate panning based on horizontal position
    if distance > 0:
        # Normalize panning to [-1, 1] range
        max_pan_distance = max_distance * 0.5  # Sounds beyond this distance have full pan
        panning = np.clip(delta[0] / max_pan_distance, -1.0, 1.0)
    else:
        panning = 0.0
    
    # Load and play audio
    sound = mixer.load_and_play(audio, volume=volume, pan=panning)
    
    # Apply distance-based filtering if enabled
    if enable_filtering:
        sound.set_distance(distance, mixer.max_distance)
    
    return sound

# Benchmarking functions
import time
import pygame
import pyaudio

def benchmark_pygame_audio(num_sounds, duration=5.0):
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    sounds = [pygame.mixer.Sound(f"test{i}.wav") for i in range(min(8, num_sounds))]
    
    start = time.perf_counter()
    for sound in sounds:
        sound.play(-1)  # Loop
    
    time.sleep(duration)
    pygame.mixer.quit()
    return time.perf_counter() - start

def benchmark_custom_mixer(num_sounds, duration=5.0):
    mixer = AudioMixer()
    sources = [mixer.load_audio(f"test{i}.wav") for i in range(num_sounds)]
    
    start = time.perf_counter()
    mixer.start_stream()
    for source in sources:
        source.loop = True
        mixer.play_audio(source)
    
    time.sleep(duration)
    mixer.stop_stream()
    return time.perf_counter() - start

# Test script
if __name__ == "__main__":
    mixer = AudioMixer()
    mixer.start_stream()
    print("Mixer initialized")

    import random
    
    # Test non-linear volume falloff with different power curves
    print("Testing volume falloff curves:")
    
    print("Testing distance-based filtering:")
    
    # Test different distances with filtering
    for distance in [0, 500, 1000, 1500, 2000]:
        volume = calculate_distance_volume(distance, 2000, power=2.0)
        # Calculate what the cutoff frequency would be
        max_cutoff = 20000
        min_cutoff = 1000
        distance_ratio = min(distance / 1000, 1.0)
        cutoff = int(max_cutoff - (max_cutoff - min_cutoff) * distance_ratio)
        print(f"Distance: {distance:4d} -> Volume: {volume:.3f}, Cutoff: {cutoff:5d}Hz")
    
    print("\nPlaying sounds at different distances with filtering:")
    
    # Play sounds at various distances
    listener_pos = np.array([0, 0])
    
    for distance in range(0, 2000, 100):
        # Test specific distances to hear filtering effect
        
        #distance = distances[i]
        
        # Place sound to the side so panning is noticeable
        source_pos = listener_pos + np.array([distance, 0])
        
        sound = playPositionalAudio(
            mixer, "audio/shotgun1.wav", 
            listener_pos, source_pos, 
            max_distance=2000, 
            volume_power=2.0,
            enable_filtering=True
        )
        
        print(f"Playing sound at distance {distance:4d} -> Volume: {sound.volume:.3f}, Cutoff: {sound.cutoff_freq:5d}Hz")
        time.sleep(2)
    
    time.sleep(5)
    mixer.stop_stream()