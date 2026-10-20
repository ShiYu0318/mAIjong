/**
 * Synthesised sound effects (Web Audio, no asset files). Every interaction gets a short,
 * tactile cue; big moments (calls, wins, level-ups) get louder, longer ones.
 */
import { create } from "zustand";

const MUTE_KEY = "maijong.muted";

interface SoundState {
  muted: boolean;
  setMuted: (m: boolean) => void;
  load: () => void;
}

export const useSound = create<SoundState>((set) => ({
  muted: false,
  setMuted: (muted) => {
    try {
      localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
    } catch {
      /* private mode */
    }
    set({ muted });
  },
  load: () => {
    try {
      set({ muted: localStorage.getItem(MUTE_KEY) === "1" });
    } catch {
      /* ignore */
    }
  },
}));

let ctx: AudioContext | null = null;
let noiseBuf: AudioBuffer | null = null;

function audio(): AudioContext | null {
  if (typeof window === "undefined" || useSound.getState().muted) return null;
  // browsers refuse to start audio before the first click or key press on the page (and
  // warn about it); stay silent until then instead of creating a blocked context
  const activation = (navigator as Navigator & { userActivation?: { hasBeenActive: boolean } })
    .userActivation;
  if (activation && !activation.hasBeenActive && !ctx) return null;
  try {
    ctx ??= new AudioContext();
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch {
    return null;
  }
}

function noise(ac: AudioContext): AudioBuffer {
  if (!noiseBuf) {
    noiseBuf = ac.createBuffer(1, ac.sampleRate * 0.3, ac.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  }
  return noiseBuf;
}

function tone(freq: number, dur: number, opts: {
  type?: OscillatorType; gain?: number; at?: number; slide?: number;
} = {}) {
  const ac = audio();
  if (!ac) return;
  const t = ac.currentTime + (opts.at ?? 0);
  const osc = ac.createOscillator();
  const g = ac.createGain();
  osc.type = opts.type ?? "sine";
  osc.frequency.setValueAtTime(freq, t);
  if (opts.slide) osc.frequency.exponentialRampToValueAtTime(opts.slide, t + dur);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(opts.gain ?? 0.2, t + 0.008);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  osc.connect(g).connect(ac.destination);
  osc.start(t);
  osc.stop(t + dur + 0.02);
}

/** Short filtered noise burst: the "clack" of a tile. */
function clack(freq: number, dur: number, gain: number, at = 0) {
  const ac = audio();
  if (!ac) return;
  const t = ac.currentTime + at;
  const src = ac.createBufferSource();
  src.buffer = noise(ac);
  const bp = ac.createBiquadFilter();
  bp.type = "bandpass";
  bp.frequency.value = freq;
  bp.Q.value = 6;
  const g = ac.createGain();
  g.gain.setValueAtTime(gain, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  src.connect(bp).connect(g).connect(ac.destination);
  src.start(t);
  src.stop(t + dur + 0.02);
}

export const sfx = {
  tap: () => tone(660, 0.07, { type: "triangle", gain: 0.12 }),
  select: () => { clack(2400, 0.05, 0.35); tone(880, 0.06, { type: "triangle", gain: 0.06 }); },
  draw: () => clack(1800, 0.06, 0.25),
  discard: () => { clack(1300, 0.09, 0.9); clack(700, 0.12, 0.5, 0.01); },
  call: () => {
    tone(392, 0.12, { type: "square", gain: 0.08 });
    tone(587, 0.18, { type: "square", gain: 0.08, at: 0.08 });
    clack(1100, 0.1, 0.8, 0.05);
  },
  ting: () => [523, 659, 784].forEach((f, i) => tone(f, 0.18, { type: "triangle", gain: 0.12, at: i * 0.07 })),
  win: () => {
    [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.25, { type: "square", gain: 0.09, at: i * 0.09 }));
    tone(1047, 0.7, { type: "triangle", gain: 0.12, at: 0.38 });
    tone(1319, 0.7, { type: "triangle", gain: 0.08, at: 0.38 });
  },
  lose: () => [392, 330, 262].forEach((f, i) => tone(f, 0.22, { type: "triangle", gain: 0.1, at: i * 0.12 })),
  coin: () => { tone(1568, 0.08, { type: "square", gain: 0.06 }); tone(2093, 0.18, { type: "square", gain: 0.06, at: 0.07 }); },
  levelUp: () => [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, 0.2, { type: "triangle", gain: 0.12, at: i * 0.08 })),
  tick: () => tone(1200, 0.04, { type: "sine", gain: 0.08 }),
  error: () => tone(180, 0.18, { type: "sawtooth", gain: 0.08, slide: 120 }),
  whoosh: () => clack(600, 0.25, 0.4),
};
