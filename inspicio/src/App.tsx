import { useState } from "react";
import { Routes, Route } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import SotopiaDashboard from "./pages/SotopiaDashboard";
import WebArenaDashboard from "./pages/WebArenaDashboard";
import WebArenaMock from "./pages/WebArenaMock";
function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/sotopia" element={<SotopiaDashboard />} />
      <Route path="/webarena" element={<WebArenaDashboard />} />
      <Route path="/webarena-mock" element={<WebArenaMock />} />
    </Routes>
  );
}

export default App;
