export const createEmptyGrid = (rows, cols) =>
  Array.from({ length: rows }, () =>
    Array.from({ length: cols }, () => ({ letter: "", status: "" }))
  );
