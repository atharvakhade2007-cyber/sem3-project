import { createContext, useCallback, useContext, useState } from 'react';
import SocialHub from '../components/SocialHub';
import ChallengeCreateModal from '../components/ChallengeCreateModal';

const UiContext = createContext(null);

/**
 * Global modal orchestration for the social layer:
 *  - SocialHub (Friends / Requests / Find Users / Duels)
 *  - ChallengeCreateModal (pick a source session OR pick a friend)
 */
export function UiProvider({ children }) {
  const [socialOpen, setSocialOpen] = useState(false);
  const [socialTab, setSocialTab] = useState('duels');
  const [challengeSpec, setChallengeSpec] = useState(null); // {friend} | {session}

  const openSocial = useCallback((tab = 'duels') => {
    setSocialTab(tab);
    setSocialOpen(true);
  }, []);

  const closeSocial = useCallback(() => setSocialOpen(false), []);

  const openChallengeWithFriend = useCallback((friend) => {
    setChallengeSpec({ friend });
  }, []);

  const openChallengeWithSession = useCallback((session) => {
    setChallengeSpec({ session });
  }, []);

  const closeChallenge = useCallback(() => setChallengeSpec(null), []);

  const value = {
    openSocial,
    closeSocial,
    socialOpen,
    socialTab,
    setSocialTab,
    challengeSpec,
    openChallengeWithFriend,
    openChallengeWithSession,
    closeChallenge,
  };

  return (
    <UiContext.Provider value={value}>
      {children}
      <SocialHub />
      <ChallengeCreateModal />
    </UiContext.Provider>
  );
}

export function useUi() {
  const ctx = useContext(UiContext);
  if (!ctx) {
    throw new Error('useUi must be used within a UiProvider');
  }
  return ctx;
}
