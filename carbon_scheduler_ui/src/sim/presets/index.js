import quickbite from './quickbite';
import ledgerlite from './ledgerlite';
import meridianbank from './meridianbank';

export const PRESETS = [quickbite, ledgerlite, meridianbank];

export function findPreset(id) {
  return PRESETS.find((p) => p.id === id) || PRESETS[0];
}
