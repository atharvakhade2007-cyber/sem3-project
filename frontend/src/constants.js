// Shared constants matching the backend's UserProfile.Avatar / GKTier choices.

export const AVATARS = [
  { key: 'owl', emoji: '🦉', label: 'Wise Owl' },
  { key: 'rocket', emoji: '🚀', label: 'Rocket' },
  { key: 'brain', emoji: '🧠', label: 'Brainiac' },
  { key: 'books', emoji: '📚', label: 'Bookworm' },
  { key: 'bolt', emoji: '⚡', label: 'Speedster' },
  { key: 'target', emoji: '🎯', label: 'Sharpshooter' },
  { key: 'wave', emoji: '🌊', label: 'Deep Thinker' },
  { key: 'fire', emoji: '🔥', label: 'Streak Master' },
];

export const TIER_LABELS = {
  easy: 'Beginner',
  medium: 'Intermediate',
  hard: 'Advanced',
};

export const LEVEL_LABELS = {
  easy: 'Lvl 2 Apprentice',
  medium: 'Lvl 4 Scholar',
  hard: 'Lvl 7 Master',
};

export function levelLabel(tier) {
  return LEVEL_LABELS[tier] || 'Lvl 4 Scholar';
}

// User level bands on the 0-based Elo scale (new users start at 0).
export const ELO_LEVELS = [
  { min: 0, label: 'Beginner', color: '#10b981' },
  { min: 200, label: 'Intermediate', color: '#f59e0b' },
  { min: 500, label: 'Advanced', color: '#f97316' },
  { min: 900, label: 'Expert', color: '#ef4444' },
];

export function eloLevel(elo) {
  const n = Number(elo) || 0;
  let level = ELO_LEVELS[0];
  ELO_LEVELS.forEach(l => { if (n >= l.min) level = l; });
  return level;
}

export function eloLevelName(elo) {
  return eloLevel(elo).label;
}

export function avatarEmoji(key) {
  return AVATARS.find(a => a.key === key)?.emoji || '🦉';
}