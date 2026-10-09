namespace GameClient
{
    public enum Wave { Square, Sine, Sawtooth }

    /// <summary>One layer of an effect: a tone (oscillator) or a noise burst, starting At seconds in.</summary>
    public readonly struct Layer
    {
        public readonly bool Noise;
        public readonly Wave Wave;
        public readonly float Freq, Dur, Vol, SlideTo, At;

        public Layer(bool noise, Wave wave, float freq, float dur, float vol, float slideTo, float at)
        {
            Noise = noise; Wave = wave; Freq = freq; Dur = dur; Vol = vol; SlideTo = slideTo; At = at;
        }

        /// <summary>sound.js tone(freq, dur, { type, vol, slideTo, at }) with the same defaults.</summary>
        public static Layer Tone(float freq, float dur, float vol = 0.15f, Wave wave = Wave.Square, float slideTo = 0, float at = 0) =>
            new Layer(false, wave, freq, dur, vol, slideTo, at);

        /// <summary>sound.js noise(dur, { vol, freq, at }) with the same defaults.</summary>
        public static Layer NoiseBurst(float dur, float vol = 0.3f, float freq = 500, float at = 0) =>
            new Layer(true, Wave.Sine, freq, dur, vol, 0, at);
    }
}
