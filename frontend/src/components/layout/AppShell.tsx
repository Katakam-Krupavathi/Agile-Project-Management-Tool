import type { ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { FolderKanban, LogOut } from 'lucide-react';
import { Avatar, HealthPulse, type ProjectHealth } from '../ui';
import { NotificationsBell } from './NotificationsBell';

export interface SidebarProject {
  id: string;
  key: string;
  name: string;
}

export interface SidebarUser {
  id: string;
  name: string;
  email: string;
}

export interface ProjectNavItem {
  to: string;
  label: string;
  end?: boolean;
}

export interface AppShellProps {
  user: SidebarUser;
  projects: SidebarProject[];
  projectNav?: ProjectNavItem[];
  onLogout: () => void;
  loggingOut?: boolean;
  title: string;
  health?: ProjectHealth;
  viewToggle?: ReactNode;
  headerActions?: ReactNode;
  children: ReactNode;
}

export function AppShell({
  user,
  projects,
  projectNav,
  onLogout,
  loggingOut = false,
  title,
  health,
  viewToggle,
  headerActions,
  children,
}: AppShellProps) {
  return (
    <div className="flex min-h-screen bg-neutral-50 text-neutral-900">
      <aside className="flex w-64 shrink-0 flex-col bg-brand text-neutral-0">
        <div className="flex h-14 items-center gap-2.5 border-b border-brand-600 px-5">
          <Link to="/projects" className="flex items-center gap-2.5 focus:outline-none">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded bg-accent text-xs font-bold text-neutral-0">
              AP
            </span>
            <span className="text-sm font-semibold tracking-tight">Agile PM</span>
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Main navigation">
          <NavLink
            to="/projects"
            end
            className={({ isActive }) =>
              [
                'flex items-center gap-2.5 rounded px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-brand-600 text-neutral-0'
                  : 'text-brand-100 hover:bg-brand-600/70 hover:text-neutral-0',
              ].join(' ')
            }
          >
            <FolderKanban className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>Projects</span>
          </NavLink>

          {projectNav && projectNav.length > 0 && (
            <div className="mt-6">
              <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-brand-200">
                Project
              </p>
              <ul className="mt-2 space-y-1">
                {projectNav.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      className={({ isActive }) =>
                        [
                          'block rounded px-3 py-1.5 text-sm transition-colors',
                          isActive
                            ? 'bg-brand-600 font-medium text-neutral-0'
                            : 'text-brand-100 hover:bg-brand-600/70 hover:text-neutral-0',
                        ].join(' ')
                      }
                    >
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {projects.length > 0 && (
            <div className="mt-6">
              <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-brand-200">
                Your Projects
              </p>
              <ul className="mt-2 space-y-1">
                {projects.map((project) => (
                  <li key={project.id}>
                    <NavLink
                      to={`/projects/${project.id}`}
                      className={({ isActive }) =>
                        [
                          'flex items-center gap-2 rounded px-3 py-1.5 text-sm transition-colors',
                          isActive
                            ? 'bg-brand-600 font-medium text-neutral-0'
                            : 'text-brand-100 hover:bg-brand-600/70 hover:text-neutral-0',
                        ].join(' ')
                      }
                    >
                      <span className="inline-block w-11 shrink-0 font-mono text-xs font-semibold text-accent-200">
                        {project.key}
                      </span>
                      <span className="truncate">{project.name}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </nav>

        <div className="border-t border-brand-600 p-3">
          <div className="flex items-center gap-2.5 px-2 py-1.5">
            <Avatar name={user.name} size="sm" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-neutral-0">{user.name}</p>
              <p className="truncate text-[11px] text-brand-200">{user.email}</p>
            </div>
            <button
              type="button"
              onClick={onLogout}
              disabled={loggingOut}
              title="Sign out"
              aria-label="Sign out"
              className="rounded p-1.5 text-brand-200 transition-colors hover:bg-brand-600 hover:text-neutral-0 disabled:opacity-50"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col bg-neutral-0">
        <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-neutral-200 bg-neutral-0 px-6">
          <div className="flex min-w-0 items-center gap-3">
            <h1 className="truncate text-base font-semibold text-neutral-900">{title}</h1>
            {health && <HealthPulse health={health} />}
          </div>
          <div className="flex items-center gap-3">
            {viewToggle}
            {headerActions}
            <NotificationsBell />
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-neutral-50 p-6">{children}</main>
      </div>
    </div>
  );
}
