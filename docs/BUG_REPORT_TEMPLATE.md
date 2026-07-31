# Bug Report Template

```text
Заголовок:

QA scenario ID:

Дата и время:

Environment:
  frontend URL:
  backend URL:
  ENVIRONMENT:
  ALLOW_DEV_AUTH:
  ADAPTIVE_PREFERENCES:
  Claude configured: yes/no

Initial fixture:

Шаги:

Фактический результат:

Ожидаемый результат:

Повторяемость:
Всегда / Иногда / Один раз

Что изменилось в данных:
  Profile:
  Strategy/MenuPlan:
  Learned Preferences:
  иначе:

Console error:

Correlation ID:

Diagnostics bundle:
  (вставить JSON со страницы /diagnostics → «Скопировать диагностическую информацию»)

Screenshot/video:

Severity:
Blocker / Critical / Major / Minor / Cosmetic
```

## Severity contract

### Blocker
- приложение не запускается;
- невозможно создать первый план;
- потеря/повреждение данных;
- auth bypass;
- privacy leak.

### Critical
- неправильный current plan;
- duplicate Strategy/MenuPlan;
- Profile priority нарушен;
- revoke не работает;
- текущий план меняется после accept/revoke/dismiss-review;
- reset затрагивает другого пользователя.

### Major
- broken feature flow;
- некорректная invalidation;
- review появляется/исчезает неправильно;
- History/Insights падают.

### Minor / Cosmetic
- текст, spacing, non-blocking a11y, animation, единичный визуальный дефект.

## Privacy

Не прикладывать: initData, tokens, API keys, полный Profile, названия блюд, raw SQL, stack traces с секретами.
