import { useState } from "react";
import { useNavigate } from "react-router-dom";

export function LandingPage() {
  const navigate = useNavigate();
  
  const projects = [
    {
      title: "Sotopia",
      description: "A platform for social interaction simulation and analysis",
      icon: "🌐",
    },
    {
      title: "Inspicio",
      description: "Interactive data exploration and visualization tool",
      icon: "📊",
    },
    {
      title: "OSW Data",
      description: "Open source data management and processing tools",
      icon: "📦",
    }
  ];

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "20px" }}>
      {/* Hero Section */}
      <section style={{ 
        padding: "60px 20px", 
        textAlign: "center",
        background: "#f9fafb",
        borderRadius: "8px",
        marginBottom: "40px"
      }}>
        <h1 style={{ fontSize: "48px", fontWeight: "bold", marginBottom: "16px" }}>
          Welcome to Our Platform
        </h1>
        <p style={{ fontSize: "20px", color: "#6b7280", maxWidth: "600px", margin: "0 auto" }}>
          Explore our suite of tools for data analysis, social simulation, and more
        </p>
        <div style={{ marginTop: "32px" }}>
          <button 
            onClick={() => navigate("/sotopia")}
            style={{
              background: "#1f2937",
              color: "white",
              padding: "12px 24px",
              borderRadius: "6px",
              fontWeight: "500",
              marginRight: "12px",
              border: "none",
              cursor: "pointer"
            }}
          >
            Explore Sotopia
          </button>
          <button style={{
            background: "white",
            color: "#1f2937",
            padding: "12px 24px",
            borderRadius: "6px",
            fontWeight: "500",
            border: "1px solid #e5e7eb",
            cursor: "pointer"
          }}>
            Learn More
          </button>
        </div>
      </section>

      {/* Projects Section */}
      <section style={{ padding: "40px 0" }}>
        <h2 style={{ fontSize: "30px", fontWeight: "bold", textAlign: "center", marginBottom: "40px" }}>
          Our Projects
        </h2>
        <div style={{ 
          display: "grid", 
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", 
          gap: "24px" 
        }}>
          {projects.map((project, index) => (
            <div key={index} style={{ 
              border: "1px solid #e5e7eb", 
              borderRadius: "8px",
              padding: "24px",
              background: "white",
              boxShadow: "0 1px 3px rgba(0,0,0,0.1)"
            }}>
              <div style={{ fontSize: "36px", marginBottom: "16px" }}>{project.icon}</div>
              <h3 style={{ fontSize: "20px", fontWeight: "600", marginBottom: "8px" }}>{project.title}</h3>
              <p style={{ color: "#6b7280", marginBottom: "16px" }}>{project.description}</p>
              <button 
                onClick={() => navigate(`/${project.title.toLowerCase()}`)}
                style={{
                  background: "#1f2937",
                  color: "white",
                  padding: "8px 16px",
                  borderRadius: "6px",
                  fontWeight: "500",
                  width: "100%",
                  border: "none",
                  cursor: "pointer"
                }}
              >
                Explore {project.title}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer style={{ 
        borderTop: "1px solid #e5e7eb", 
        padding: "24px 0",
        marginTop: "40px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap"
      }}>
        <p style={{ color: "#6b7280", fontSize: "14px" }}>
          © 2023 Our Platform. All rights reserved.
        </p>
        <div style={{ display: "flex", gap: "16px" }}>
          <button style={{ 
            background: "transparent", 
            border: "none", 
            color: "#6b7280",
            cursor: "pointer"
          }}>About</button>
          <button style={{ 
            background: "transparent", 
            border: "none", 
            color: "#6b7280",
            cursor: "pointer"
          }}>Contact</button>
          <button style={{ 
            background: "transparent", 
            border: "none", 
            color: "#6b7280",
            cursor: "pointer"
          }}>GitHub</button>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage; 