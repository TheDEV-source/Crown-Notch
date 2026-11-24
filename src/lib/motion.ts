// Spring physics shared by every morph in the notch shell (per spec:
// stiffness 380 / damping 28 / mass 0.8).
export const SPRING = {
  type: "spring",
  stiffness: 380,
  damping: 28,
  mass: 0.8,
} as const;

// Sizes (logical px) of the three notch states.
export const SIZES = {
  idle: { w: 180, h: 32 },
  peek: { w: 260, h: 44 },
  expanded: { w: 420, h: 190 },
} as const;

export type NotchState = keyof typeof SIZES;
