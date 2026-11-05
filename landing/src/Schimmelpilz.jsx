import { useEffect, useState } from "react";
import "./schimmelpilz-guide.css";

// "Schimmelpilz", the office's comic assistant (after the figure in the logo): brown hair in a bun,
// black robe with white bands, pink flip-flops. Drawn as SVG so poses and faces can change per step.
const SKIN = "#f6cfae", SKIN_DARK = "#e3ab86", HAIR = "#6b3f25", HAIR_DARK = "#4d2b18", ROBE = "#1f2228", ROBE_LIGHT = "#363a43", PINK = "#ff4f9f";

const Hand = ({ x, y, r = 8 }) => <circle cx={x} cy={y} r={r} fill={SKIN} stroke={SKIN_DARK} strokeWidth="1.2" />;
const Sleeve = ({ d }) => <path d={d} fill={ROBE} stroke={ROBE_LIGHT} strokeWidth="1.2" strokeLinejoin="round" />;
const LEFT_DOWN = <g><Sleeve d="M66 130 C52 150 46 176 47 196 L67 199 C67 178 71 158 78 141 Z" /><Hand x={57} y={203} /></g>;
const RIGHT_DOWN = <g><Sleeve d="M134 130 C148 150 154 176 153 196 L133 199 C133 178 129 158 122 141 Z" /><Hand x={143} y={203} /></g>;

function Letter({ x = 68, y = 138 }) {
  return <g transform={`rotate(-5 ${x + 32} ${y + 24})`}>
    <rect x={x} y={y} width="64" height="48" rx="2" fill="#fffdf6" stroke="#c9cfbf" strokeWidth="1.3" />
    {[10, 17, 24, 31].map(line => <line key={line} x1={x + 8} x2={x + (line === 31 ? 36 : 56)} y1={y + line} y2={y + line} stroke="#b8beb0" strokeWidth="2" strokeLinecap="round" />)}
    <text x={x + 50} y={y + 42} fontSize="12" fontWeight="700" fill="#a12b2b" fontFamily="Georgia, serif">§</text>
  </g>;
}

function Folder() {
  return <g transform="rotate(4 100 172)">
    <path d="M64 146 h22 l5 -6 h22 l5 6 h18 v50 h-72 Z" fill="#0b5a46" stroke="#083f31" strokeWidth="1.4" strokeLinejoin="round" />
    <rect x="80" y="160" width="40" height="15" rx="2" fill="#fffdf6" />
    <text x="100" y="171.5" fontSize="9.5" fontWeight="700" textAnchor="middle" fill="#0b5a46" fontFamily="Arial, sans-serif" letterSpacing=".8">AKTE</text>
  </g>;
}

const POSES = {
  wave: { look: [1, -1], arms: <>{LEFT_DOWN}<g className="sp-wave"><Sleeve d="M132 134 C150 122 160 100 163 78 L147 73 C145 93 137 109 122 121 Z" />
    <circle cx="157" cy="66" r="9.5" fill={SKIN} stroke={SKIN_DARK} strokeWidth="1.2" />{[-8, -3, 2, 7].map(dx => <ellipse key={dx} cx={157 + dx} cy="55" rx="2.6" ry="5.5" fill={SKIN} stroke={SKIN_DARK} strokeWidth="1" />)}</g></> },
  read: { look: [0, 3], glasses: true, arms: <><Sleeve d="M66 130 C56 152 60 170 76 178 L86 166 C77 160 75 149 78 140 Z" /><Sleeve d="M134 130 C144 152 140 170 124 178 L114 166 C123 160 125 149 122 140 Z" />
    <Letter /><Hand x={74} y={176} /><Hand x={126} y={176} /></> },
  file: { look: [-1, 1], arms: <><Sleeve d="M66 130 C56 152 58 170 72 182 L84 172 C76 164 75 150 78 140 Z" /><Sleeve d="M134 130 C144 152 142 170 128 182 L116 172 C124 164 125 150 122 140 Z" />
    <Folder /><Hand x={70} y={184} /><Hand x={130} y={184} /></> },
  think: { look: [-2, -3], arms: <>{LEFT_DOWN}<Sleeve d="M130 130 C152 140 154 168 140 170 C128 172 120 150 113 126 L124 121 C129 141 134 155 139 156 C143 150 140 141 128 138 Z" /><Hand x={116} y={120} />
    <g className="sp-float"><text x="160" y="86" fontSize="24" fontWeight="800" fill="#0b5a46">?</text><text x="178" y="66" fontSize="16" fontWeight="800" fill="#a27d49">?</text></g></> },
  alarm: { look: [0, 0], arms: <><Sleeve d="M68 132 C52 120 44 98 41 76 L57 72 C59 92 65 108 78 120 Z" /><Hand x={47} y={66} r={9} /><Sleeve d="M132 132 C148 120 156 98 159 76 L143 72 C141 92 135 108 122 120 Z" /><Hand x={153} y={66} r={9} />
    <path className="sp-float" d="M146 92 C146 86 150 82 150 82 C150 82 154 86 154 92 C154 96 146 96 146 92 Z" fill="#8fd0ff" stroke="#4c9fd8" strokeWidth="1" /></> },
  cheer: { look: [1, -1], arms: <>{LEFT_DOWN}<g className="sp-wave"><Sleeve d="M132 134 C150 122 160 100 163 80 L147 75 C145 95 137 109 122 121 Z" />
    <circle cx="156" cy="68" r="9.5" fill={SKIN} stroke={SKIN_DARK} strokeWidth="1.2" /><rect x="153" y="49" width="6.5" height="14" rx="3.2" fill={SKIN} stroke={SKIN_DARK} strokeWidth="1.1" /></g>
    <g className="sp-float" fill="#e8b83a"><path d="M40 70 l3 -9 l3 9 l9 3 l-9 3 l-3 9 l-3 -9 l-9 -3 Z" /><path d="M172 112 l2 -6 l2 6 l6 2 l-6 2 l-2 6 l-2 -6 l-6 -2 Z" /></g></> },
  point: { look: [3, 0], arms: <>{LEFT_DOWN}<Sleeve d="M132 134 C150 130 165 124 178 117 L184 131 C169 138 153 145 128 150 Z" /><Hand x={186} y={124} /><ellipse cx="197" cy="122" rx="7" ry="2.8" fill={SKIN} stroke={SKIN_DARK} strokeWidth="1" /></> },
};

