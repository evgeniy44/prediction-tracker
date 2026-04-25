# Annotation Guidelines: Prediction Detection (Level 1)

## Task

For each text post, answer: **Does this text contain at least one prediction?** (YES / NO)

## Definition

A **prediction** is a statement about a **future event** that can later be **verified** as true or false.

## YES — contains a prediction

- Concrete claim about a future event: "Війна закінчиться до кінця 2023 року"
- Forecast with approximate timing: "Контрнаступ почнеться влітку"
- Forecast without date but verifiable post-factum: "Росія програє цю війну"
- Quantitative forecast: "Рубль впаде до 100 за долар"
- Prediction about someone's actions: "Путін не застосує ядерну зброю"
- Prediction embedded in longer text (even one sentence counts)

## NO — does not contain a prediction

- **Fact / news**: "Сьогодні обстріляли Харків" (past/present event)
- **Opinion / assessment**: "Це була помилка командування" (evaluation, not forecast)
- **Intent / declaration**: "Ми будемо боротись до перемоги" (willpower, not prediction)
- **Vague conditional**: "Якщо дадуть зброю — переможемо" (no specific outcome claimed)
- **Rhetorical**: "Хто міг подумати?" (not a claim)
- **Too vague**: "Думаю, переговори можливі" (no concrete event)
- **Analysis of present**: "Ми підготовлені краще ніж рік тому" (assessment of now)
- **Call to action**: "Підтримайте ЗСУ!" (appeal, not forecast)

## Edge Cases

| Text | Label | Why |
|------|-------|-----|
| "Санкції запрацюють через 6-12 місяців" | YES | Specific timeframe, verifiable |
| "Думаю, Росія не витримає довго" | NO | Too vague, no concrete event |
| "F-16 змінять ситуацію в небі" | YES | Implicit prediction about future impact |
| "Ми вже бачимо деморалізацію ворога" | NO | Observation of present |
| "До кінця року звільнимо Херсон" | YES | Concrete event + deadline |
| "Перемога буде за нами" | NO | Slogan / declaration, not verifiable prediction |

## Hard Patterns (refined in annotation session, 2026-04-17)

Four patterns that caused most ambiguity in first 130 labels. All default to **NO** unless the exception criterion is met.

### 1. Timestamp / topic lists of video shows

Most Arestovich posts that consist of a YouTube timestamp list default to **NO** — the post text is metadata pointing to a video, not the predictive content itself.

- **NO by default**: questions ("Що з Крахом?"), topic labels ("Сценарії розвитку"), neutral summaries ("Позиція США").
- **YES exception**: only if the timestamp descriptions *themselves* contain fully-formed concrete predictions (timeframe, probability, or quantitative claim). Example from real data: `"прохода ВСУ до Мариуполя и прорыв блокады вероятна"`, `"в ближайшие дни поедут 45 автобусов"`, `"Призыв в апреле–июле в РФ и вероятность направления срочников - 100%"` — all in one post → YES.
- Single short statement in a timestamp list (e.g. `"На Україну не будуть чинити тиск через Мінський формат"`) is not enough → NO.

### 2. Slogan predictions without verifiability criteria

Pledges/slogans that sound forward-looking but have no way to measure fulfilment → **NO**.

- "Жоден злочин не залишиться безкарним"
- "Військові злочинці будуть покарані. Рано чи пізно вони понесуть відповідальність."
- "Зроблять все необхідне, щоб знайти злочинців"
- "Перемога буде за нами"
- "Грузія буде вільною" (when isolated, without a specific event)

Even though technically about the future, these lack a concrete outcome threshold or timeframe that can be checked in N years.

### 3. Normative "треба/повинно" vs predictive "буде/станеться"

Distinguish what the author says **should** happen (prescription) vs. what **will** happen (prediction).

- **NO** — normative: "Україна має скасувати воєнний стан", "треба змінити систему", "необхідно провести реформи", "держава повинна передбачати наслідки".
- **YES** — predictive: "Зеленський оголосить вибори до кінця року", "Захід ніколи не дасть гарантій безпеки".

Rule of thumb: if replacing the verb with "must / should" fits → NO. If replacing with "will / is going to" fits → YES candidate.

### 4. Hedged / vague predictions without concrete content

Timeline without content, or content without any threshold → **NO**.

- "Найближчі тижні будуть переломними" — no specific outcome → NO.
- "Скоро стане проблемою суспільного масштабу" — "скоро" + "проблемою" too vague → NO.
- "Серія гонок триватиме в активній фазі до ~2045" — has timeline but content ("цікавих подій буде багато") is vague → NO.
- "Поразка Росії стане неминучою" — no criterion for "поразка" → NO (unless context defines it).

If you can't imagine what specifically would falsify the claim in 1/5/10 years, it's not a prediction.

### 5. Non-substantive claims (added 2026-04-21 — discovered during Task 13.5 dry run)

Verifiable + future-pointing — but outcome is **mechanically determined** or just **restates a known fact**. These pollute the dataset (no user would query them) → **NO**.

- "К 14 січня літаки повернуть дипломатів" — routine logistical schedule, not a forecast.
- "Трамп зможе вести переговори тільки після інавгурації 20 січня" — restates US constitutional law.
- "Суд має винести рішення до кінця місяця" — procedural deadline, not outcome forecast.
- "Парламент проведе засідання у вівторок" — calendar-bound certainty.

**Test:** "Would a reader 1 year later actually CARE whether this came true?" If no — it's not substantive, label NO.

This rules out prediction-shaped claims about scheduled events whose **mechanism is known** (planes fly on schedule, leaders inaugurate on date, parliaments meet weekly). Real predictions are about events where the **outcome is uncertain** — would a peace deal be signed, would a leader be removed, would sanctions take effect.

## Important

- If a post contains **both** predictions and non-predictions, label **YES** (at least one prediction present)
- Judge based on the **author's intent at time of writing** — even if the prediction later came true or was obviously wrong
- Ukrainian political/military commentary often mixes analysis with predictions — look for the future-oriented verifiable claim
- **Be strict on verifiability.** Given low base rate (~12-15% YES in Arestovich's Telegram), annotator drift toward YES inflates false positives in gold labels. When in doubt, prefer NO.
