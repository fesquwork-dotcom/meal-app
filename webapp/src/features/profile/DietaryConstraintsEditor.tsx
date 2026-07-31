import { useState, type FC } from 'react';
import { Button, Chip, Input, Section, Typography } from '@/components/ui';
import {
  addConstraint,
  constraintsByKind,
  removeConstraint,
} from '@/features/profile/dietaryConstraints';
import type { DietaryConstraintKind, Profile } from '@/types/profile';

type VisibleConstraintKind = Exclude<DietaryConstraintKind, 'intolerance'>;

const KIND_LABELS: Record<VisibleConstraintKind, string> = {
  allergy: 'Аллергия',
  preference: 'Не нравится',
};

const SECTION_COPY: Record<
  VisibleConstraintKind,
  { title: string; description: string; confirmRemove?: string }
> = {
  allergy: {
    title: 'Аллергии',
    description: 'Эти продукты полностью исключаются из рецептов и корзины.',
    confirmRemove:
      'После удаления продукт снова сможет появляться в меню. Удалить аллергию?',
  },
  preference: {
    title: 'Не люблю / не предлагать',
    description: 'Вкусовые предпочтения, которые можно изменить в любой момент.',
  },
};

interface ConstraintSectionProps {
  kind: VisibleConstraintKind;
  profile: Profile;
  disabled?: boolean;
  onChange: (profile: Profile) => void;
}

const ConstraintSection: FC<ConstraintSectionProps> = ({
  kind,
  profile,
  disabled = false,
  onChange,
}) => {
  const [draftValue, setDraftValue] = useState('');
  const copy = SECTION_COPY[kind];
  const items = constraintsByKind(profile.dietary_constraints, kind);

  const handleAdd = () => {
    const trimmed = draftValue.trim();
    if (!trimmed) return;
    onChange({
      ...profile,
      dietary_constraints: addConstraint(profile.dietary_constraints, kind, trimmed),
    });
    setDraftValue('');
  };

  const handleRemove = (id: string, value: string) => {
    if (copy.confirmRemove && !window.confirm(copy.confirmRemove.replace('аллергию', value))) {
      return;
    }
    if (!copy.confirmRemove && !window.confirm(`Удалить «${value}»?`)) {
      return;
    }
    onChange({
      ...profile,
      dietary_constraints: removeConstraint(profile.dietary_constraints, id),
    });
  };

  return (
    <Section title={copy.title} description={copy.description}>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <Chip
            key={item.id}
            selected
            disabled={disabled}
            onClick={() => !disabled && handleRemove(item.id, item.value)}
          >
            {item.value} ×
          </Chip>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <Input
          value={draftValue}
          disabled={disabled}
          placeholder="Введите продукт"
          onChange={(event) => setDraftValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              handleAdd();
            }
          }}
        />
        <Button type="button" disabled={disabled || !draftValue.trim()} onClick={handleAdd}>
          Добавить
        </Button>
      </div>
    </Section>
  );
};

interface LegacyConstraintsSectionProps {
  profile: Profile;
  disabled?: boolean;
  onChange: (profile: Profile) => void;
}

const LegacyConstraintsSection: FC<LegacyConstraintsSectionProps> = ({
  profile,
  disabled = false,
  onChange,
}) => {
  if (profile.legacy_constraints.length === 0) {
    return null;
  }

  const handleClassify = (legacyValue: string, kind: VisibleConstraintKind) => {
    const nextConstraints = addConstraint(profile.dietary_constraints, kind, legacyValue);
    onChange({
      ...profile,
      dietary_constraints: nextConstraints,
      legacy_constraints: profile.legacy_constraints.filter((item) => item !== legacyValue),
      requires_constraint_review: profile.legacy_constraints.length > 1,
    });
  };

  return (
    <Section
      title="Старые исключения"
      description="Уточните, почему их нужно исключать. До классификации продукт остаётся исключённым."
    >
      <div className="flex flex-col gap-4">
        {profile.legacy_constraints.map((value) => (
          <div key={value} className="rounded-lg border border-app-border p-3">
            <Typography variant="label" className="mb-2 block">
              Почему исключить «{value}»?
            </Typography>
            <div className="flex flex-wrap gap-2">
              {(['allergy', 'preference'] as VisibleConstraintKind[]).map(
                (kind) => (
                  <Chip
                    key={kind}
                    disabled={disabled}
                    onClick={() => !disabled && handleClassify(value, kind)}
                  >
                    {KIND_LABELS[kind]}
                  </Chip>
                ),
              )}
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
};

export interface DietaryConstraintsEditorProps {
  profile: Profile;
  onChange: (profile: Profile) => void;
  disabled?: boolean;
  fieldErrors?: Record<string, string>;
}

export const DietaryConstraintsEditor: FC<DietaryConstraintsEditorProps> = ({
  profile,
  onChange,
  disabled = false,
  fieldErrors = {},
}) => {
  return (
    <div className="flex flex-col gap-6">
      {profile.requires_constraint_review && (
        <Typography variant="caption" className="text-app-hint" role="status">
          Проверьте старые исключения — укажите тип для каждого продукта.
        </Typography>
      )}
      {fieldErrors.dietary_constraints && (
        <Typography variant="caption" className="text-app-destructive" role="alert">
          {fieldErrors.dietary_constraints}
        </Typography>
      )}
      <ConstraintSection kind="allergy" profile={profile} disabled={disabled} onChange={onChange} />
      <ConstraintSection
        kind="preference"
        profile={profile}
        disabled={disabled}
        onChange={onChange}
      />
      <LegacyConstraintsSection profile={profile} disabled={disabled} onChange={onChange} />
    </div>
  );
};
