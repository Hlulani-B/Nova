import React from "react";
import { useNavigate } from "react-router-dom";

const css = `
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Poppins:wght@300;400;500&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

html, body, #root { height: 100%; }

.phone {
  width: 100%;
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
  font-family: 'Poppins', sans-serif;
}

.top {
  position: relative;
  background: #acbdaa;
  height: 45%;
  min-height: 260px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.top::after {
  content: "";
  position: absolute;
  bottom: -1px;
  left: 0;
  width: 100%;
  height: 70px;
  background: #fff;
  border-radius: 60% 60% 0 0 / 100% 100% 0 0;
}

.brand {
  position: absolute;
  top: 24px;
  left: 24px;
  color: #fff;
  font-family: 'Playfair Display', serif;
  font-weight: 700;
  letter-spacing: 3px;
  font-size: 18px;
}

.flower { height: 80%; max-height: 320px; width: auto; z-index: 1; margin-top: 10px; }

.content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 32px 32px;
  text-align: center;
}

.title {
  font-family: 'Playfair Display', serif;
  font-size: 52px;
  color: #acbdaa;
  letter-spacing: 2px;
}

.desc {
  margin: 14px auto 0;
  max-width: 560px;
  font-weight: 300;
  font-size: 15px;
  line-height: 1.8;
  color: #6b6b6b;
}

.btn {
  margin-top: 28px;
  border: none;
  background: #acbdaa;
  color: #fff;
  font-family: 'Poppins', sans-serif;
  font-weight: 500;
  font-size: 15px;
  padding: 14px 44px;
  border-radius: 40px;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(172, 189, 170, 0.5);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 26px rgba(172, 189, 170, 0.65);
}

@media (min-width: 900px) {
  .top::after { height: 110px; }
  .brand { top: 32px; left: 44px; font-size: 24px; }
  .title { font-size: 76px; }
  .desc { font-size: 18px; }
  .btn { font-size: 17px; padding: 18px 64px; }
}
`;

function Flower() {
    const navigate = useNavigate();
  const petals = [0, 60, 120, 180, 240, 300];
  return (
    <svg className="flower" viewBox="0 0 200 240" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <path d="M100 120 C100 160 92 200 100 235" />
      <path d="M99 185 C70 180 55 160 52 145 C80 148 95 163 99 185Z" />
      <path d="M101 205 C130 200 145 182 148 168 C120 170 105 185 101 205Z" />
      <g transform="translate(100 78)">
        {petals.map((a) => (
          <ellipse key={a} cx="0" cy="-34" rx="16" ry="30" transform={`rotate(${a})`} fill="rgba(255,255,255,0.2)" />
        ))}
        <circle r="14" fill="#fff" />
      </g>
    </svg>
  );
}

export default function App() {
    const navigate = useNavigate();
  return (
    <>
      <style>{css}</style>
      <div className="phone">
        <div className="top">
          <span className="brand">NOVA</span>
          <Flower />
        </div>
        <div className="content">
          <h1 className="title">Nova</h1>
          <p className="desc">
            A gentle little helper for your messy spreadsheets. Upload your
            data and Nova quietly tidies it up, smoothing out duplicates and
            gaps so everything feels clear, calm and ready to explore.
          </p>
          <button className="btn" onClick={() => navigate('/workspace')}>
            Get Started
          </button>
        </div>
      </div>
    </>
  );
}