import { useState } from "react";
import { Routes, Route } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import SotopiaDashboard from "./pages/SotopiaDashboard";

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/sotopia" element={<SotopiaDashboard />} />
    </Routes>
  );
}

export default App;
