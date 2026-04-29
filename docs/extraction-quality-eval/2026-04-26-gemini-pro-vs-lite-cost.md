# Gemini 3.1 Pro Preview vs Flash Lite Preview — порівняння вартості

**Дата:** 2026-04-26
**Контекст:** Task 13.5 extraction quality evaluation. Pro Preview додано як 4-та модель після paid Tier 1 для Gemini API.

## TL;DR

| Метрика | Flash Lite | **Pro Preview** | Ratio |
|---------|-----------:|----------------:|------:|
| Input price ($/1M tokens) | $0.25 | $2.00 | **8×** |
| Output price ($/1M tokens) | $1.50 | $12.00 | **8×** |
| Cost on 97 gold-постах | ~$0.06 | ~$2.00 | **~33×** |
| Cost на full 5572 Arestovich | ~$3.50 | **~$115** | **~33×** |
| avg_quality_score | 2.029 | **2.304** | +14 % |
| precision на витягнутих claims | 51 % | **65 %** | +28 % |
| YES recall (15 gold YES posts) | **11/15** | 9/15 | −13 % |
| Cost-per-valid-claim | **$0.003** | $0.13 | 43× |

**Bottom line:** Pro Preview коштує **~33 разів більше** ніж Flash Lite за +14 % avg_score; recall гірший на 13 %. Flash Lite суттєво виграє за cost-per-valid-claim (43× дешевше).

## Ціни (litellm `model_cost`, станом на 2026-04-26)

```
gemini-3.1-pro-preview:
  input_cost_per_token:  $2.00 / 1M  ($4.00 / 1M above 200k context)
  output_cost_per_token: $12.00 / 1M ($18.00 / 1M above 200k context)

gemini-3.1-flash-lite-preview:
  input_cost_per_token:  $0.25 / 1M
  output_cost_per_token: $1.50 / 1M
```

**Важливо для Pro:** це **thinking model**. Її `reasoning_tokens` тарифікуються як звичайні output-токени (`output_cost_per_reasoning_token = None` → fallback до `output_cost_per_token = $12/1M`). На практиці Pro випльовує ~5–10× більше output-токенів ніж non-reasoning модель з тим самим JSON-результатом.

## Розрахунок на нашому датасеті

### Параметри 97 Arestovich gold-постів

| Параметр | Значення |
|----------|---------:|
| Постів | 97 |
| Avg chars/пост | 1 376 |
| Median chars/пост | 841 |
| Max chars/пост | 4 120 |
| Estimated avg post tokens (3 chars/token, mixed Cyrillic+Latin) | ~459 |
| Extraction system prompt (`EXTRACTION_SYSTEM`) | ~803 tokens |
| User-template overhead | ~50 tokens |
| **Total input/call** | **~1 312 tokens** |

### Output-token estimates

Pro Preview — thinking режим, тому output включає reasoning:

| Модель | Avg output tokens/call | Total output tokens (97 викликів) |
|--------|----------------------:|----------------------------------:|
| Flash Lite | ~200 (JSON only) | ~19 400 |
| **Pro Preview** | **~1 500 (thinking + JSON)** | **~145 500** |

Pro генерує помітно менше final claims (23 проти 35 у Flash Lite), але загальна вага output вища через невидимі reasoning-токени.

### Cost calculation

**Flash Lite (97 постів):**
```
Input:  127 k tokens × $0.25/1M = $0.032
Output: 19.4 k tokens × $1.50/1M = $0.029
TOTAL:  $0.061
```

**Pro Preview (97 постів):**
```
Input:  127 k tokens × $2.00/1M = $0.254
Output: 145.5 k tokens × $12.00/1M = $1.746
TOTAL:  $2.00
```

**Cost ratio: ~33×** (не 8× як показують ціни-за-токен — різниця посилюється thinking-токенами Pro).

## Екстраполяція на повний Arestovich dataset (5572 постів)

Лінійне масштабування 97 → 5572 (×57.4):

| Модель | Estimated total cost |
|--------|--------------------:|
| Flash Lite | ~$3.50 |
| **Pro Preview** | **~$115** |

Чи варто $115 за +14% avg_score та −13% recall? Для нашого use-case — **ні**.

## Якість vs вартість

### Quality metrics (97 Arestovich gold posts, Opus 4.6 judge)

| Метрика | Flash Lite | Pro Preview | Δ |
|---------|-----------:|------------:|--:|
| Total claims витягнуто | 35 | 23 | −34 % |
| `exact_match` | 6 (17 %) | 4 (17 %) | = |
| `faithful_paraphrase` | 12 (34 %) | 11 (48 %) | +14 pp |
| `not_a_prediction` | 17 (49 %) | 8 (35 %) | −14 pp |
| `hallucination` | 0 | 0 | = |
| **Valid claims (3+3 verdicts)** | **18** | **15** | −17 % |
| **Precision** | **51 %** | **65 %** | +14 pp |
| **avg_quality_score** | 2.029 | **2.304** | +14 % |

