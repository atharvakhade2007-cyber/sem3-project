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

export function avatarEmoji(key) {
  return AVATARS.find(a => a.key === key)?.emoji || '🦉';
}