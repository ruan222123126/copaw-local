import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { AgentsPage } from "../features/agents/AgentsPage";
import { ChatPage } from "../features/chat/ChatPage";
import { ChannelsPage } from "../features/channels/ChannelsPage";
import { CronJobsPage } from "../features/cron-jobs/CronJobsPage";
import { EnvironmentsPage } from "../features/environments/EnvironmentsPage";
import { ModelsPage } from "../features/models/ModelsPage";
import { SessionsPage } from "../features/sessions/SessionsPage";
import { SkillsPage } from "../features/skills/SkillsPage";
import { WorkspacePage } from "../features/workspace/WorkspacePage";
import { useConsoleStore } from "../store/app-store";

const NAV_ITEMS = [
  { path: "/chat", label: "Chat" },
  { path: "/channels", label: "Channels" },
  { path: "/sessions", label: "Sessions" },
  { path: "/cron-jobs", label: "Cron Jobs" },
  { path: "/skills", label: "Skills" },
  { path: "/workspace", label: "Workspace" },
  { path: "/models", label: "Models" },
  { path: "/environments", label: "Environments" },
  { path: "/agents", label: "Agents" },
];

function HeaderControls() {
  const userId = useConsoleStore((state) => state.userId);
  const channel = useConsoleStore((state) => state.channel);
  const setUserId = useConsoleStore((state) => state.setUserId);
  const setChannel = useConsoleStore((state) => state.setChannel);

  return (
    <div className="topbar-controls">
      <label>
        user_id
        <input
          value={userId}
          onChange={(event) => setUserId(event.target.value || "default")}
          placeholder="default"
        />
      </label>
      <label>
        channel
        <input
          value={channel}
          onChange={(event) => setChannel(event.target.value || "console")}
          placeholder="console"
        />
      </label>
    </div>
  );
}

export function App() {
  return (
    <div className="app-shell">
      <aside className="left-rail">
        <div className="brand">
          <img src="/copaw-symbol.svg" alt="CoPaw" />
          <div>
            <strong>CoPaw Console Next</strong>
            <span>重建版前端</span>
          </div>
        </div>

        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                isActive ? "nav-link is-active" : "nav-link"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <p>
            使用 <code>COPAW_CONSOLE_STATIC_DIR</code> 切换灰度，当前工程默认对接同源 API。
          </p>
          <HeaderControls />
        </header>

        <section className="page-shell">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/channels" element={<ChannelsPage />} />
            <Route path="/sessions" element={<SessionsPage />} />
            <Route path="/cron-jobs" element={<CronJobsPage />} />
            <Route path="/models" element={<ModelsPage />} />
            <Route path="/environments" element={<EnvironmentsPage />} />
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/workspace" element={<WorkspacePage />} />
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Routes>
        </section>
      </main>
    </div>
  );
}
