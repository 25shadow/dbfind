import { NavLink, Outlet } from "react-router-dom";

export function AppLayout() {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand">DbFind</div>
        <nav className="nav-list">
          <NavLink to="/workspace">工作台</NavLink>
          <NavLink to="/history">历史</NavLink>
          <NavLink to="/settings">设置</NavLink>
        </nav>
      </aside>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

