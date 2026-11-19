import type { ProjectMember, StoryPriority } from './types';

export interface ParsedQuickAdd {
  title: string;
  assigneeId: string | null;
  priority: StoryPriority;
  dueDate: string | null;
}

export type QuickAddParseResult =
  | { ok: true; value: ParsedQuickAdd }
  | { ok: false; error: string };

const VALID_PRIORITIES = new Set<StoryPriority>(['low', 'medium', 'high', 'urgent']);
const ISO_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

function formatLocalDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function parseDueToken(raw: string, referenceDate: Date): string | null {
  const lowered = raw.toLowerCase();
  if (lowered === 'today') {
    return formatLocalDate(referenceDate);
  }
  if (lowered === 'tomorrow') {
    const next = new Date(referenceDate);
    next.setDate(next.getDate() + 1);
    return formatLocalDate(next);
  }
  const match = ISO_DATE_RE.exec(raw);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const probe = new Date(Date.UTC(year, month - 1, day));
  if (
    probe.getUTCFullYear() !== year ||
    probe.getUTCMonth() !== month - 1 ||
    probe.getUTCDate() !== day
  ) {
    return null;
  }
  return raw;
}

function matchMember(handle: string, members: ProjectMember[]): ProjectMember | undefined {
  const target = handle.toLowerCase();
  return members.find((member) => {
    const emailLower = member.email.toLowerCase();
    const emailLocal = emailLower.split('@')[0] ?? '';
    const nameLower = member.name.toLowerCase();
    const firstName = nameLower.split(/\s+/)[0] ?? '';
    const compactName = nameLower.replace(/\s+/g, '');
    return (
      emailLower === target ||
      emailLocal === target ||
      nameLower === target ||
      firstName === target ||
      compactName === target
    );
  });
}

export function parseQuickAdd(
  input: string,
  members: ProjectMember[],
  referenceDate: Date = new Date(),
): QuickAddParseResult {
  const trimmed = input.trim();
  if (!trimmed) {
    return { ok: false, error: 'Enter a story title to quick-add.' };
  }

  const tokens = trimmed.split(/\s+/);
  const titleParts: string[] = [];
  let assigneeId: string | null = null;
  let priority: StoryPriority = 'medium';
  let dueDate: string | null = null;

  for (const token of tokens) {
    if (token.startsWith('@') && token.length > 1) {
      const handle = token.slice(1);
      const matched = matchMember(handle, members);
      if (!matched) {
        return {
          ok: false,
          error: `Unknown assignee "${token}". Match a project member's name or email prefix.`,
        };
      }
      assigneeId = matched.user_id;
      continue;
    }

    if (token.startsWith('!') && token.length > 1) {
      const candidate = token.slice(1).toLowerCase() as StoryPriority;
      if (!VALID_PRIORITIES.has(candidate)) {
        return {
          ok: false,
          error: `Invalid priority "${token}". Use !low, !medium, !high, or !urgent.`,
        };
      }
      priority = candidate;
      continue;
    }

    if (token.toLowerCase().startsWith('due:')) {
      const rawDate = token.slice(4);
      const parsed = parseDueToken(rawDate, referenceDate);
      if (!parsed) {
        return {
          ok: false,
          error: `Invalid due date "${token}". Use due:YYYY-MM-DD, due:today, or due:tomorrow.`,
        };
      }
      dueDate = parsed;
      continue;
    }

    titleParts.push(token);
  }

  const title = titleParts.join(' ').trim();
  if (!title) {
    return { ok: false, error: 'Story title cannot be empty.' };
  }

  return {
    ok: true,
    value: {
      title,
      assigneeId,
      priority,
      dueDate,
    },
  };
}
