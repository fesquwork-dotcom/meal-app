import type { ProfileServerUpdateState } from '@/features/profile/profileServerUpdate';

export interface ProfileServerUpdateViewModel {
  visible: boolean;
  title: string;
  description: string;
  canLoadServerVersion: boolean;
  canContinueEditing: boolean;
}

const HIDDEN: ProfileServerUpdateViewModel = {
  visible: false,
  title: '',
  description: '',
  canLoadServerVersion: false,
  canContinueEditing: false,
};

export const PROFILE_SERVER_UPDATE_TITLE = 'Сохранённые настройки изменились';

export const PROFILE_SERVER_UPDATE_DESCRIPTION =
  'Ваши несохранённые изменения сохранены на этом устройстве. ' +
  'Перед сохранением нужно выбрать, какую версию оставить.';

/**
 * Pure view model for the soft server-update warning banner.
 * «Продолжить редактирование» hides the banner only for the dismissed
 * revision; a newer server revision shows the banner again.
 */
export function buildProfileServerUpdateViewModel(
  state: ProfileServerUpdateState,
  dismissedForRevision: number | null,
): ProfileServerUpdateViewModel {
  if (state.status !== 'detected') {
    return HIDDEN;
  }

  if (dismissedForRevision !== null && dismissedForRevision === state.currentServerRevision) {
    return HIDDEN;
  }

  return {
    visible: true,
    title: PROFILE_SERVER_UPDATE_TITLE,
    description: PROFILE_SERVER_UPDATE_DESCRIPTION,
    canLoadServerVersion: true,
    canContinueEditing: true,
  };
}
