import sounddevice as sd
import numpy as np
import monome
import asyncio

# Parameters
frequency = 440  # Base frequency in Hz (A4 note)
sample_rate = 44100  # Sampling rate in Hz
bitmap_size = 8  # Monome grid size
internal_resolution = 32  # For smooth interpolation
speed = 0.02  # Frame update speed in seconds
amplitude = 1  # Amplitude of the wave
phase_increment = 0.1  # Base speed of phase change
brightness_factor = 15  # Scale brightness to Monome (0–15)
sound_duration = 0.1  # Duration of each tone in seconds
pitch_variation_factor = 0.02  # Smooth pitch variation factor

class AliveWaveGridApp(monome.GridApp):
    def __init__(self, wave_func=np.sin):
        super().__init__()
        self.phase = 0
        self.wave_func = wave_func
        self.connected = False
        self.prev_brightness = 0  # Store previous brightness for smooth pitch changes

    def generate_bitmap(self, phase):
        """Generate a smooth bitmap for the Monome Grid."""
        # Use a high-resolution grid internally for smooth interpolation
        x = np.linspace(0, bitmap_size, internal_resolution, endpoint=False)
        wave = amplitude * self.wave_func(2 * np.pi * (x / bitmap_size) + phase)
        wave_scaled = np.interp(wave, (-1, 1), (0, bitmap_size - 1))  # Scale to Monome's grid
        brightness = np.interp(np.abs(wave), (0, 1), (1, brightness_factor))  # Smooth brightness

        # Convert to bitmap
        bitmap = np.zeros((bitmap_size, bitmap_size), dtype=int)
        for col in range(bitmap_size):
            # Find interpolated position for this column
            col_x = np.interp(col, np.arange(bitmap_size), np.linspace(0, internal_resolution - 1, bitmap_size))
            row = int(np.round(wave_scaled[int(col_x)]))
            bitmap[row, col] = int(brightness[int(col_x)])
        return bitmap

    async def play_sound(self, brightness):
        """Play a smooth, organic sound with pitch modulation."""
        # Smooth pitch glide
        pitch = frequency + (brightness * pitch_variation_factor)
        t = np.linspace(0, sound_duration, int(sample_rate * sound_duration), False)

        # Generate smooth sound wave with slight frequency variation
        sound_wave = 0.5 * np.sin(2 * np.pi * pitch * t)

        # Apply a simple envelope (Attack, Decay, Sustain, Release)
        envelope = np.concatenate([
            np.linspace(0, 1, int(sample_rate * 0.02)),  # Attack
            np.linspace(1, 0.8, int(sample_rate * 0.05)),  # Decay
            np.ones(int(sample_rate * (sound_duration - 0.07))),  # Sustain
            np.linspace(0.8, 0, int(sample_rate * 0.02))  # Release
        ])

        # Apply the envelope to the sound wave
        sound_wave *= envelope[:len(sound_wave)]

        # Play the sound
        sd.play(sound_wave, samplerate=sample_rate)
        sd.wait()  # Wait until the sound finishes

    async def display_bitmap(self, bitmap):
        """Send the bitmap to the Monome Grid."""
        self.grid.led_all(0)  # Clear the grid
        for row_idx, row in enumerate(bitmap):
            for col_idx, col in enumerate(row):
                # Convert NumPy integers to native Python integers
                self.grid.led_set(int(col_idx), int(row_idx), int(col))               

    async def start_animation(self):
        """Run the smooth animation loop."""
        self.connected = True
        while self.connected:
            # Generate the next frame
            bitmap = self.generate_bitmap(self.phase)

            # Display the frame
            await self.display_bitmap(bitmap)

            # Get the maximum brightness from the middle row to modulate the sound
            middle_row_brightness = bitmap[bitmap_size // 2].max()

            # If brightness changes, play a new sound smoothly
            if abs(self.prev_brightness - middle_row_brightness) > 0.1:
                #await self.play_sound(middle_row_brightness)
                self.prev_brightness = middle_row_brightness                

            # Smoothly change parameters for organic movement
            self.phase += phase_increment + 0.05 * np.sin(self.phase)
            await asyncio.sleep(speed)

    def stop_animation(self):
        """Stop the animation loop."""
        self.connected = False

async def main():
    loop = asyncio.get_event_loop()

    grid_app = AliveWaveGridApp()

    def serialosc_device_added(id, type, port):
        print(f"Connecting to {id} ({type})")
        asyncio.ensure_future(grid_app.grid.connect('127.0.0.1', port))

    def grid_ready():
        """Start animation when the grid is ready."""
        print("Grid connected. Starting animation...")
        asyncio.ensure_future(grid_app.start_animation())

    grid_app.grid.ready_event.add_handler(grid_ready)

    serialosc = monome.SerialOsc()
    serialosc.device_added_event.add_handler(serialosc_device_added)

    await serialosc.connect()
    await loop.create_future()

if __name__ == '__main__':
    asyncio.run(main())