const MOUTHS = {
  grin: <path d="M88 105 Q100 118 112 105 Z" fill="#fff" stroke="#7a2d22" strokeWidth="2" strokeLinejoin="round" />,
  smile: <path d="M90 106 Q100 114 110 106" fill="none" stroke="#7a2d22" strokeWidth="2.4" strokeLinecap="round" />,
  focus: <path d="M93 108 Q100 111 107 108" fill="none" stroke="#7a2d22" strokeWidth="2.4" strokeLinecap="round" />,
  worried: <ellipse cx="100" cy="109" rx="5" ry="6" fill="#7a2d22" />,
  think: <path d="M93 109 Q99 106 107 110" fill="none" stroke="#7a2d22" strokeWidth="2.4" strokeLinecap="round" />,
};
const BROWS = {
  grin: ["M80 74 Q87 70 94 73", "M106 73 Q113 70 120 74"], smile: ["M80 75 Q87 71 94 74", "M106 74 Q113 71 120 75"],
  focus: ["M80 76 L94 75", "M106 75 L120 76"], worried: ["M80 74 Q87 72 94 70", "M106 70 Q113 72 120 74"], think: ["M80 73 Q87 69 94 72", "M106 76 L120 76"],
};

export function SchimmelpilzFigure({ pose = "wave", mood = "smile", talking = false, size = 150, title = "Frau Schimmelpilz, Ihre Rechtsassistentin" }) {
  const shape = POSES[pose] || POSES.wave;
  const [dx, dy] = shape.look;
  return <svg className={`sp-figure${talking ? " talking" : ""}`} viewBox="0 0 210 280" width={size} height={size * 280 / 210} role="img" aria-label={title}>
    <ellipse cx="100" cy="268" rx="54" ry="6" fill="rgba(0,0,0,.12)" />
    <g className="sp-body">
      {/* legs and pink flip-flops */}
      <rect x="83" y="232" width="11" height="28" rx="4" fill={SKIN} /><rect x="106" y="232" width="11" height="28" rx="4" fill={SKIN} />
      <ellipse cx="87" cy="263" rx="14" ry="4.5" fill={PINK} /><ellipse cx="113" cy="263" rx="14" ry="4.5" fill={PINK} />
      <ellipse cx="87" cy="259" rx="10" ry="4" fill={SKIN} /><ellipse cx="113" cy="259" rx="10" ry="4" fill={SKIN} />
      <path d="M80 260 L88 254 L95 260 M106 260 L113 254 L120 260" stroke={PINK} strokeWidth="2.6" fill="none" strokeLinecap="round" />
      {/* robe */}
      <path d="M60 136 C64 124 78 118 100 118 C122 118 136 124 140 136 L153 236 C130 245 70 245 47 236 Z" fill={ROBE} stroke={ROBE_LIGHT} strokeWidth="1.4" />
      <path d="M92 122 L88 238 M108 122 L112 238" stroke={ROBE_LIGHT} strokeWidth="3" />
      <path d="M72 170 L66 230 M128 170 L134 230" stroke={ROBE_LIGHT} strokeWidth="1.4" opacity=".7" />
      {/* neck and white bands (Beffchen) */}
      <rect x="93" y="110" width="14" height="13" fill={SKIN} />
      <path d="M86 120 Q100 128 114 120 L112 126 Q100 132 88 126 Z" fill="#fff" />
      <path d="M94 126 L100 129 L97 150 L90 148 Z M106 126 L100 129 L103 150 L110 148 Z" fill="#fff" stroke="#d9dde2" strokeWidth=".8" />
      {shape.arms}
      {/* head */}
      <g className="sp-head">
        <circle cx="100" cy="74" r="41" fill={HAIR} />
        <circle cx="131" cy="36" r="15" fill={HAIR} stroke={HAIR_DARK} strokeWidth="1.5" />
        <path d="M124 32 Q132 26 138 34 Q133 42 126 38" fill="none" stroke={HAIR_DARK} strokeWidth="1.6" />
        <path d="M143 44 Q152 50 148 60 M119 30 Q112 28 110 34" fill="none" stroke={HAIR} strokeWidth="2.6" strokeLinecap="round" />
        <circle cx="66" cy="90" r="6" fill={SKIN} stroke={SKIN_DARK} /><circle cx="134" cy="90" r="6" fill={SKIN} stroke={SKIN_DARK} />
        <ellipse cx="100" cy="88" rx="33" ry="31" fill={SKIN} />
        <path d="M66 82 C68 58 90 46 112 50 C128 53 138 66 136 84 C128 70 116 62 104 66 C94 60 78 66 66 82 Z" fill={HAIR} />
        <path d="M68 80 C62 94 64 110 70 118" fill="none" stroke={HAIR} strokeWidth="5" strokeLinecap="round" />
        <g className="sp-eyes">
          {[87, 113].map(x => <g key={x}><ellipse cx={x} cy="88" rx="7.2" ry="8.6" fill="#fff" stroke="#3b2a20" strokeWidth="1.3" />
            <circle cx={x + dx} cy={88 + dy} r="4.6" fill="#5a3418" /><circle cx={x + dx} cy={88 + dy} r="2.2" fill="#1a0f08" /><circle cx={x + dx + 1.6} cy={86 + dy} r="1.3" fill="#fff" /></g>)}
        </g>
        {shape.glasses && <g fill="none" stroke="#2c2f36" strokeWidth="1.8"><circle cx="87" cy="88" r="10.5" /><circle cx="113" cy="88" r="10.5" /><path d="M97.5 87 Q100 85 102.5 87" /></g>}
        {(BROWS[mood] || BROWS.smile).map(d => <path key={d} d={d} fill="none" stroke={HAIR_DARK} strokeWidth="2.6" strokeLinecap="round" />)}
        <path d="M98 96 Q100 99 102 96" fill="none" stroke={SKIN_DARK} strokeWidth="1.6" strokeLinecap="round" />
        <ellipse cx="78" cy="101" rx="5.5" ry="3.2" fill="#ff8f8f" opacity=".35" /><ellipse cx="122" cy="101" rx="5.5" ry="3.2" fill="#ff8f8f" opacity=".35" />
        <g className="sp-mouth-rest">{MOUTHS[mood] || MOUTHS.smile}</g>
        <ellipse className="sp-mouth-talk" cx="100" cy="108" rx="6" ry="4.5" fill="#7a2d22" />
      </g>
    </g>
  </svg>;
}

