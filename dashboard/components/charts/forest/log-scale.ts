export function logScale(
  value: number,
  min: number,
  max: number,
  width: number
): number {
  const logMin = Math.log10(Math.max(min, 0.001));
  const logMax = Math.log10(max);
  const clamped = Math.max(Math.min(value, max), min);
  const logV = Math.log10(clamped);
  return ((logV - logMin) / (logMax - logMin)) * width;
}

export function logTicks(min: number, max: number): number[] {
  const ticks: number[] = [];
  let v = min;
  while (v <= max) {
    ticks.push(v);
    v *= 10;
  }
  return ticks;
}
