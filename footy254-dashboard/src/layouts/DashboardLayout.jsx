import { Outlet } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import Footer from "../components/Footer";
import BetSlipDrawer from "../components/BetSlipDrawer";

export default function DashboardLayout() {
  return (
    <div className="page-glow flex min-h-screen flex-col text-chalk">
      <Sidebar />
      <Header />
      <main className="mx-auto w-full max-w-md flex-1 px-4 pb-6 pt-5 sm:max-w-2xl lg:max-w-6xl lg:pl-28">
        <Outlet />
      </main>
      <div className="pb-24 lg:pb-0">
        <Footer />
      </div>
      {/* Mounted once here (not per-page) so a bet slip selection survives
          navigating away from the Betting page. */}
      <BetSlipDrawer />
    </div>
  );
}
