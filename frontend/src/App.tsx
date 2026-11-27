import { useState } from "react";
import { useTranslation } from "react-i18next";
import { LANGUAGES } from "./i18n";
import Connections from "./pages/Connections";
import Squads from "./pages/Squads";
import ReviewAssistants from "./pages/ReviewAssistants";
import DailyAssistants from "./pages/DailyAssistants";

const TABS = { review: ReviewAssistants, daily: DailyAssistants, squads: Squads, connections: Connections };
type Tab = keyof typeof TABS;

export default function App() {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<Tab>("review");
  const Page = TABS[tab];
  return (
    <div className="app">
      <header>
        <h1>Squad Assistant</h1>
        <nav>
          {(Object.keys(TABS) as Tab[]).map((k) => (
            <button key={k} className={k === tab ? "active" : ""} onClick={() => setTab(k)}>
              {t(`nav.${k}`)}
            </button>
          ))}
        </nav>
        <select value={i18n.resolvedLanguage} onChange={(e) => i18n.changeLanguage(e.target.value)}>
          {Object.entries(LANGUAGES).map(([code, label]) => (
            <option key={code} value={code}>{label}</option>
          ))}
        </select>
      </header>
      <main>
        <Page />
      </main>
    </div>
  );
}
