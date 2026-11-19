import { AlertTriangle, CheckCircle2, Clock, Download, Loader2, RotateCcw } from 'lucide-react';
import { Badge, Button } from '../ui';
import { reportsApi } from '../../lib/api';
import type { Job } from '../../lib/types';

export interface JobStatusCardProps {
  job: Job;
  isOwner: boolean;
  retrying?: boolean;
  onRetry?: (jobId: string) => void;
}

export function JobStatusCard({
  job,
  isOwner,
  retrying = false,
  onRetry,
}: JobStatusCardProps) {
  const isRetrying = job.status === 'queued' && job.attempts > 0;
  const isDead = job.status === 'dead' || job.status === 'failed';
  const reportId =
    job.result && typeof job.result.report_id === 'string' ? job.result.report_id : null;

  let statusLabel = 'Queued';
  let badgeVariant: 'brand' | 'accent' | 'neutral' = 'neutral';
  let icon = <Clock className="h-4 w-4 text-neutral-500" aria-hidden="true" />;

  if (isRetrying) {
    statusLabel = `Retrying (attempt ${job.attempts} of ${job.max_attempts})`;
    badgeVariant = 'brand';
    icon = <Clock className="h-4 w-4 text-brand" aria-hidden="true" />;
  } else if (job.status === 'running') {
    statusLabel = `Running (attempt ${job.attempts} of ${job.max_attempts})`;
    badgeVariant = 'brand';
    icon = <Loader2 className="h-4 w-4 animate-spin text-brand" aria-hidden="true" />;
  } else if (job.status === 'succeeded') {
    statusLabel = 'Succeeded';
    badgeVariant = 'accent';
    icon = <CheckCircle2 className="h-4 w-4 text-accent" aria-hidden="true" />;
  } else if (isDead) {
    statusLabel = `Failed (${job.attempts}/${job.max_attempts} attempts)`;
    badgeVariant = 'brand';
    icon = <AlertTriangle className="h-4 w-4 text-brand" aria-hidden="true" />;
  }

  return (
    <section
      aria-label="Report job status"
      className="flex flex-wrap items-center justify-between gap-4 rounded border border-neutral-200 bg-neutral-0 p-4"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5">{icon}</div>
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-neutral-900">Report generation job</span>
            <Badge variant={badgeVariant}>{statusLabel}</Badge>
          </div>
          <p className="font-mono text-xs text-neutral-500">Job ID: {job.id}</p>
          {job.last_error && (
            <p role="alert" className="text-xs font-medium text-brand">
              Last error: {job.last_error}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {job.status === 'succeeded' && reportId && (
          <a
            href={reportsApi.downloadUrl(reportId)}
            download
            className="inline-flex h-8 items-center gap-1.5 rounded border border-neutral-200 bg-neutral-0 px-3 text-xs font-medium text-neutral-900 hover:bg-neutral-50"
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Download .md</span>
          </a>
        )}

        {job.status === 'dead' && isOwner && onRetry && (
          <Button
            size="sm"
            variant="primary"
            loading={retrying}
            onClick={() => onRetry(job.id)}
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Retry</span>
          </Button>
        )}
      </div>
    </section>
  );
}
