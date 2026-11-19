import { useState, type FormEvent } from 'react';
import { AlertCircle } from 'lucide-react';
import { Button, Input, Modal } from '../ui';
import { useCreateProject } from '../../hooks/useProjects';
import { ApiError } from '../../lib/api';

export interface CreateProjectModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (projectId: string) => void;
}

const KEY_REGEX = /^[A-Z]{2,5}$/;

export function CreateProjectModal({ open, onClose, onCreated }: CreateProjectModalProps) {
  const createProject = useCreateProject();

  const [key, setKey] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);

  const resetAndClose = () => {
    setKey('');
    setName('');
    setDescription('');
    setError(null);
    onClose();
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    const normalizedKey = key.trim().toUpperCase();
    if (!KEY_REGEX.test(normalizedKey)) {
      setError('Project key must be 2 to 5 uppercase letters (A–Z).');
      return;
    }
    if (!name.trim()) {
      setError('Project name is required.');
      return;
    }

    try {
      const created = await createProject.mutateAsync({
        key: normalizedKey,
        name: name.trim(),
        description: description.trim() ? description.trim() : null,
      });
      resetAndClose();
      onCreated?.(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Unable to create project.');
    }
  };

  return (
    <Modal open={open} title="New project" onClose={resetAndClose}>
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded border border-brand-200 bg-brand-50 px-3 py-2.5 text-sm text-brand"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        <Input
          label="Project key"
          name="key"
          required
          maxLength={5}
          value={key}
          onChange={(e) => setKey(e.target.value.toUpperCase().replace(/[^A-Z]/g, ''))}
          placeholder="APM"
          hint="2 to 5 uppercase letters (e.g., APM, CORE)."
        />

        <Input
          label="Project name"
          name="name"
          required
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Core Platform"
        />

        <div className="space-y-1.5">
          <label htmlFor="project-description" className="block text-sm font-medium text-neutral-900">
            Description <span className="font-normal text-neutral-500">(optional)</span>
          </label>
          <textarea
            id="project-description"
            rows={3}
            maxLength={4000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Scope and goals for this project..."
            className="block w-full rounded border border-neutral-200 bg-neutral-0 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-500 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand"
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={resetAndClose}>
            Cancel
          </Button>
          <Button type="submit" loading={createProject.isPending}>
            Create project
          </Button>
        </div>
      </form>
    </Modal>
  );
}
