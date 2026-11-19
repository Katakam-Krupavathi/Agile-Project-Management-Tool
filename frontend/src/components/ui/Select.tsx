import { forwardRef, type SelectHTMLAttributes } from 'react';
import { AlertCircle } from 'lucide-react';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, options, error, id, className = '', ...props },
  ref,
) {
  const selectId = id ?? props.name;
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={selectId} className="block text-sm font-medium text-neutral-900">
          {label}
        </label>
      )}
      <select
        ref={ref}
        id={selectId}
        aria-invalid={Boolean(error)}
        className={[
          'block w-full rounded border bg-neutral-0 px-3 py-2 text-sm text-neutral-900',
          'transition-colors focus:outline-none focus:ring-2 focus:ring-brand focus:border-brand',
          error ? 'border-neutral-900' : 'border-neutral-200',
          className,
        ].join(' ')}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && (
        <p role="alert" className="flex items-center gap-1.5 text-xs font-medium text-neutral-900">
          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-brand" aria-hidden="true" />
          <span>{error}</span>
        </p>
      )}
    </div>
  );
});
