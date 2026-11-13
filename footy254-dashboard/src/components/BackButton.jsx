import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

// A plain "go back" button for pages reached by drilling in (Jackpots,
// Wallet, Bet History) that previously had no way out except the sidebar.
// navigate(-1) returns to wherever the user actually came from; falling
// back to the Betting page covers a direct link/refresh where there's no
// history entry to go back to.
export default function BackButton({ fallback = "/betting" }) {
  const navigate = useNavigate();

  function goBack() {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate(fallback);
    }
  }

  return (
    <button
      type="button"
      onClick={goBack}
      className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-chalk/60 hover:text-chalk"
    >
      <ArrowLeft size={16} />
      Back
    </button>
  );
}
