import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/context/AuthContext";
import "@/App.css";

import Home from "@/pages/Home";
import Events from "@/pages/Events";
import EventDetail from "@/pages/EventDetail";
import TeamDetail from "@/pages/TeamDetail";
import PlayerDetail from "@/pages/PlayerDetail";
import Standings from "@/pages/Standings";
import Sponsors from "@/pages/Sponsors";
import LiveScorecard from "@/pages/LiveScorecard";
import Admin from "@/pages/Admin";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import RegisterTeam from "@/pages/RegisterTeam";
import SignupCompany from "@/pages/SignupCompany";
import Services from "@/pages/Services";
import ServiceDetail from "@/pages/ServiceDetail";
import Dashboard from "@/pages/Dashboard";
import Bookings from "@/pages/Bookings";
import PlatformAdmin from "@/pages/PlatformAdmin";
import PlayerSignup from "@/pages/PlayerSignup";
import PlayerLogin from "@/pages/PlayerLogin";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import PlayerProfile from "@/pages/PlayerProfile";
import { PlayerSearch, PlayerProfileView } from "@/pages/PlayerDirectory";
import VendorSignup from "@/pages/VendorSignup";
import VendorDashboard from "@/pages/VendorDashboard";
import VendorMarket from "@/pages/VendorMarket";
import About from "@/pages/About";
import Contact from "@/pages/Contact";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/events" element={<Events />} />
          <Route path="/events/:id" element={<EventDetail />} />
          <Route path="/live/:fixture_id" element={<LiveScorecard />} />
          <Route path="/teams/:id" element={<TeamDetail />} />
          <Route path="/team-players/:id" element={<PlayerDetail />} />
          <Route path="/standings" element={<Standings />} />
          <Route path="/sponsors" element={<Sponsors />} />
          <Route path="/services" element={<Services />} />
          <Route path="/services/:id" element={<ServiceDetail />} />
          <Route path="/about" element={<About />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/hire" element={<VendorMarket />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/bookings" element={<Bookings />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/platform-admin" element={<PlatformAdmin />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/register-team" element={<RegisterTeam />} />
          <Route path="/signup-company" element={<SignupCompany />} />

          {/* Players */}
          <Route path="/players/signup" element={<PlayerSignup />} />
          <Route path="/players/login" element={<PlayerLogin />} />
          <Route path="/players/forgot-password" element={<ForgotPassword />} />
          <Route path="/players/reset-password" element={<ResetPassword />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/players/me" element={<PlayerProfile />} />
          <Route path="/players/profiles" element={<PlayerSearch />} />
          <Route path="/players/profiles/:id" element={<PlayerProfileView />} />

          {/* Vendors */}
          <Route path="/vendor/signup" element={<VendorSignup />} />
          <Route path="/vendor/dashboard" element={<VendorDashboard />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" theme="dark" />
    </AuthProvider>
  );
}

export default App;
