import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css"; // Make sure this imports your Tailwind CSS

// Make sure the root element exists
const rootElement = document.getElementById("root");
if (!rootElement) {
  const newRoot = document.createElement("div");
  newRoot.id = "root";
  document.body.appendChild(newRoot);
}

ReactDOM.createRoot(rootElement || document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
