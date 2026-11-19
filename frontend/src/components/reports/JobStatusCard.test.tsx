import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { JobStatusCard } from './JobStatusCard';
import type { Job } from '../../lib/types';

function makeJob(overrides: Partial<Job>): Job {
  return {
    id: 'job-123',
    job_type: 'generate_project_report',
    status: 'queued',
    attempts: 0,
    max_attempts: 3,
    run_at: '2026-11-20T10:00:00Z',
    last_error: null,
    result: null,
    project_id: 'p1',
    created_by: 'u1',
    created_at: '2026-11-20T10:00:00Z',
    updated_at: '2026-11-20T10:00:00Z',
    completed_at: null,
    ...overrides,
  };
}

describe('JobStatusCard', () => {
  it('renders retrying state with attempt count', () => {
    render(
      <JobStatusCard
        job={makeJob({
          status: 'queued',
          attempts: 2,
          max_attempts: 3,
          last_error: 'RuntimeError: transient error',
        })}
        isOwner={true}
      />,
    );

    expect(screen.getByText('Retrying (attempt 2 of 3)')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('transient error');
  });

  it('renders download link on succeeded job', () => {
    render(
      <JobStatusCard
        job={makeJob({
          status: 'succeeded',
          attempts: 1,
          result: { report_id: 'rep-42' },
        })}
        isOwner={false}
      />,
    );

    expect(screen.getByText('Succeeded')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /download \.md/i });
    expect(link).toHaveAttribute('href', expect.stringContaining('/reports/rep-42'));
  });

  it('shows Retry button on dead job only for owners', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();

    const { rerender } = render(
      <JobStatusCard
        job={makeJob({ status: 'dead', attempts: 3, last_error: 'Permanent failure' })}
        isOwner={false}
        onRetry={onRetry}
      />,
    );

    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();

    rerender(
      <JobStatusCard
        job={makeJob({ status: 'dead', attempts: 3, last_error: 'Permanent failure' })}
        isOwner={true}
        onRetry={onRetry}
      />,
    );

    await user.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledWith('job-123');
  });
});
