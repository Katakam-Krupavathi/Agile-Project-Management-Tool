import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { Button, Input } from '../components/ui';
import { useRegister } from '../hooks/useAuth';
import { ApiError } from '../lib/api';

export function RegisterPage() {
  const navigate = useNavigate();
  const register = useRegister();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    if (!name.trim()) {
      setFormError('Please enter your name.');
      return;
    }
    if (!email.trim()) {
      setFormError('Please enter your email.');
      return;
    }
    if (password.length < 8) {
      setFormError('Password must be at least 8 characters.');
      return;
    }

    try {
      await register.mutateAsync({
        name: name.trim(),
        email: email.trim(),
        password,
      });
      navigate('/projects', { replace: true });
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : 'Unable to create account.');
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-50 p-6">
      <section className="w-full max-w-md rounded border border-neutral-200 bg-neutral-0 p-8 shadow-sm">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="inline-flex h-8 w-8 items-center justify-center rounded bg-brand text-sm font-semibold text-neutral-0"
          >
            AP
          </span>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-brand">Create account</h1>
            <p className="text-xs text-neutral-500">Agile Project Management Tool</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
          {formError && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded border border-brand-200 bg-brand-50 px-3 py-2.5 text-sm text-brand"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{formError}</span>
            </div>
          )}

          <Input
            label="Full name"
            name="name"
            type="text"
            autoComplete="name"
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Alex Rivera"
          />

          <Input
            label="Email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="alex@team.dev"
          />

          <Input
            label="Password"
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            hint="At least 8 characters."
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />

          <Button type="submit" className="w-full" loading={register.isPending}>
            Create account
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-neutral-500">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-brand hover:underline">
            Sign in
          </Link>
        </p>
      </section>
    </main>
  );
}