### Gold-recall (15 YES-постів)

| Метрика | Flash Lite | Pro Preview |
|---------|-----------:|------------:|
| YES posts з валідною екстракцією | **11/15 (73 %)** | 9/15 (60 %) |
| YES posts з 0 валідних claims (miss) | 4/15 | 6/15 |
| `not_a_prediction` claims на NO-постах (false positives) | 0/82 | 0/82 |

Pro Preview пропустив на 2 більше YES-постів. Жодного false-positive на NO-постах у обох моделей.

### Cost-per-valid-claim

| Модель | Total cost (97 постів) | Valid claims | $/valid claim |
|--------|----------------------:|-------------:|--------------:|
| Flash Lite | $0.061 | 18 | **$0.0034** |
| Pro Preview | $2.00 | 15 | $0.133 |

**Pro Preview коштує ~40× більше за один валідний claim.** Це найгостріший cut-метрик: він враховує і ціну, і якість, і recall.

## Якісний аналіз поведінки (на основі manual review YES posts 1–7)

### Pro Preview behavior pattern

**Сильні сторони:**
- Найвища precision (65 %) — менше шуму на claim
- Найнижча `not_a_prediction` rate (35 %) — краще розрізняє реальні передбачення від слоганів
- 0 hallucinations
- Сильніше дотримується critterion 4 (substantiveness): не витягав «К 14 января самолеты возвращают дипломатов» (тривіальна логістика) — як і задумано

**Слабкі сторони:**
- Уникає **імовірнісних claims** з hedge-маркерами («скорее всего», «вероятна», «довольно высокая»)
- Уникає **vague-target claims** без чіткого target_date
- Витягує rhetorical metaphor («агонія влади») в одному з постів — суперечність до власного консервативного патерну
- Пропускає **concrete predictions з deadlines** в окремих постах (приклад: Post 7 — «прекратить боевые действия до конца апреля»)

### Flash Lite behavior pattern

**Сильні сторони:**
- Найвища recall (73 %) на YES-постах
- Дешевий настільки, що можна запускати на будь-якому обсязі

**Слабкі сторони:**
- 49 % витягнутих claims — `not_a_prediction` (slogans / rhetorical / normative)
- Більше шуму потребує downstream-фільтру

## Architectural implications

### Опція A: Single-model production з Flash Lite (поточний baseline)
- Cost: ~$3.50 на 5572 постів
- Quality: 73 % recall, 51 % precision
- **Pros:** дешево, високий recall
- **Cons:** треба пост-фільтр на slogans/normative

### Опція B: Single-model production з Pro Preview
- Cost: ~$115 на 5572 постів
- Quality: 60 % recall, 65 % precision
- **Pros:** менше шуму
- **Cons:** **33× дорожче**, гірший recall

### Опція C: Two-stage pipeline (Flash Lite → Pro Preview re-rank)
- Stage 1: Flash Lite extracts на всіх 5572 постах — $3.50
- Stage 2: Pro Preview re-judges кожен Flash-Lite claim — input ≈ post + claim ≈ ~1500 tokens × 35/97 × 5572 ≈ ~3M tokens. Output невеликий (verdict). Cost ≈ $6–10
- **Total: ~$10–15**
- **Pros:** Flash Lite recall (73 %) + Pro Preview precision filter
- **Cons:** не тестували; додаткова інфраструктура

### Рекомендація
Для нашого pet-проекту з фіксованим бюджетом на api: **залишаємось на Flash Lite (Option A)** + light heuristic post-filter (regex на slogans). Опція C цікава на майбутнє якщо precision стане критичною.

## Caveats

1. **Token estimates approximate.** Token counts не зберігалися в артефактах; використано середнє чарактерне приближення (3 chars/token для mixed Cyrillic+Latin). Реальна вартість може варіюватись ±30 %.
2. **Pro «thinking output» оцінено приблизно.** Точний reasoning_tokens count потребує перезапуску з логуванням `response.usage`.
3. **Один прогін кожного.** Дисперсія між запусками не вимірювалась.
4. **Free-tier обмеження зняте.** Розрахунки припускають paid Tier 1 (без cache hits, без batch API).
5. **Prompt caching не використано.** З promptт caching (`cache_creation` + `cache_read` для system prompt) Pro можна знизити до ~$50–80, Flash Lite до ~$2.50.

## TODO
- [ ] Перезапустити з token logging для точних чисел
- [ ] Перевірити як змінюється cost з prompt caching активованим
- [ ] Прототип Option C (Flash Lite → Pro re-rank) на 50 постах для proof-of-concept
