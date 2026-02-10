import { STORAGE_KEYS } from "../config";

export const getStored = (key) => window.localStorage.getItem(key);

export const setStored = (key, value) => window.localStorage.setItem(key, value);

export const removeStored = (key) => window.localStorage.removeItem(key);

export const clearStoredGameState = () => {
  removeStored(STORAGE_KEYS.gameUid);
  removeStored(STORAGE_KEYS.helpSeen);
};

export const generateUid = () => {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `uid-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};
