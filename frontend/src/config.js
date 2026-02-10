const env = import.meta.env ?? {};

export const API_BASE =
  env.VITE_API_BASE_URL ||
  (env.DEV ? "http://localhost:5000/api" : "/api");

export const LETTER_STATUS = {
  correct: "correct",
  present: "present",
  absent: "absent"
};

export const DEFAULT_KEYBOARD = [
  "QWERTYUIOP".split(""),
  "ASDFGHJKL".split(""),
  ["ENTER", ..."ZXCVBNM".split(""), "⌫"]
];

export const STATUS_PRIORITY = {
  [LETTER_STATUS.correct]: 3,
  [LETTER_STATUS.present]: 2,
  [LETTER_STATUS.absent]: 1
};

export const STORAGE_KEYS = {
  uid: "wordly_uid",
  gameUid: "wordly_game_uid",
  helpSeen: "wordly_help_seen",
  playerName: "wordly_name"
};
