import { forwardRef, type InputHTMLAttributes } from 'react';
import { AlertCircle } from 'lucide-react';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, id, className = '', ...props },
  ref,
) {
  const inputId = id ?? props.name;
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-neutral-900">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={inputId}
        aria-invalid={Boolean(error)}
        className={[
          'block w-full rounded border bg-neutral-0 px-3 py-2 text-sm text-neutral-900',
          'placeholder:text-neutral-500 transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-brand focus:border-brand',
          error ? 'border-neutral-900' : 'border-neutral-200',
          className,
        ].join(' ')}
        {...props}
      />
      {error ? (
        <p role="alert" className="flex items-center gap-1.5 text-xs font-medium text-neutral-900">
          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-brand" aria-hidden="true" />
          <span>{error}</span>
        </p>
      ) : (
        hint && <p className="text-xs text-neutral-500">{hint}</p>
      )}
    </div>
  );
});
