// ======================================================
// BET SLIP CONTEXT
// ======================================================
//
// Holds the selections the user has picked on the odds board before they
// place the bet. Purely client-side state (nothing hits the backend until
// "Place bet") - mirrors how AuthContext holds session state.
//
// A leg is: { matchId, selection, homeTeam, awayTeam, competition, odds }

import { createContext, useContext, useMemo, useState } from "react";
import { placeSingleBet, placeMultiBet } from "../services/betting";

const BetSlipContext = createContext(null);

const STORAGE_KEY = "footy254:bet-slip";

function loadInitialLegs() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persist(legs) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(legs));
  } catch {
    // Private mode / storage disabled - the slip just won't survive a reload.
  }
}

export function BetSlipProvider({ children }) {
  const [legs, setLegs] = useState(loadInitialLegs);
  const [stake, setStake] = useState("100");
  const [open, setOpen] = useState(false);
  const [placing, setPlacing] = useState(false);
  const [lastSlip, setLastSlip] = useState(null);
  const [error, setError] = useState("");

  function addLeg(leg) {
    setError("");
    setLegs((prev) => {
      const withoutSameMatch = prev.filter((l) => l.matchId !== leg.matchId);
      const already = prev.find(
        (l) => l.matchId === leg.matchId && l.selection === leg.selection
      );
      // Clicking the same selection again removes it (toggle); clicking a
      // different outcome on a match already in the slip replaces that leg -
      // a slip can only hold one outcome per fixture.
      const next = already ? withoutSameMatch : [...withoutSameMatch, leg];
      persist(next);
      return next;
    });
    setOpen(true);
  }

  function removeLeg(matchId) {
    setLegs((prev) => {
      const next = prev.filter((l) => l.matchId !== matchId);
      persist(next);
      return next;
    });
  }

  function clearSlip() {
    setLegs([]);
    persist([]);
    setLastSlip(null);
    setError("");
  }

  const isSelected = (matchId, selection) =>
    legs.some((l) => l.matchId === matchId && l.selection === selection);

  const combinedOdds = useMemo(
    () => legs.reduce((acc, l) => acc * (Number(l.odds) || 1), 1),
    [legs]
  );

  const potentialPayout = useMemo(() => {
    const s = Number(stake) || 0;
    if (legs.length === 0) return 0;
    const odds = legs.length === 1 ? Number(legs[0].odds) || 0 : combinedOdds;
    return +(s * odds).toFixed(2);
  }, [legs, stake, combinedOdds]);

  async function placeBet() {
    setError("");
    if (legs.length === 0) return;
    const s = Number(stake);
    if (!s || s <= 0) {
      setError("Enter a stake greater than zero.");
      return;
    }

    setPlacing(true);
    try {
      let slip;
      if (legs.length === 1) {
        slip = await placeSingleBet({
          matchId: legs[0].matchId,
          selection: legs[0].selection,
          stake: s,
        });
      } else {
        slip = await placeMultiBet({
          legs: legs.map((l) => ({ matchId: l.matchId, selection: l.selection })),
          stake: s,
        });
      }
      setLastSlip(slip);
      setLegs([]);
      persist([]);
      return slip;
    } catch (err) {
      setError(err?.message || "Could not place bet. Please try again.");
      throw err;
    } finally {
      setPlacing(false);
    }
  }

  const value = {
    legs,
    addLeg,
    removeLeg,
    clearSlip,
    isSelected,
    stake,
    setStake,
    combinedOdds,
    potentialPayout,
    open,
    setOpen,
    placing,
    placeBet,
    lastSlip,
    setLastSlip,
    error,
    setError,
  };

  return <BetSlipContext.Provider value={value}>{children}</BetSlipContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useBetSlip() {
  return useContext(BetSlipContext);
}
