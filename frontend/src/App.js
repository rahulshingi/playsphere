import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/context/AuthContext";
import "@/App.css";

import Home from "@/pages/Home";
import Events from "@/pages/Events";
import EventDetail from "@/pages/EventDetail";
import Teams from "@/pages/Teams";
import TeamDetail from "@/pages/TeamDetail";
import PlayerDetail from "@/pages/PlayerDetail";
import Standings from "@/pages/Standings";
import Sponsors from "@/pages/Sponsors";
import Admin from "@/pages/Admin";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import RegisterTeam from "@/pages/RegisterTeam";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/events" element={<Events />} />
          <Route path="/events/:id" element={<EventDetail />} />
          <Route path="/teams" element={<Teams />} />
          <Route path="/teams/:id" element={<TeamDetail />} />
          <Route path="/players/:id" element={<PlayerDetail />} />
          <Route path="/standings" element={<Standings />} />
          <Route path="/sponsors" element={<Sponsors />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/register-team" element={<RegisterTeam />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" theme="dark" />
    </AuthProvider>
  );
}

export default App;