// Speech bubble that writes its text like someone talking; click or reduced motion shows it at once.
function useTyped(text) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const quiet = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (quiet) { setShown(text.length); return undefined; }
    setShown(0);
    let at = 0;
    const timer = setInterval(() => { at = Math.min(text.length, at + 2); setShown(at); if (at >= text.length) clearInterval(timer); }, 22);
    return () => clearInterval(timer);
  }, [text]);
  return [text.slice(0, shown), shown < text.length, () => setShown(text.length)];
}

export function AssistantSays({ pose, mood, text, note, children, compact = false }) {
  const [typed, typing, finish] = useTyped(text);
  return <div className={`sp-guide${compact ? " compact" : ""}`}>
    <div className="sp-figure-wrap"><SchimmelpilzFigure pose={pose} mood={mood} talking={typing} size={compact ? 96 : 140} /></div>
    <div className="sp-bubble" onClick={finish}>
      <span className="sp-name">Frau Schimmelpilz</span>
      <p aria-hidden="true">{typed}{typing && <span className="sp-caret">▍</span>}</p>
      <p className="sp-sr" aria-live="polite">{text}</p>
      {note && !typing && <small>{note}</small>}
      {children && <div className={`sp-replies${typing ? " waiting" : ""}`}>{children}</div>}
    </div>
  </div>;
}

// The way a law office handles incoming post, shown as a track the assistant walks along.
export function OfficeTrack({ steps, current, busy = false }) {
  return <ol className="sp-track" aria-label="Ablauf">
    {steps.map((label, index) => <li key={label} className={index < current ? "done" : index === current ? `now${busy ? " busy" : ""}` : ""} aria-current={index === current ? "step" : undefined}>
      <span>{index < current ? "✓" : index + 1}</span><em>{label}</em></li>)}
  </ol>;
}
