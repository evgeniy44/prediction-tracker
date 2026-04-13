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

## Important

- If a post contains **both** predictions and non-predictions, label **YES** (at least one prediction present)
- Judge based on the **author's intent at time of writing** — even if the prediction later came true or was obviously wrong
- Ukrainian political/military commentary often mixes analysis with predictions — look for the future-oriented verifiable claim
