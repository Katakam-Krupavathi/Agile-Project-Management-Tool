import { useState, type FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Trash2, UserPlus } from 'lucide-react';
import { AppShell } from '../components/layout/AppShell';
import { buildProjectNav } from '../components/layout/projectNav';
import { Avatar, Button, ErrorState, Input, Select, Skeleton } from '../components/ui';
import { useCurrentUser, useLogout } from '../hooks/useAuth';
import { useProjects, useProjectTree } from '../hooks/useProjects';
import {
  useAddProjectMember,
  useProjectMembers,
  useRemoveProjectMember,
  useUpdateProjectMemberRole,
} from '../hooks/useWorkspace';
import { canManageProject } from '../lib/permissions';
import type { ProjectRole } from '../lib/types';

const ROLE_OPTIONS: { value: ProjectRole; label: string }[] = [
  { value: 'owner', label: 'Owner' },
  { value: 'member', label: 'Member' },
  { value: 'viewer', label: 'Viewer' },
];

export function ProjectMembersPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const { data: projectsPage } = useProjects(Boolean(user));
  const { data: tree, isLoading: loadingTree } = useProjectTree(projectId);
  const membersQuery = useProjectMembers(projectId);
  const addMember = useAddProjectMember(projectId ?? '');
  const updateRole = useUpdateProjectMemberRole(projectId ?? '');
  const removeMember = useRemoveProjectMember(projectId ?? '');

  const [email, setEmail] = useState('');
  const [role, setRole] = useState<ProjectRole>('member');
  const [confirmRemoveId, setConfirmRemoveId] = useState<string | null>(null);

  if (!user) return null;

  const projects = projectsPage?.items ?? [];
  const isOwner = canManageProject(tree?.project.role);
  const members = membersQuery.data?.items ?? [];

  const handleLogout = async () => {
    await logout.mutateAsync();
    navigate('/login', { replace: true });
  };

  const handleAdd = async (event: FormEvent) => {
    event.preventDefault();
    if (!email.trim()) return;
    await addMember.mutateAsync({ email: email.trim(), role });
    setEmail('');
    setRole('member');
  };

  return (
    <AppShell
      user={user}
      projects={projects}
      projectNav={buildProjectNav(projectId, tree?.project.role)}
      onLogout={handleLogout}
      loggingOut={logout.isPending}
      title={tree ? `${tree.project.key} · Members` : 'Project Members'}
      health={tree?.rollup.health}
    >
      {loadingTree || membersQuery.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : !isOwner ? (
        <ErrorState
          title="Owner access required"
          message="Only project owners can manage team membership and roles."
        />
      ) : membersQuery.isError ? (
        <ErrorState
          title="Could not load members"
          message={
            membersQuery.error instanceof Error ? membersQuery.error.message : 'Unexpected error'
          }
          onRetry={() => membersQuery.refetch()}
        />
      ) : (
        <div className="space-y-6">
          <form
            onSubmit={handleAdd}
            className="flex flex-wrap items-end gap-3 rounded border border-neutral-200 bg-neutral-0 p-4"
          >
            <div className="min-w-[220px] flex-1">
              <Input
                label="Add member by email"
                name="member-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="teammate@team.dev"
              />
            </div>
            <div className="w-40">
              <Select
                label="Role"
                name="member-role"
                value={role}
                onChange={(e) => setRole(e.target.value as ProjectRole)}
                options={ROLE_OPTIONS}
              />
            </div>
            <Button type="submit" loading={addMember.isPending}>
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              <span>Add member</span>
            </Button>
          </form>

          <ul className="divide-y divide-neutral-200 overflow-hidden rounded border border-neutral-200 bg-neutral-0">
            {members.map((member) => (
              <li
                key={member.id}
                className="flex flex-wrap items-center justify-between gap-4 px-4 py-3.5"
              >
                <div className="flex items-center gap-3">
                  <Avatar name={member.name} size="md" />
                  <div>
                    <p className="text-sm font-medium text-neutral-900">{member.name}</p>
                    <p className="text-xs text-neutral-500">{member.email}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2.5">
                  <select
                    aria-label={`Role for ${member.name}`}
                    value={member.role}
                    onChange={(e) =>
                      updateRole.mutate({
                        userId: member.user_id,
                        role: e.target.value as ProjectRole,
                      })
                    }
                    className="rounded border border-neutral-200 bg-neutral-0 px-2.5 py-1.5 text-xs font-medium text-neutral-900 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
                  >
                    {ROLE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>

                  {confirmRemoveId === member.user_id ? (
                    <div className="flex items-center gap-1.5">
                      <Button
                        size="sm"
                        variant="primary"
                        loading={removeMember.isPending}
                        onClick={async () => {
                          await removeMember.mutateAsync(member.user_id);
                          setConfirmRemoveId(null);
                        }}
                      >
                        Remove
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => setConfirmRemoveId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      aria-label={`Remove ${member.name}`}
                      onClick={() => setConfirmRemoveId(member.user_id)}
                      className="rounded p-1.5 text-neutral-500 hover:bg-neutral-50 hover:text-brand"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </AppShell>
  );
}
