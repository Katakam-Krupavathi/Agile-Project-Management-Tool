import type { ProjectRole } from './types';

export function canEditProjectItems(role: ProjectRole | undefined): boolean {
  return role === 'owner' || role === 'member';
}

export function canManageProject(role: ProjectRole | undefined): boolean {
  return role === 'owner';
}
