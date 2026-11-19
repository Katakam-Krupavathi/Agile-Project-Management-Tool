import type { ProjectNavItem } from './AppShell';

export function buildProjectNav(projectId: string | undefined): ProjectNavItem[] {
  if (!projectId) return [];
  return [
    { to: `/projects/${projectId}`, label: 'Workspace', end: true },
    { to: `/projects/${projectId}/activity`, label: 'Activity' },
    { to: `/projects/${projectId}/reports`, label: 'Reports' },
  ];
}
