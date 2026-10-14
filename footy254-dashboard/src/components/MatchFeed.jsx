import { useEffect, useState } from "react";

import { getUpcomingFixtures } from "../services";

import MatchCard from "./MatchCard";

export default function MatchFeed() {

  const [matches, setMatches] = useState([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  useEffect(() => {

    async function loadMatches() {

      try {

      const data = await getUpcomingFixtures();

      setMatches(data.fixtures || []);

      }

      catch (err) {

        console.error(err);

        setError(
          "Unable to load fixtures."
        );

      }

      finally {

        setLoading(false);

      }

    }

    loadMatches();

  }, []);

  if (loading) {

    return (

      <div className="rounded-2xl border border-white/10 bg-pitch p-6 text-center text-slate-400">

        Loading upcoming fixtures...

      </div>

    );

  }

  if (error) {

    return (

      <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-6 text-center text-red-300">

        {error}

      </div>

    );

  }

  if (!matches.length) {

    return (

      <div className="rounded-2xl border border-white/10 bg-pitch p-6 text-center text-slate-400">

        No upcoming fixtures available.

      </div>

    );

  }

  return (

    <div className="space-y-4">

      {

        matches.map(match => (

          <MatchCard

            key={match.match_id}

            match={match}

          />

        ))

      }

    </div>

  );

}