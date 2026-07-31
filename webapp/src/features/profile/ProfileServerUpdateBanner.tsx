import type { FC } from 'react';

import { Button, Typography } from '@/components/ui';
import type { ProfileServerUpdateState } from '@/features/profile/profileServerUpdate';
import { buildProfileServerUpdateViewModel } from '@/features/profile/profileServerUpdateViewModel';

export interface ProfileServerUpdateBannerProps {
  state: ProfileServerUpdateState;
  dismissedForRevision: number | null;
  onContinueEditing: () => void;
  onLoadServerVersion: () => void;
}

/**
 * Soft warning: the server profile changed while a dirty draft exists.
 * Not a destructive error — uses secondary theme tokens, `role="status"`.
 */
export const ProfileServerUpdateBanner: FC<ProfileServerUpdateBannerProps> = ({
  state,
  dismissedForRevision,
  onContinueEditing,
  onLoadServerVersion,
}) => {
  const viewModel = buildProfileServerUpdateViewModel(state, dismissedForRevision);

  if (!viewModel.visible) {
    return null;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col gap-3 rounded-app bg-app-secondary p-4"
    >
      <div className="flex flex-col gap-1">
        <Typography variant="body" className="font-semibold text-app-text">
          {viewModel.title}
        </Typography>
        <Typography variant="caption" className="text-app-hint">
          {viewModel.description}
        </Typography>
      </div>
      <div className="flex flex-col gap-2">
        {viewModel.canContinueEditing && (
          <Button type="button" variant="ghost" size="sm" onClick={onContinueEditing}>
            Продолжить редактирование
          </Button>
        )}
        {viewModel.canLoadServerVersion && (
          <Button type="button" variant="secondary" size="sm" onClick={onLoadServerVersion}>
            Загрузить сохранённые
          </Button>
        )}
      </div>
    </div>
  );
};
