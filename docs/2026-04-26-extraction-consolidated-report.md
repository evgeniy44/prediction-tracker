# Consolidated Extraction Report — Task 13.5

**Дата:** 2026-04-26
**Датасет:** 97 Arestovich gold-постів × 4 моделі × Opus 4.6 judge
**Файли-джерела:** `extraction_outputs.json`, `extraction_judgements.json`, `gold_labels.json`

Звіт групує claims по постах (один пост → всі 4 моделі поряд) з вердиктами Opus. Пости, де всі 4 моделі повернули 0 claims і Opus не позначив missed, опущено (нудно).

## Зведена таблиця по моделях

| Модель | Posts з claims | Total claims | Valid | Invalid | Hallucinations | Opus missed |
|--------|---------------:|-------------:|------:|--------:|---------------:|------------:|
| Pro Preview | 12 | 23 | 15 | 8 | 0 | 36 |
| Flash Lite | 17 | 35 | 18 | 17 | 0 | 33 |
| DeepSeek V3.1 | 12 | 64 | 28 | 36 | 0 | 20 |
| Sonnet 4.6 | 3 | 9 | 3 | 6 | 0 | 44 |

**Легенда вердиктів:** ✅ exact_match / faithful_paraphrase  |  ⚠️ valid_but_metadata_error  |  ❌ not_a_prediction / truncated  |  💀 hallucination

---

## YES gold-пости (15)

Очікуємо що моделі знайдуть передбачення.

### `O_Arestovich_official_6481` — gold `YES` — 2024-11-16

> Провели эфир с Юрием Романенко и Яцеком Бартощяком, где говорили об изменениях и перспективах для Украины и Польши после прихода Трампа.  Долгое время в США у власти находились представители Демократической партии, чья политика носит глобалистский характер и сопровождается яркими лозунгами и закулис…

**Pro Preview** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "С приходом к власти в США республиканцев, внешняя политика будет носить характер реалполитик, что подразумевает пересмотр отношений с Европой."
    - *This is a concrete prediction about the character of US foreign policy under the incoming Republican administration, verifiable by observing actual po*
  - 🔍 "Несмотря на изменения во внешней политике США, Украину полностью не бросят."
    - *This predicts that the US will continue some level of support for Ukraine under the new administration, which is a verifiable future outcome.*

**Flash Lite** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "С приходом к власти в США республиканцев, внешняя политика будет носить характер реалполитик, что подразумевает пересмотр отношений с Европой."
    - *This is a concrete prediction about the character of US foreign policy under the incoming Republican administration, verifiable by observing actual po*
  - 🔍 "Несмотря на изменения во внешней политике США, Украину полностью не бросят."
    - *This predicts that the US will continue some level of support for Ukraine under the new administration, which is a verifiable future outcome.*

**DeepSeek V3.1** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "С приходом к власти в США республиканцев, внешняя политика будет носить характер реалполитик, что подразумевает пересмотр отношений с Европой."
    - *This is a concrete prediction about the character of US foreign policy under Republicans, verifiable by observing whether US-Europe relations are subs*
  - 🔍 "Несмотря на изменения во внешней политике США, Украину полностью не бросят."
    - *This predicts that the US will continue some level of support for Ukraine under the new administration, which is a verifiable future outcome.*

**Sonnet 4.6** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "С приходом к власти в США республиканцев, внешняя политика будет носить характер реалполитик, что подразумевает пересмотр отношений с Европой."
    - *This is a concrete prediction about the character of US foreign policy under the incoming Republican administration, verifiable by observing actual po*
  - 🔍 "Несмотря на изменения во внешней политике США, Украину полностью не бросят."
    - *This predicts that the US will continue some level of support for Ukraine under the new administration, which is a verifiable future outcome.*

---

### `O_Arestovich_official_7683` — gold `YES` — 2025-11-12

> - Чтобы лучше понять природу громкого коррупционного скандала в энергетике, его нужно рассматривать в контексте того же двойного ультиматума Трампа.  Коррупция в Украине давно расследована западными партнёрами, и при необходимости могут запускаться процессы с оглаской для общественности.  Коррупция…

**Pro Preview** — 3 claims, 2 missed
- ✅ `faithful_paraphrase` — "С высокой вероятностью будут всплывать всё новые скандалы и факты коррупции - на крови украинских граждан."
  - *This is a near-verbatim quote from the post. It is a forward-looking claim about future corruption scandals surfacing, which is verifiable (either new scandals emerge or they don't) and substantive. T*
- ✅ `faithful_paraphrase` — "Электроэнергия будет отсутствовать часами и днями, отопление - с перебоями, фронт - трещать."
  - *This is a near-verbatim quote from the post making predictions about infrastructure failures and frontline deterioration. These are verifiable future claims about external events with substantive outc*
- ✅ `faithful_paraphrase` — "Будет вскрываться деятельность российской агентуры в высших эшелонах власти"
  - *This is a near-verbatim quote from the post predicting that Russian agent activity in top government echelons will be exposed. This is a future, verifiable, external, and substantive prediction. Metad*
  *Opus каже missed:*
  - 🔍 "Но в любом случае это начало конца Зеленского как политика."
    - *This is a concrete prediction that Zelensky's political career is beginning to end, which is verifiable over time by observing whether he loses power *
  - 🔍 "граждане ничего не смогут изменить до выборов, которые состоятся ещё не скоро"
    - *This predicts that elections will not happen soon, which is a verifiable claim about the timing of Ukrainian elections.*

**Flash Lite** — 3 claims, 3 missed
- ✅ `faithful_paraphrase` — "С высокой вероятностью будут всплывать всё новые скандалы и факты коррупции - на крови украинских граждан."
  - *This is a near-verbatim quote from the post. It is a forward-looking claim about new corruption scandals emerging, which is verifiable (either new scandals surface or they don't) and substantive. The *
- ✅ `exact_match` — "Электроэнергия будет отсутствовать часами и днями, отопление - с перебоями, фронт - трещать."
  - *This is a verbatim quote from the post predicting future energy outages and frontline deterioration. These are verifiable future claims about external events. Metadata is acceptable.*
- ✅ `exact_match` — "Будет вскрываться деятельность российской агентуры в высших эшелонах власти"
  - *Verbatim quote from the post predicting that Russian agent activity in top government echelons will be exposed. This is a future, verifiable, external, substantive prediction. Metadata is correct.*
  *Opus каже missed:*
  - 🔍 "Но в любом случае это начало конца Зеленского как политика."
    - *This is a concrete forward-looking claim that Zelensky's political career is beginning to end, which is verifiable over time by whether he retains pol*
  - 🔍 "процесс может выйти из-под контроля на фоне новых ударов по энергетике и провалов на фронте"
    - *This predicts that the anti-corruption process may spiral out of control amid energy strikes and frontline failures — a verifiable future scenario abo*
  - 🔍 "Если будут обнародованы аналогичные материалы о коррупции в оборонной сфере во время крупных провалов на фронте, украинское общество окажется в состоянии глубочайшего шока."
    - *This is a conditional prediction about public reaction to defense corruption revelations — while conditional, it contains a concrete verifiable outcom*

**DeepSeek V3.1** — 5 claims, 1 missed
- ❌ `not_a_prediction` — "Если будут обнародованы аналогичные материалы о коррупции в оборонной сфере во время крупных провалов на фронте, украинское общество окажется в состоянии глубочайшего шока."
  - *This is a conditional statement ('если будут обнародованы...') describing a hypothetical reaction, not a prediction that something will happen. The author is not predicting that these materials will b*
- ❌ `not_a_prediction` — "С высокой вероятностью будут всплывать всё новые скандалы и факты коррупции - на крови украинских граждан."
  - *While this is forward-looking, it is too vague to be verifiable — 'new scandals and corruption facts will surface' lacks any concrete criteria, timeframe, or specificity that would allow objective ver*
- ❌ `not_a_prediction` — "Электроэнергия будет отсутствовать часами и днями, отопление - с перебоями, фронт - трещать."
  - *This is a vague rhetorical description of expected deteriorating conditions without specific timeframes, thresholds, or measurable criteria. It also largely describes the current ongoing situation rat*
- ❌ `not_a_prediction` — "Будет вскрываться деятельность российской агентуры в высших эшелонах власти"
  - *This is vague — no specifics about who, when, or what level of disclosure. It lacks concrete verifiable criteria and reads more as a rhetorical forecast of general trend.*
- ❌ `not_a_prediction` — "граждане ничего не смогут изменить до выборов, которые состоятся ещё не скоро."
  - *The claim that elections won't happen soon is vague (no timeframe specified), and 'citizens won't be able to change anything' is a rhetorical/normative assessment rather than a verifiable prediction.*
  *Opus каже missed:*
  - 🔍 "Но в любом случае это начало конца Зеленского как политика."
    - *This is a concrete forward-looking claim that the current events mark the beginning of Zelensky's political decline, which is verifiable over time — b*

**Sonnet 4.6** — 0 claims, 4 missed
  *Opus каже missed:*
  - 🔍 "Но в любом случае это начало конца Зеленского как политика."
    - *This is a concrete prediction that Zelensky's political career is beginning to end, which is verifiable over time by observing whether he loses power *
  - 🔍 "С высокой вероятностью будут всплывать всё новые скандалы и факты коррупции"
    - *This predicts that new corruption scandals will emerge in the near future, which is a verifiable future event with a concrete outcome.*
  - 🔍 "процесс может выйти из-под контроля на фоне новых ударов по энергетике и провалов на фронте"
    - *This predicts that the anti-corruption process may spiral out of control amid energy attacks and front-line failures — a verifiable future scenario, t*
  - 🔍 "Будет вскрываться деятельность российской агентуры в высших эшелонах власти"
    - *This predicts that Russian agent activity in top government echelons will be exposed, a concrete verifiable future event.*

---

### `O_Arestovich_official_6695` — gold `YES` — 2024-12-30

> А теперь - как оно на самом деле:  1. Путин никуда не летал и не собирался лететь.   2. Патрушев никуда не летал.  Глава Совета Безопасности, он вообще не внешним делам, а по внутренним, он неуполномочен.   3. Самолёты летного отряда «Россия» - каждый год летают в это время в Нью-Йорк и Вашингтон -…

**Pro Preview** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "я считаю, что вероятность добиться прекращения огня довольно высокая"
    - *This is a substantive prediction about the outcome of Trump's efforts to end the war — that a ceasefire will likely be achieved — which is verifiable *

**Flash Lite** — 1 claims, 0 missed
- ✅ `faithful_paraphrase` — "вероятность добиться прекращения огня довольно высокая"
  - *This is a valid prediction from the post where the author states 'я считаю, что вероятность добиться прекращения огня довольно высокая.' It refers to a future event (ceasefire), is verifiable (either *

**DeepSeek V3.1** — 3 claims, 0 missed
- ❌ `not_a_prediction` — "К 14 января эти же самолеты возвращают этих дипломатов обратно"
  - *This is a description of a routine annual logistical operation (diplomats being flown back after holidays), presented as a known recurring fact. It fails criterion 4 — the outcome is mechanically dete*
- ❌ `not_a_prediction` — "Все разговоры всерьез с кем бы-то ни было Трамп сможет начать только 20 января, после официального приведения к присяге"
  - *This is a restatement of a known constitutional/legal fact — the inauguration date is January 20 and the author is saying Trump can only act officially after that. It fails criterion 4 as a non-substa*
- ✅ `faithful_paraphrase` — "вероятность добиться прекращения огня довольно высокая"
  - *The post says 'я считаю, что вероятность добиться прекращения огня довольно высокая' — this is a genuine prediction about a future uncertain outcome (ceasefire being achieved), it is verifiable, exter*

**Sonnet 4.6** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "я считаю, что вероятность добиться прекращения огня довольно высокая"
    - *This is a substantive prediction about the outcome of Trump's efforts to end the war — that a ceasefire will likely be achieved — which is verifiable *

---

### `O_Arestovich_official_6119` — gold `YES` — 2024-08-26

> «- А в кипящих котлах этих воен и смут, столько пищи для маленьких наших мозгов…» (с)  ———-  Ну давайте я, наконец, проясню:  -  как можно быть «..за переговоры и создание системы коллективной безопасности в Европе с реальным учетом интересов всех сторон» и одновременно - радоваться Курской операции…

**Pro Preview** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "боюсь, на данном историческом этапе, они [союзники] точно не за вариант Б"
    - *This is a verifiable claim about allies' strategic stance — that Western allies will not support full wartime mobilization option for Ukraine at this *
  - 🔍 "оптимальной стратегией на сегодня является Б плавно переходящий в А: нанесение противнику такого ущерба, чтобы он начал реально двигаться и идти на компромиссы"
    - *This is a normative/strategic recommendation rather than a prediction of what WILL happen — on reflection, this does NOT qualify as a prediction.*

**Flash Lite** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "боюсь, на данном историческом этапе, они [союзники] точно не за вариант Б"
    - *This is a verifiable claim about allies' strategic stance — that Western allies will not support full wartime mobilization of Ukraine — which can be c*
  - 🔍 "оптимальной стратегией на сегодня является Б плавно переходящий в А: нанесение противнику такого ущерба, чтобы он начал реально двигаться и идти на компромиссы"
    - *While partly normative, this implicitly predicts that Ukraine's strategy will follow path B transitioning to A, which is verifiable against actual pol*

**DeepSeek V3.1** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "боюсь, на данном историческом этапе, они [союзники] точно не за вариант Б"
    - *This is a verifiable claim about allies' strategic stance — that Western allies will not support full wartime mobilization of Ukraine — which can be c*
  - 🔍 "оптимальной стратегией на сегодня является Б плавно переходящий в А: нанесение противнику такого ущерба, чтобы он начал реально двигаться и идти на компромиссы"
    - *While partly normative, this implicitly predicts that inflicting sufficient damage on Russia will lead it to move toward real compromises — a verifiab*

**Sonnet 4.6** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "боюсь, на данном историческом этапе, они [союзники] точно не за вариант Б"
    - *This is a verifiable claim about allied strategy — that Western allies will not support full wartime mobilization of Ukraine at this stage, which can *

---

### `O_Arestovich_official_6016` — gold `YES` — 2024-08-06

> 1. Операция наших сил по созданию демилитаризированной зоны в Курской области - закономерное развитие войны.  Не надо думать, воюя с централизованным государством (Украиной), что фронт умеют и хотят расширять одностороннее только агрессоры.  Мы умеем играть в эти игры вдвоем.   2. Один из главных во…

**Pro Preview** — 1 claims, 1 missed
- ✅ `exact_match` — "Поэтому, несмотря на анонс ноябрьский переговоров о мире, все время до этих самых переговоров может быть (и скорее всего будет) временем весьма ожесточенных действий сторон."
  - *This is a near-verbatim quote from the post. It predicts that the period until the announced November peace negotiations will be marked by intense military actions by both sides. The hedged 'скорее вс*
  *Opus каже missed:*
  - 🔍 "противник УЖЕ начал снимать с фронта и перебрасывать свои резервы на Курское направление"
    - *This is actually a present/past assessment ('УЖЕ начал'), not a future prediction, so it does not qualify.*

**Flash Lite** — 1 claims, 1 missed
- ✅ `exact_match` — "все время до этих самых переговоров может быть (и скорее всего будет) временем весьма ожесточенных действий сторон."
  - *This is a near-verbatim quote from the post. It predicts that the period until the announced November peace negotiations will be marked by intense military actions by both sides. This is a future-orie*
  *Opus каже missed:*
  - 🔍 "противник УЖЕ начал снимать с фронта и перебрасывать свои резервы на Курское направление"
    - *This is a present-tense factual claim about current troop movements, not a future prediction — so it does NOT qualify. Excluding.*

**DeepSeek V3.1** — 2 claims, 1 missed
- ❌ `not_a_prediction` — "противник УЖЕ начал снимать с фронта и перебрасывать свои резервы на Курское направление"
  - *This is a statement about a present/already-occurring event ('УЖЕ начал' = 'has ALREADY begun'), not a prediction about a future event. It describes a current situation the author claims is already a *
- ✅ `faithful_paraphrase` — "все время до этих самых переговоров может быть (и скорее всего будет) временем весьма ожесточенных действий сторон"
  - *This is a valid prediction: the author forecasts that the period until the announced November peace negotiations will most likely be a time of intensified military actions by both sides. It is future-*
  *Opus каже missed:*
  - 🔍 "Это сковывание резервов российской группировки "Север", которые могли быть использованы против нас в Харьковской, Луганской областях или в той же Сумской."
    - *No — this is an analysis of the present purpose of the operation, not a prediction about a future verifiable event.*

**Sonnet 4.6** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "несмотря на анонс ноябрьский переговоров о мире, все время до этих самых переговоров может быть (и скорее всего будет) временем весьма ожесточенных действий сторон"
    - *This is a prediction that the period leading up to the announced November peace negotiations will most likely see intensified military actions by both*

---

### `O_Arestovich_official_1779` — gold `YES` — 2022-04-01

> Свежий эфир на [ФЕЙГИН LIVE](https://youtu.be/T1zjCAtHRN4). Обсудили такие темы:**  ** 01:35 Первая интрига: обвал и отступление из-под Киева;  03:04 Северо-западное направление: освобождены Буча, Гостомель, Ирпень, Бородянка, Иванков;  03:37 Отступили из Чернобыльской зоны. облучённые военные армии…

**Pro Preview** — 2 claims, 2 missed
- ✅ `faithful_paraphrase` — "в ближайшие дни поедут 45 эвакуационных автобусов из Мариуполя"
  - *This is a future event claim about evacuation buses departing Mariupol in the coming days. It is verifiable (did 45 buses leave?), external, and substantive given the siege of Mariupol. The metadata i*
- ✅ `faithful_paraphrase` — "Призыв в апреле–июле в РФ и вероятность направления срочников на войну в Украину (100%)"
  - *The claim that conscripts from the April-July draft will be sent to fight in Ukraine (with 100% probability stated) is a future, verifiable, external, and substantive prediction. The spring conscripti*
  *Opus каже missed:*
  - 🔍 "Перспектива прохода ВСУ до Мариуполя и прорыв блокады вероятна"
    - *This is a prediction that the Ukrainian Armed Forces will likely break through to Mariupol and lift the blockade — a future, verifiable, external, and*
  - 🔍 "могут быть сложности в достижении успехов Москвы в зоне ООС"
    - *This predicts that Moscow may face difficulties achieving success in the JFO zone — a future, verifiable, external military prediction, though somewha*

**Flash Lite** — 3 claims, 0 missed
- ❌ `not_a_prediction` — "Перспектива прохода ВСУ до Мариуполя и прорыв блокады вероятна"
  - *This is a vague assessment of probability ('вероятна') without a concrete verifiable claim. It describes a 'perspective' rather than making a definitive prediction about what will happen.*
- ✅ `faithful_paraphrase` — "в ближайшие дни поедут 45 эвакуационных автобусов из Мариуполя"
  - *This is a concrete, verifiable prediction about a specific near-future event (45 evacuation buses from Mariupol in the coming days). It is presented as an outcome of negotiations and is faithfully ext*
- ✅ `faithful_paraphrase` — "Призыв в апреле–июле в РФ и вероятность направления срочников на войну в Украину (100%)"
  - *This is a concrete prediction with a stated 100% probability that conscripts from the April-July draft in Russia will be sent to fight in Ukraine. It is verifiable and faithfully extracted from the po*

**DeepSeek V3.1** — 5 claims, 0 missed
- ❌ `not_a_prediction` — "Начинается ожидаемая 5 суток военная операция"
  - *This describes a military operation that is beginning now (present tense 'начинается'), referring to the current situation around Izyum. It's a description of an ongoing event, not a prediction about *
- ✅ `faithful_paraphrase` — "Перспектива прохода ВСУ до Мариуполя и прорыв блокады вероятна"
  - *This is a prediction that the Ukrainian Armed Forces will likely break through to Mariupol and lift the blockade. It refers to a future event with a verifiable outcome (did the blockade get broken or *
- ✅ `faithful_paraphrase` — "в ближайшие дни поедут 45 эвакуационных автобусов из Мариуполя"
  - *This is a concrete prediction about 45 evacuation buses departing Mariupol in the coming days, which is verifiable. It's faithfully extracted from the post's description of negotiation outcomes.*
- ✅ `faithful_paraphrase` — "Призыв в апреле–июле в РФ и вероятность направления срочников на войну в Украину (100%)"
  - *This predicts with 100% certainty that Russian conscripts from the April-July draft will be sent to fight in Ukraine. This is a future, verifiable, substantive prediction about military policy. The ex*
- ❌ `not_a_prediction` — "Как будет происходить смена путинского режима"
  - *This is a topic heading ('How the change of Putin's regime will happen') describing a discussion topic, not a concrete prediction with a verifiable outcome.*

**Sonnet 4.6** — 0 claims, 3 missed
  *Opus каже missed:*
  - 🔍 "Перспектива прохода ВСУ до Мариуполя и прорыв блокады вероятна"
    - *This is a prediction that Ukrainian forces will likely break through to Mariupol and lift the blockade — a future military event with a verifiable out*
  - 🔍 "в ближайшие дни поедут 45 эвакуационных автобусов из Мариуполя"
    - *This predicts a specific near-term event (45 evacuation buses departing Mariupol) that can be verified as having happened or not.*
  - 🔍 "Призыв в апреле–июле в РФ и вероятность направления срочников на войну в Украину (100%)"
    - *This predicts with stated 100% certainty that Russian conscripts from the April-July draft will be sent to fight in Ukraine — a verifiable future mili*

---

### `O_Arestovich_official_6937` — gold `YES` — 2025-02-18

> - Когда звучит слово «Запад», то стоит понимать, что он очень разный.  Долгое время на Западе доминировал левацкий тренд, который сейчас проигрывает.  ЕС, куда мы так отчаянно стремимся, смог построить свою социальную и политическую систему только под зонтиком безопасности США.  Вместо трат на оборо…

**Pro Preview** — 3 claims, 2 missed
- ✅ `faithful_paraphrase` — "Американская и российская стороны нарабатывают соглашения, которые утвердят Путин и Трамп на личной встрече."
  - *This is a near-verbatim quote from the post. It contains a verifiable prediction: that Putin and Trump will personally meet and approve agreements being worked out by the US and Russian sides. This is*
- ✅ `exact_match` — "Украину поставят перед фактом соглашений и немного даже позволят что-то дополнить, но мнение Украины не будет определяющем в этих соглашениях по прекращению огня."
  - *This is a verbatim quote from the post. It predicts that Ukraine will be presented with a fait accompli regarding ceasefire agreements and will not have a determining voice. This is a future-oriented,*
- ❌ `not_a_prediction` — "В ближайшие недели мы будем наблюдать последние недели агонии действующей власти."
  - *This is a vague rhetorical statement without concrete verifiable criteria. 'Agony of the current government' is subjective and metaphorical — there's no clear condition that a fact-checker could objec*
  *Opus каже missed:*
  - 🔍 "Трамп демонстрирует жесткое намерение прекратить боевые действия в Украине до конца апреля."
    - *This predicts a specific outcome (cessation of hostilities in Ukraine) with a specific deadline (end of April), which is verifiable and substantive.*
  - 🔍 "Настанет время, когда не будут гибнуть солдаты на фронте, на улицах украинских городов не будут людей избивать и заталкивать в бусики, начнется мирный процесс и подготовка к выбора"
    - *This predicts a ceasefire, end of forced mobilization practices, start of a peace process, and preparation for elections in Ukraine — concrete verifia*

**Flash Lite** — 4 claims, 3 missed
- ❌ `not_a_prediction` — "Трамп демонстрирует жесткое намерение прекратить боевые действия в Украине до конца апреля."
  - *This describes Trump's current demonstrated intention ('демонстрирует жесткое намерение'), which is a present-tense assessment of his posture, not a prediction of a future outcome. It doesn't say host*
- ✅ `faithful_paraphrase` — "Американская и российская стороны нарабатывают соглашения, которые утвердят Путин и Трамп на личной встрече."
  - *This is a verbatim quote from the post. It contains a future-oriented, verifiable prediction: that Putin and Trump will approve agreements at a personal meeting. The metadata is reasonable (no specifi*
- ✅ `exact_match` — "Украину поставят перед фактом соглашений и немного даже позволят что-то дополнить, но мнение Украины не будет определяющем в этих соглашениях по прекращению огня."
  - *This is a near-verbatim quote from the post and constitutes a valid prediction about Ukraine's role in ceasefire agreements — a future, verifiable, external, substantive claim. Metadata is correct.*
- ✅ `exact_match` — "начнется мирный процесс и подготовка к выборам, на которых уже украинцы будет решать свою дальнейшую судьбу."
  - *This is a near-verbatim quote from the post predicting a future peace process and election preparation in Ukraine. It is verifiable, external, and substantive. Metadata is acceptable.*
  *Opus каже missed:*
  - 🔍 "В ближайшие недели мы будем наблюдать последние недели агонии действующей власти."
    - *This predicts that the current Ukrainian government will be in its final weeks of power in the near term — a future, verifiable, external, substantive*
  - 🔍 "Политический итог будет плохим для них, но хорошим для Украины."
    - *This predicts that the political outcome will be bad for the current authorities but good for Ukraine — a future, verifiable (at least the 'bad for th*
  - 🔍 "Настанет время, когда не будут гибнуть солдаты на фронте, на улицах украинских городов не будут людей избивать и заталкивать в бусики"
    - *This predicts a future cessation of combat deaths and an end to forced mobilization practices on Ukrainian streets — verifiable, external, and substan*

**DeepSeek V3.1** — 6 claims, 0 missed
- ✅ `faithful_paraphrase` — "Трамп демонструє жесткое намерение прекратить боевые действия в Украине до конца апреля."
  - *This is a close paraphrase of 'Трамп демонстрирует жесткое намерение прекратить боевые действия в Украине до конца апреля.' It is a valid prediction: future event (ceasefire by end of April), verifiab*
- ✅ `exact_match` — "Американская и российская стороны нарабатывают соглашения, которые утвердят Путин и Трамп на личной встрече."
  - *This is a near-verbatim quote from the post. The claim that Putin and Trump will approve agreements at a personal meeting is a future, verifiable, external, and substantive prediction. Metadata is acc*
- ✅ `exact_match` — "Украину поставят перед фактом соглашений и немного даже позволят что-то дополнить, но мнение Украины не будет определяющем в этих соглашениях по прекращению огня."
  - *Near-verbatim quote from the post. This is a valid prediction about Ukraine's role in ceasefire negotiations — future, verifiable (Ukraine's participation level can be assessed), external, and substan*
- ❌ `not_a_prediction` — "В ближайшие недели мы будем наблюдать последние недели агонии действующей власти."
  - *This is a vague rhetorical statement without concrete verifiable criteria. What constitutes 'agony of the current government'? There's no specific measurable outcome — it falls under category D (vague*
- ❌ `not_a_prediction` — "Политический итог будет плохим для них, но хорошим для Украины."
  - *This is a vague evaluative statement without any concrete verifiable outcome. 'Bad for them, good for Ukraine' has no measurable criteria — falls under category D.*
- ❌ `not_a_prediction` — "Настанет время, когда не будут гибнуть солдаты на фронте, на улицах украинских городов не будут людей избивать и заталкивать в бусики, начнется мирный процесс и подготовка к выборам, на которых уже ук"
  - *This is a vague aspirational/rhetorical statement with no timeframe ('настанет время' = 'a time will come'). It reads as a slogan or hopeful declaration rather than a concrete prediction with verifiab*

**Sonnet 4.6** — 6 claims, 0 missed
- ✅ `faithful_paraphrase` — "Трамп демонстрирует жесткое намерение прекратить боевые действия в Украине до конца апреля."
  - *This is a near-verbatim quote from the post. It is a prediction about Trump's intention to end hostilities by end of April 2025, which is future, verifiable, external, and substantive. Metadata is cor*
- ✅ `exact_match` — "Американская и российская стороны нарабатывают соглашения, которые утвердят Путин и Трамп на личной встрече."
  - *This is a verbatim quote from the post. The first part ('нарабатывают соглашения') describes a present process, but the key predictive element is that Putin and Trump will approve these agreements at *
- ✅ `exact_match` — "Украину поставят перед фактом соглашений и немного даже позволят что-то дополнить, но мнение Украины не будет определяющем в этих соглашениях по прекращению огня."
  - *Verbatim quote from the post. This is a prediction about Ukraine's role in future ceasefire agreements — future, verifiable (Ukraine's participation level can be assessed), external, and substantive.*
- ❌ `not_a_prediction` — "В ближайшие недели мы будем наблюдать последние недели агонии действующей власти."
  - *This is a vague rhetorical statement without concrete verifiable criteria. 'Agony of the current government' has no measurable outcome — what exactly constitutes 'agony'? This falls under category D (*
- ❌ `not_a_prediction` — "Политический итог будет плохим для них, но хорошим для Украины."
  - *This is a vague evaluative statement without concrete verifiable criteria. 'Bad for them, good for Ukraine' is subjective and not objectively measurable. Falls under category D.*
- ❌ `not_a_prediction` — "Настанет время, когда не будут гибнуть солдаты на фронте, на улицах украинских городов не будут людей избивать и заталкивать в бусики, начнется мирный процесс и подготовка к выборам, на которых уже ук"
  - *This is a vague aspirational/rhetorical statement with no timeframe ('настанет время'). It describes an idealized future without concrete timing or conditions, making it unverifiable in practice. Fall*

---

### `O_Arestovich_official_3490` — gold `YES` — 2023-04-05

> В эфире UKRLIFE TV с Людмилой Немирей обсудили сложившуюся международную обстановку и развеяли несколько мифов, в частности китайский.  Американские аналитики и военные эксперты заявляют о «страшной китайской угрозе». Это поддерживают их коллеги по всему миру.  Дело в том, что если эти аналитики и э…

**Pro Preview** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "Считаю, что он будет действовать так дальше."
    - *This predicts that China will continue to rely on soft power rather than military force in its foreign policy — a future-oriented, verifiable, substan*
  - 🔍 "разговоров о вторжении Китая на Тайвань в ближайшие месяцы и годы будет много"
    - *This predicts that there will be extensive discussion/rhetoric about a Chinese invasion of Taiwan in the coming months and years (implying it won't ac*

**Flash Lite** — 2 claims, 1 missed
- ❌ `not_a_prediction` — "Вторжение на Тайвань бы немедленно вызвало санкции Запада, которы бы сложили китайскую экспортно ориентированную экономику как домик из карт."
  - *This is a conditional/hypothetical statement ('if China invaded Taiwan, then X would happen'), not a prediction that something will happen. It describes a hypothetical scenario to argue why China won'*
- ✅ `faithful_paraphrase` — "Считаю, что он [Китай] будет действовать так дальше [добиваться успехов во внешней политике мягкой силой]."
  - *This is a valid prediction about China's future foreign policy behavior — that China will continue to rely on soft power rather than military force. It is future-oriented, verifiable (one can check wh*
  *Opus каже missed:*
  - 🔍 "Но разговоров о вторжении Китая на Тайвань в ближайшие месяцы и годы будет много."
    - *This is a concrete, future-oriented, verifiable prediction that discourse about a Chinese invasion of Taiwan will continue to be prominent in the comi*

**DeepSeek V3.1** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "Считаю, что он будет действовать так дальше."
    - *This predicts that China will continue to rely on soft power rather than military force in its foreign policy — a future-oriented, verifiable, substan*
  - 🔍 "разговоров о вторжении Китая на Тайвань в ближайшие месяцы и годы будет много"
    - *This predicts that there will be extensive discussion/rhetoric about a Chinese invasion of Taiwan in the coming months and years (implying it won't ac*

**Sonnet 4.6** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "Считаю, что он будет действовать так дальше."
    - *This predicts that China will continue to rely on soft power rather than military force in its foreign policy — a future-oriented, verifiable, substan*
  - 🔍 "разговоров о вторжении Китая на Тайвань в ближайшие месяцы и годы будет много"
    - *This predicts that there will be extensive discussion/rhetoric about a Chinese invasion of Taiwan in the coming months and years (implying no actual i*

---

### `O_Arestovich_official_2899` — gold `YES` — 2022-11-15

> - Не ждите яростного военного ответа НАТО по российским целям.  Все зависит от того, как НАТО ответит на вопрос:  - был ли удар преднамеренным или нет?  Конечно, если он был преднамеренным, то это повод к консультациям о применении Пятой статьи - о коллективной обороне.   Заметьте - не к войне, а к…

**Pro Preview** — 2 claims, 1 missed
- ✅ `faithful_paraphrase` — "Не ждите яростного военного ответа НАТО по российским целям."
  - *This is a valid prediction about a future event — that NATO will not respond with a fierce military strike against Russian targets following the Poland incident. It is verifiable (did NATO launch mili*
- ✅ `faithful_paraphrase` — "Отдаленные последствия, в виде усиления санкций и расширения поставок оружия нам, да, более вероятны."
  - *This is a prediction that the long-term consequences of the incident will likely include strengthened sanctions and expanded weapons deliveries to Ukraine. It is future-oriented, verifiable, external,*
  *Opus каже missed:*
  - 🔍 "Если вердикт будет «непреднамеренный удар» то это, скорее всего, суд, компенсации."
    - *This is a conditional prediction about the likely outcome (court proceedings and compensation) if the strike is deemed unintentional — a verifiable fu*

**Flash Lite** — 1 claims, 2 missed
- ✅ `faithful_paraphrase` — "Отдаленные последствия, в виде усиления санкций и расширения поставок оружия нам, да, более вероятны."
  - *This is a prediction about future consequences of the Poland missile incident — strengthened sanctions and expanded weapons deliveries to Ukraine. It refers to a future state, is verifiable (did sanct*
  *Opus каже missed:*
  - 🔍 "Не ждите яростного военного ответа НАТО по российским целям."
    - *This is a concrete prediction that NATO will not respond with a military strike against Russian targets — a verifiable future outcome regarding the Po*
  - 🔍 "Если вердикт будет «непреднамеренный удар» то это, скорее всего, суд, компенсации."
    - *This is a conditional but concrete prediction that if the strike is deemed unintentional, the outcome will be legal proceedings and compensation — a v*

**DeepSeek V3.1** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "Если вердикт будет «непреднамеренный удар» то это, скорее всего, суд, компенсации."
    - *This is a conditional prediction about the concrete consequences (court proceedings, compensations) if the strike is deemed unintentional — verifiable*
  - 🔍 "Отдаленные последствия, в виде усиления санкций и расширения поставок оружия нам, да, более вероятны."
    - *This predicts that the incident will likely lead to strengthened sanctions and expanded weapons deliveries to Ukraine — a verifiable future outcome.*

**Sonnet 4.6** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "Если вердикт будет «непреднамеренный удар» то это, скорее всего, суд, компенсации."
    - *This is a conditional prediction about the likely outcome (court proceedings, compensations) if the strike is deemed unintentional — a verifiable futu*
  - 🔍 "Отдаленные последствия, в виде усиления санкций и расширения поставок оружия нам, да, более вероятны."
    - *This predicts that the incident will likely lead to strengthened sanctions and expanded weapons deliveries to Ukraine — a concrete, verifiable future *

---

### `O_Arestovich_official_7331` — gold `YES` — 2025-06-24

> - Через 10-15 лет привычного мира не будет.  Сменятся границы и общий мировой уклад.  На протяжении этих 10-15 лет будут идти войны разной интенсивности в разных уголках земного шара.  Восточная Европа - один из таких центров разлома.  Невозможен возврат к предыдущим границам Украины и к прежнему ук…

**Pro Preview** — 3 claims, 1 missed
- ❌ `not_a_prediction` — "Через 10-15 лет привычного мира не будет. Сменятся границы и общий мировой уклад. На протяжении этих 10-15 лет будут идти войны разной интенсивности в разных уголках земного шара."
  - *While this is future-oriented, it is extremely vague — 'привычного мира не будет', 'сменятся границы', 'войны разной интенсивности в разных уголках' lack concrete verifiable criteria. An impartial fac*
- ✅ `faithful_paraphrase` — "Невозможен возврат к предыдущим границам Украины и к прежнему укладу жизни."
  - *This is a future-oriented claim with a verifiable outcome — Ukraine will not return to its pre-war borders. It is substantive and externally meaningful. The extraction is faithful to the post text, an*
- ❌ `not_a_prediction` — "Таким образом, Украина повторяет свой привычный сценарий, двигаясь к Руине. И в ближайшие 10 лет повторит его, закончив с анти-проектом - в третий раз за сто лет."
  - *This uses a historical metaphor ('Руина', 'анти-проект') without concrete verifiable criteria. What exactly constitutes 'закончив с анти-проектом' or 'Руина' in modern terms? An impartial fact-checker*
  *Opus каже missed:*
  - 🔍 "Может быть, будет три Украины."
    - *This is a concrete, future-oriented, verifiable prediction that Ukraine may split into three separate entities — an impartial observer could check whe*

**Flash Lite** — 2 claims, 3 missed
- ❌ `not_a_prediction` — "Может быть, будет три Украины."
  - *The phrase 'может быть' (maybe) makes this extremely vague and hedged. There is no timeframe and no concrete verifiable condition — it's speculative musing rather than a prediction with a checkable ou*
- ❌ `not_a_prediction` — "И в ближайшие 10 лет повторит его [сценарий Руины], закончив с анти-проектом - в третий раз за сто лет."
  - *While it has a timeframe (~10 years), the claim uses vague metaphorical language ('сценарий Руины', 'анти-проект') without a concrete, objectively verifiable outcome. What exactly constitutes 'finishi*
  *Opus каже missed:*
  - 🔍 "Через 10-15 лет привычного мира не будет. Сменятся границы и общий мировой уклад."
    - *A concrete prediction with a timeframe (10-15 years) that world borders and the global order will change significantly — verifiable by checking whethe*
  - 🔍 "На протяжении этих 10-15 лет будут идти войны разной интенсивности в разных уголках земного шара."
    - *Predicts ongoing wars of varying intensity across the globe over the next 10-15 years — verifiable by tracking armed conflicts worldwide through that *
  - 🔍 "На сегодня РФ выполняет политическую задачу - взятие под контроль территорий тех областей, которые она записала в свою Конституцию."
    - *This is actually a present-state assessment, not a future prediction — on reflection, this does NOT qualify.*

**DeepSeek V3.1** — 6 claims, 1 missed
- ❌ `not_a_prediction` — "Через 10-15 лет привычного мира не будет."
  - *This is a vague, sweeping declaration without concrete verifiable criteria. What constitutes 'привычный мир' is undefined and cannot be objectively checked as true or false.*
- ❌ `not_a_prediction` — "На протяжении этих 10-15 лет будут идти войны разной интенсивности в разных уголках земного шара."
  - *This is essentially a truism — wars of varying intensity are always occurring somewhere on the globe. It lacks specificity and is non-substantive since it's virtually guaranteed to be true regardless.*
- ❌ `not_a_prediction` — "Невозможен возврат к предыдущим границам Украины и к прежнему укладу жизни."
  - *While this is future-oriented and about external events, it is vague ('прежний уклад жизни') and partly a present-tense assessment. The border claim is somewhat verifiable but 'уклад жизни' is not. Ov*
- ✅ `faithful_paraphrase` — "Может быть, будет три Украины."
  - *This is a speculative but verifiable prediction about Ukraine splitting into three entities. The hedging 'может быть' is present in the original. It refers to a future external event with a concrete v*
- ❌ `not_a_prediction` — "Украина повторяет свой привычный сценарий, двигаясь к Руине."
  - *This is a present-tense rhetorical/analytical assessment using a historical metaphor ('Руїна'). It describes a current trajectory rather than making a concrete future prediction with verifiable criter*
- ✅ `faithful_paraphrase` — "И в ближайшие 10 лет повторит его, закончив с анти-проектом - в третий раз за сто лет."
  - *This is a future-oriented prediction that Ukraine will cease to exist as a state project within 10 years. While somewhat vague on exact criteria, 'закончив с анти-проектом' implies state failure/colla*
  *Opus каже missed:*
  - 🔍 "Сменятся границы и общий мировой уклад."
    - *This predicts that borders will change globally within 10-15 years, which is a future, verifiable, external, and substantive claim about geopolitical *

**Sonnet 4.6** — 0 claims, 4 missed
  *Opus каже missed:*
  - 🔍 "Через 10-15 лет привычного мира не будет. Сменятся границы и общий мировой уклад."
    - *Predicts that within 10-15 years global borders and world order will fundamentally change — a verifiable future claim about geopolitical transformatio*
  - 🔍 "На протяжении этих 10-15 лет будут идти войны разной интенсивности в разных уголках земного шара."
    - *Predicts ongoing wars of varying intensity across the globe over the next 10-15 years — verifiable by checking whether multiple active conflicts persi*
  - 🔍 "Может быть, будет три Украины."
    - *Predicts Ukraine may split into three separate entities — a concrete, verifiable geopolitical outcome, though hedged with 'может быть'.*
  - 🔍 "И в ближайшие 10 лет повторит его, закончив с анти-проектом - в третий раз за сто лет."
    - *Predicts Ukraine will end as a state project ('Руина') within the next 10 years — a concrete future geopolitical outcome that is verifiable.*

---

### `O_Arestovich_official_7318` — gold `YES` — 2025-06-15

> - В беседе с Константином Боровым говорили о стратегиях мировых игроков.   Израиль имеет четкие планы относительно иранской ядерной программы - ее не должно существовать.  Лидеры Ирана не раз называли целью политики страны - уничтожение Израиля.  Израиль готовил операцию 20 лет и нанес удар, к котор…

**Pro Preview** — 1 claims, 2 missed
- ❌ `not_a_prediction` — "Реальных гарантий безопасности Украине (которыми является только готовность к прямому военному столкновению с РФ) Запад никогда не даст, он себе их дать не может."
  - *This is a present-tense analytical assessment/rhetorical declaration about the West's fundamental inability/unwillingness, not a concrete future event with a verifiable outcome. 'Никогда' makes it unf*
  *Opus каже missed:*
  - 🔍 "Его цели на ближайшие 10-15 лет: - разгром Украины как прокси-силы Запада; - реализация ультиматума Западу - НАТО за границы 97-го года, - создание нового союза в лице трёх славянс"
    - *This is a concrete prediction about Russia's strategic goals over the next 10-15 years with verifiable outcomes (defeat of Ukraine as Western proxy, N*
  - 🔍 "Возможны боестолкновения в странах Балтии, гибридные и военные операции в Балтийском море."
    - *This is a forward-looking claim about possible military clashes in the Baltics and hybrid/military operations in the Baltic Sea — a concrete, verifiab*

**Flash Lite** — 1 claims, 2 missed
- ❌ `not_a_prediction` — "Возможны боестолкновения в странах Балтии, гибридные и военные операции в Балтийском море."
  - *The word 'возможны' (possible) makes this extremely vague — it states that clashes are 'possible' without any timeframe or concrete commitment. This is speculative hedging rather than a verifiable pre*
  *Opus каже missed:*
  - 🔍 "Реальных гарантий безопасности Украине... Запад никогда не даст, он себе их дать не может."
    - *This is a concrete forward-looking claim that the West will never provide real security guarantees (defined as readiness for direct military confronta*
  - 🔍 "Его цели на ближайшие 10-15 лет: разгром Украины как прокси-силы Запада; реализация ультиматума Западу - НАТО за границы 97-го года, создание нового союза в лице трёх славянских на"
    - *This describes Russia's goals for the next 10-15 years as concrete intended outcomes (defeat of Ukraine as proxy, NATO rollback, Slavic union) — verif*

**DeepSeek V3.1** — 6 claims, 0 missed
- ❌ `not_a_prediction` — "Россия может выиграть в сухопутном столкновении с объединенным Западом, если сотни тысяч мужиков с автоматами и дронами двинутся в сторону стран ЕС — остановить их будет некому и нечем."
  - *This is a present-tense assessment of military capabilities ('могут выиграть', 'остановить будет некому'), not a prediction of a future event. It describes a hypothetical scenario and current balance *
- ❌ `not_a_prediction` — "Западные страны могут выиграть в воздушном столкновении с РФ, но в сухопутном — нет."
  - *This is a present-tense assessment of military capabilities attributed to military specialists' calculations. It describes the current state of affairs, not a future event with a verifiable outcome.*
- ❌ `not_a_prediction` — "Европейские политики ни в каком варианте не рассматривают вариант прямого вооруженного конфликта с РФ по собственной инициативе."
  - *This is a present-tense assessment of European politicians' current stance, not a prediction about a future event. It describes what they currently think/do, not what will happen.*
- ✅ `faithful_paraphrase` — "Реальных гарантий безопасности Украине (которыми является только готовность к прямому военному столкновению с РФ) Запад никогда не даст."
  - *This is a near-verbatim quote from the post making a forward-looking claim ('никогда не даст') about the West never providing real security guarantees to Ukraine. It is future-oriented, verifiable (if*
- ✅ `faithful_paraphrase` — "Возможны боестолкновения в странах Балтии, гибридные и военные операции в Балтийском море."
  - *This is a near-verbatim quote from the post predicting possible military clashes in the Baltics and hybrid/military operations in the Baltic Sea. It is future-oriented, verifiable, external, and subst*
- ❌ `not_a_prediction` — "Цели российского руководства на ближайшие 10-15 лет: разгром Украины как прокси-силы Запада; реализация ультиматума Западу — НАТО за границы 97-го года; создание нового союза в лице трёх славянских на"
  - *This describes Russia's stated/attributed goals and intentions, not a prediction that these goals will be achieved. It is an analysis of current strategic aims, not a forecast of future outcomes.*

**Sonnet 4.6** — 0 claims, 3 missed
  *Opus каже missed:*
  - 🔍 "Его цели на ближайшие 10-15 лет: - разгром Украины как прокси-силы Запада; - реализация ультиматума Западу - НАТО за границы 97-го года, - создание нового союза в лице трёх славянс"
    - *This describes concrete goals attributed to Russian leadership over the next 10-15 years as things they will pursue — verifiable future outcomes (Ukra*
  - 🔍 "Возможны боестолкновения в странах Балтии, гибридные и военные операции в Балтийском море."
    - *This is a prediction of possible future military clashes in the Baltics and hybrid/military operations in the Baltic Sea — a verifiable, substantive g*
  - 🔍 "Реальных гарантий безопасности Украине... Запад никогда не даст, он себе их дать не может."
    - *This predicts that the West will never provide real security guarantees to Ukraine (defined as readiness for direct military confrontation with Russia*

---

### `O_Arestovich_official_7462` — gold `YES` — 2025-08-19

> - Ключевой задачей Украины на сегодня во всех этих аляскинских историях является сохранение политической независимости в перспективе.   При всей общности символического капитала с Россией и Беларусью, на лицо - фундаментальные расхождения в представлениях о правах и свободах и о должном и возможном…

**Pro Preview** — 1 claims, 0 missed
- ✅ `faithful_paraphrase` — "Если это не сделать добровольно, смена проекта (основных направлений внешней и внутренней политики и стратегии развития) произойдет насильственно. Сроки - 10-15 лет. Ценой будет утрата политической не"
  - *This is a near-verbatim extraction of a conditional prediction from the post: if Ukraine doesn't voluntarily change its strategic orientation, within 10-15 years it will lose political independence an*

**Flash Lite** — 2 claims, 1 missed
- ✅ `faithful_paraphrase` — "Если это не сделать добровольно, смена проекта (основных направлений внешней и внутренней политики и стратегии развития) произойдет насильственно."
  - *This is a conditional prediction about Ukraine's future: if it doesn't voluntarily change its strategic direction, the change will happen by force within 10-15 years. It refers to a future external ev*
- ✅ `faithful_paraphrase` — "Ценой будет утрата политической независимости и вместо Украины здесь будет федеральный округ «Малороссия»"
  - *This is a conditional prediction (contingent on Ukraine not changing course) about Ukraine losing political independence and becoming a Russian federal district 'Malorossiya' within 10-15 years. It is*
  *Opus каже missed:*
  - 🔍 "отказ коллективного Запада в единстве символического капитала с Украиной (нас не считают частью Европы и отказали в приеме в ЕС и НАТО)"
    - *No — this is presented as a past/present assessment ('отказали'), not a future prediction. Would not qualify.*

**DeepSeek V3.1** — 2 claims, 1 missed
- ❌ `not_a_prediction` — "Если это не сделать добровольно, смена проекта (основных направлений внешней и внутренней политики и стратегии развития) произойдет насильственно."
  - *This is a conditional normative/rhetorical statement ('if X is not done, then Y will happen') that functions as a warning or argument for the author's preferred policy. It lacks concrete verifiable cr*
- ❌ `not_a_prediction` — "Ценой будет утрата политической независимости и вместо Украины здесь будет федеральный округ «Малороссия» - со всеми вытекающими для дискуссий о правах, свободах о особенностях последствиями."
  - *This is a conditional consequence of the previous statement (if Ukraine doesn't change course voluntarily). While it describes a concrete outcome (Ukraine becoming a federal district 'Malorossiya'), i*
  *Opus каже missed:*
  - 🔍 "Сроки - 10-15 лет."
    - *Combined with the preceding context about forced project change and Ukraine becoming a federal district 'Malorossiya', this gives a concrete timeframe*

**Sonnet 4.6** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "Если это не сделать добровольно, смена проекта (основных направлений внешней и внутренней политики и стратегии развития) произойдет насильственно. Сроки - 10-15 лет. Ценой будет ут"
    - *This is a concrete prediction with a timeframe (10-15 years): if Ukraine doesn't voluntarily change its strategic orientation, it will lose political *

---

### `O_Arestovich_official_4338` — gold `YES` — 2023-09-12

> На встрече Путина и Ким Чен Ына обязательно будет поднят вопрос о поставках боеприпасов для российской армии, которые ей очень нужны для продолжения войны.  Скорее все поставки будут, открытым является вопрос количества.  Даже существенное количество не изменит радикально ход войны, а может лишь зам…

**Pro Preview** — 3 claims, 2 missed
- ❌ `not_a_prediction` — "На встрече Путина и Ким Чен Ына обязательно будет поднят вопрос о поставках боеприпасов для российской армии, которые ей очень нужны для продолжения войны."
  - *This is essentially a statement of the obvious — the entire purpose of the Putin-Kim meeting was widely known to be about arms/ammunition. The outcome is not genuinely uncertain; it's a near-certainty*
- ✅ `exact_match` — "Скорее все поставки будут, открытым является вопрос количества."
  - *This is a valid prediction that North Korea will supply ammunition to Russia. It refers to a future event, is verifiable (did DPRK supply ammo to Russia?), is external, and is substantive — at the tim*
- ✅ `exact_match` — "В случае передачи боеприпасов армии РФ, нам симметрично будут увеличены поставки вооружений и техники с возможным широким расширением номенклатуры."
  - *This is a conditional but verifiable prediction: if DPRK supplies ammo to Russia, Western partners will increase arms supplies to Ukraine with a possible broadening of weapon types. It's future, verif*
  *Opus каже missed:*
  - 🔍 "Даже существенное количество не изменит радикально ход войны, а может лишь замедлить наше продвижение."
    - *This is a prediction that even substantial DPRK ammunition supplies will not radically change the course of the war but may only slow Ukrainian advanc*
  - 🔍 "За вероятной сделкой может стоять Китай, играя против Запада, что не останется без ответа со стороны наших партнёров."
    - *This predicts that China may be behind the DPRK-Russia deal and that Western partners will respond — the second part ('не останется без ответа') is a *

**Flash Lite** — 1 claims, 3 missed
- ✅ `exact_match` — "В случае передачи боеприпасов армии РФ, нам симметрично будут увеличены поставки вооружений и техники с возможным широким расширением номенклатуры."
  - *This is a near-verbatim quote from the post. It is a conditional prediction about a future event (increased Western arms supplies to Ukraine if North Korea supplies Russia), which is verifiable and su*
  *Opus каже missed:*
  - 🔍 "Скорее все поставки будут, открытым является вопрос количества."
    - *This is a prediction that North Korea will supply ammunition to Russia, which is a future, verifiable, external, and substantive claim.*
  - 🔍 "Даже существенное количество не изменит радикально ход войны, а может лишь замедлить наше продвижение."
    - *This predicts that even substantial North Korean ammunition supplies will not radically change the course of the war, only slow Ukrainian advances — a*
  - 🔍 "За вероятной сделкой может стоять Китай, играя против Запада, что не останется без ответа со стороны наших партнёров."
    - *This predicts that Western partners will respond to China's possible role behind the North Korea-Russia deal — a future, verifiable, and substantive c*

**DeepSeek V3.1** — 5 claims, 0 missed
- ❌ `not_a_prediction` — "На встрече Путина и Ким Чен Ына обязательно будет поднят вопрос о поставках боеприпасов для российской армии"
  - *This is essentially a statement of the obvious — it would be universally expected that ammunition supplies would be discussed at such a meeting. The outcome is not genuinely uncertain or strategically*
- ✅ `exact_match` — "Скорее все поставки будут"
  - *This is a valid prediction that North Korea will supply ammunition to Russia. It is future-oriented, verifiable, external, and substantive. The quote is verbatim from the post.*
- ✅ `exact_match` — "Даже существенное количество не изменит радикально ход войны, а может лишь замедлить наше продвижение"
  - *This is a valid prediction about the impact of North Korean ammunition on the war's course — it claims even substantial quantities won't radically change the war. It is future, verifiable (one can ass*
- ✅ `faithful_paraphrase` — "За вероятной сделкой может стоять Китай, играя против Запада, что не останется без ответа со стороны наших партнёров"
  - *The first part ('может стоять Китай') is speculative analysis, but the second part ('не останется без ответа со стороны наших партнёров') is a prediction that Western partners will respond. Combined, *
- ✅ `exact_match` — "В случае передачи боеприпасов армии РФ, нам симметрично будут увеличены поставки вооружений и техники с возможным широким расширением номенклатуры"
  - *This is a conditional but valid prediction: if Russia receives North Korean ammunition, Ukraine will receive increased weapons supplies with potentially expanded types. It is future, verifiable, exter*

**Sonnet 4.6** — 0 claims, 3 missed
  *Opus каже missed:*
  - 🔍 "Скорее все поставки будут, открытым является вопрос количества."
    - *This predicts that North Korea will supply ammunition to Russia — a future event with a verifiable outcome.*
  - 🔍 "За вероятной сделкой может стоять Китай, играя против Запада, что не останется без ответа со стороны наших партнёров."
    - *This predicts that Western partners will respond to a China-backed NK-Russia arms deal — a verifiable future geopolitical outcome.*
  - 🔍 "В случае передачи боеприпасов армии РФ, нам симметрично будут увеличены поставки вооружений и техники с возможным широким расширением номенклатуры."
    - *This is a conditional prediction that Western arms supplies to Ukraine will increase in volume and variety if Russia receives NK ammunition — verifiab*

---

### `O_Arestovich_official_7416` — gold `YES` — 2025-07-29

> - После начала протестов в Украине многие медийные підпанки, ещё недавно поющие дифирамбы любимому президенту, начали поддерживать протесты и говорить о коррупции в стране.  Это верный признак того, что в Украине произошли тектонические сдвиги, а Зеленский движется в политическое небытие.  Причина э…

**Pro Preview** — 2 claims, 4 missed
- ❌ `not_a_prediction` — "В Украине нет единства, а значит, ситуация с внутренним расколом и региональным сепаратизмом практически неизбежна."
  - *This is a vague rhetorical assertion about an inevitable condition without a concrete verifiable outcome or timeframe. It's more of a present-state analysis ('нет единства') combined with a vague forw*
- ❌ `not_a_prediction` — "Когда Зеленский уйдёт, сразу встанет вопрос о пересмотре того, как страну готовили к войне и как её вели."
  - *This is a conditional rhetorical statement about what will happen 'when Zelensky leaves' — it's vague (what counts as 'the question arising'?), and it's more of a normative/analytical assertion than a*
  *Opus каже missed:*
  - 🔍 "Эта информация нуждается в проверке, но, возможно, вскоре будет обнародована."
    - *Predicts that NABU audio recordings involving Zelensky will be publicly released soon — a concrete, verifiable future event.*
  - 🔍 "Цена мира с Россией - четыре области и Крым."
    - *Predicts that the eventual peace deal will involve ceding four oblasts and Crimea to Russia — a specific, verifiable outcome of future negotiations.*
  - 🔍 "Вопрос с Зеленским решён - сейчас мы наблюдаем его политический финал."
    - *Predicts that Zelensky is in his final political phase and will lose power — a concrete verifiable future political outcome.*
  - 🔍 "В противном случае РФ может использовать политический хаос, чтобы речь шла уже не о четырёх, а о шести, восьми или десяти областях."
    - *Predicts that if political transition is chaotic, Russia will escalate territorial demands beyond four oblasts — a verifiable conditional prediction a*

**Flash Lite** — 6 claims, 4 missed
- ❌ `not_a_prediction` — "Эта информация [аудиозаписи НАБУ] нуждается в проверке, но, возможно, вскоре будет обнародована."
  - *The hedging ('возможно', 'вскоре') makes this too vague to be verifiable — no concrete timeframe or definite claim. It's a speculative possibility, not a prediction with a checkable outcome.*
- ❌ `not_a_prediction` — "Никакие санкции против России не подействуют."
  - *This is a general rhetorical assertion about the ineffectiveness of sanctions — it lacks a specific timeframe or concrete verifiable criterion. It reads as an analytical/normative statement rather tha*
- ✅ `faithful_paraphrase` — "Запад не будет воевать с Россией за Украину"
  - *The post says 'Запад не будет воевать с Россией за Украину - это давно решённый вопрос.' This is a forward-looking claim about Western military non-intervention that is verifiable (either the West ent*
- ✅ `faithful_paraphrase` — "ситуация с внутренним расколом и региональным сепаратизмом практически неизбежна."
  - *The post states 'В Украине нет единства, а значит, ситуация с внутренним расколом и региональным сепаратизмом практически неизбежна.' This is a prediction about future internal fragmentation and separ*
- ❌ `not_a_prediction` — "Если же придут другие [к власти], действия ТЦК, а также запреты на русский язык и церковь будут расследованы, и виновные могут понести наказание."
  - *This is a conditional statement ('если придут другие') describing one of two possible scenarios. The conditional framing and 'могут понести наказание' hedging make it a speculative scenario rather tha*
- ❌ `not_a_prediction` — "Украина вполне может повторить события 1918–1919 годов, когда правительства держались у власти по полгода"
  - *The phrase 'вполне может повторить' expresses a possibility, not a prediction. It's a hedged speculative analogy without a definite claim about what will happen.*
  *Opus каже missed:*
  - 🔍 "Вопрос с Зеленским решён - сейчас мы наблюдаем его политический финал."
    - *This is a concrete prediction that Zelensky's political career is ending, which is verifiable — either he leaves power in the near term or he doesn't.*
  - 🔍 "Цена мира с Россией - четыре области и Крым."
    - *This predicts the specific territorial terms of a future peace deal — verifiable against any eventual agreement.*
  - 🔍 "майданный проект в Украине закрыт"
    - *This is a prediction that the post-Maidan political project in Ukraine is finished, which is a substantive and verifiable claim about Ukraine's politi*
  - 🔍 "В противном случае РФ может использовать политический хаос, чтобы речь шла уже не о четырёх, а о шести, восьми или десяти областях."
    - *This predicts that Russia will exploit political chaos to demand more territory beyond the initial four oblasts and Crimea — verifiable against future*

**DeepSeek V3.1** — 18 claims, 1 missed
- ❌ `not_a_prediction` — "Зеленский движется в политическое небытие"
  - *This is a vague rhetorical assessment of the present situation ('движется') without a concrete verifiable outcome or timeframe. It's more of a present-tense characterization than a specific prediction*
- ✅ `faithful_paraphrase` — "аудиозаписи, которые НАБУ делало в квартире у «кошелька Зеленского» - Тимура Миндича... возможно, вскоре будет обнародована"
  - *This is a prediction that NABU audio recordings from Mindich's apartment may soon be made public. It has a future event, is verifiable, external, and substantive. The hedging ('возможно') is present i*
- ❌ `not_a_prediction` — "Процесс развенчания мифа о Зеленском ускоряется и может достичь пика в ближайшее время"
  - *This is vague — 'может достичь пика в ближайшее время' lacks concrete criteria for what 'peak' means and when. An impartial fact-checker could not objectively confirm or refute this.*
- ❌ `not_a_prediction` — "Никакие санкции против России не подействуют"
  - *This is a broad analytical assertion without a specific timeframe or concrete verifiable criterion. 'Подействуют' is too vague — by what measure? It's more of a rhetorical declaration.*
- ✅ `faithful_paraphrase` — "Россия сможет продолжить боевые действия под любыми санкциями"
  - *This is a prediction that Russia will be able to continue military operations regardless of any sanctions imposed. It is future-oriented, verifiable (Russia either continues fighting or is forced to s*
- ✅ `exact_match` — "Запад не будет воевать с Россией за Украину"
  - *This is a concrete, verifiable prediction about Western countries not entering direct military conflict with Russia over Ukraine. It is future-oriented, external, and substantive.*
- ✅ `faithful_paraphrase` — "Цена мира с Россией - четыре области и Крым"
  - *This is a prediction about the terms of a future peace deal — that it will involve ceding four oblasts and Crimea. It is verifiable, future-oriented, external, and substantive.*
- ✅ `faithful_paraphrase` — "Вопрос с Зеленским решён - сейчас мы наблюдаем его политический финал"
  - *This predicts that Zelensky's political career is ending. It is future-oriented (his departure from power), verifiable, external, and substantive.*
- ✅ `faithful_paraphrase` — "ситуация с внутренним расколом и региональным сепаратизмом практически неизбежна"
  - *This predicts internal division and regional separatism in Ukraine as nearly inevitable. It is future-oriented, verifiable (separatist movements either emerge or don't), external, and substantive.*
- ✅ `faithful_paraphrase` — "Когда Зеленский уйдёт, сразу встанет вопрос о пересмотре того, как страну готовили к войне и как её вели"
  - *This is a conditional prediction about what will happen after Zelensky leaves power — a review of war preparation and conduct. It is verifiable, future-oriented, external, and substantive.*
- ❌ `not_a_prediction` — "Если к власти придут националисты, окажется, что «давили» недостаточно сильно - и гайки закрутят по полной"
  - *This is a conditional scenario ('если придут националисты') with vague outcome ('гайки закрутят по полной'). The outcome is too vague and metaphorical to be objectively verified.*
- ✅ `faithful_paraphrase` — "Если же придут другие, действия ТЦК, а также запреты на русский язык и церковь будут расследованы, и виновные могут понести наказание"
  - *This is a conditional prediction with a concrete verifiable outcome — investigations into TCC actions and language/church bans if non-nationalists come to power. The conditional framing is preserved f*
- ✅ `exact_match` — "Украина вполне может повторить события 1918–1919 годов, когда правительства держались у власти по полгода"
  - *This predicts Ukraine may experience rapid government turnover similar to 1918-1919. It is future-oriented, verifiable, external, and substantive, though hedged with 'вполне может'.*
- ❌ `not_a_prediction` — "майданный проект в Украине закрыт"
  - *This is a present-tense assessment/declaration about the current state of affairs rather than a prediction about a future event. 'Закрыт' is stated as already accomplished.*
- ❌ `not_a_prediction` — "В скором времени мы это увидим"
  - *This is a vague forward-looking statement without any concrete verifiable content. It fails criterion 2 — there is no specific outcome to check.*
- ✅ `exact_match` — "Мировое сообщество, несомненно, будет стремиться к тому, чтобы транзит власти в Украине прошёл максимально безболезненно"
  - *This predicts that the international community will work to ensure a smooth power transition in Ukraine. It is future-oriented, verifiable (observable diplomatic actions), external, and substantive.*
- ❌ `not_a_prediction` — "России нужен спокойный переход власти от Зеленского к кому бы то ни было, чтобы этот «кто-то другой» подписал передачу четырёх областей и Крыма"
  - *This is an analytical statement about Russia's motivations/needs, not a prediction about a future event. It describes why Russia wants something, not what will happen.*
- ✅ `faithful_paraphrase` — "В противном случае РФ может использовать политический хаос, чтобы речь шла уже не о четырёх, а о шести, восьми или десяти областях"
  - *This is a conditional prediction that if there is political chaos, Russia may escalate demands from four oblasts to six, eight, or ten. It is future-oriented, verifiable, external, and substantive.*
  *Opus каже missed:*
  - 🔍 "Трамп начал ускорять процесс перемирия"
    - *While partly present-tense, in context it implies Trump will push for a ceasefire — however, on reflection this describes a current action ('начал'), *

**Sonnet 4.6** — 0 claims, 7 missed
  *Opus каже missed:*
  - 🔍 "Эта информация нуждается в проверке, но, возможно, вскоре будет обнародована."
    - *Predicts that NABU audio recordings involving Zelensky will be publicly released soon — a future, verifiable, external, substantive event.*
  - 🔍 "Процесс развенчания мифа о Зеленском ускоряется и может достичь пика в ближайшее время."
    - *Predicts that negative media coverage of Zelensky will peak soon — somewhat vague but borderline; on reflection this is too vague ('может', 'в ближайш*
  - 🔍 "Цена мира с Россией - четыре области и Крым."
    - *Predicts the specific territorial terms of a future peace deal — verifiable by checking eventual agreement terms.*
  - 🔍 "Вопрос с Зеленским решён - сейчас мы наблюдаем его политический финал."
    - *Predicts Zelensky's imminent political end/removal from power — a future, verifiable, external, substantive claim.*
  - 🔍 "ситуация с внутренним расколом и региональным сепаратизмом практически неизбежна"
    - *Predicts that Ukraine will face internal fragmentation and regional separatism — a future, verifiable, external, substantive geopolitical prediction.*
  - 🔍 "В любом случае майданный проект в Украине закрыт."
    - *Predicts the end of the post-Maidan political project in Ukraine — a substantive, verifiable political forecast.*
  - 🔍 "В противном случае РФ может использовать политический хаос, чтобы речь шла уже не о четырёх, а о шести, восьми или десяти областях."
    - *Predicts Russia will exploit political chaos to demand more than five territories — a conditional but verifiable future geopolitical prediction.*

---

### `O_Arestovich_official_1395` — gold `YES` — 2021-10-06

> По некоторым данным, в Иране заявляют, что если Армения сдаст Сюник, то они начнут боевые действия против Азербайджана. А это подразумевает угрозу региональной войны, в которую немедленно впишется Турция. Надеюсь, Азербайджан готов к возможному развитию событий. Я лично желаю Азербайджану удачи в сл…

**Pro Preview** — 1 claims, 2 missed
- ✅ `faithful_paraphrase` — "Я думаю, что российская сторона попытается столкнуть Азербайджан и Турцию с Ираном, спровоцировать конфликт и затем выступить миротворцем."
  - *This is a valid prediction about Russia's future strategic behavior — attempting to provoke an Azerbaijan-Turkey vs. Iran conflict and then acting as peacemaker. It is future-oriented, verifiable (one*
  *Opus каже missed:*
  - 🔍 "россияне согласны на обустройство Зангезурского коридора"
    - *This is a prediction that Russia has agreed to the establishment of the Zangezur corridor, which is a verifiable future outcome concerning whether the*
  - 🔍 "если Армения сдаст Сюник, то они начнут боевые действия против Азербайджана"
    - *This is a conditional prediction attributed to Iran about starting military action against Azerbaijan if Armenia cedes Syunik — a verifiable future co*

**Flash Lite** — 1 claims, 2 missed
- ✅ `faithful_paraphrase` — "российская сторона попытается столкнуть Азербайджан и Турцию с Ираном, спровоцировать конфликт и затем выступить миротворцем."
  - *This is a valid prediction about Russia's future strategic behavior — attempting to provoke a conflict between Azerbaijan/Turkey and Iran and then acting as peacemaker. It is future-oriented, verifiab*
  *Opus каже missed:*
  - 🔍 "россияне согласны на обустройство Зангезурского коридора"
    - *This is a prediction that Russia has agreed to the establishment of the Zangezur corridor, which is a verifiable future geopolitical outcome regarding*
  - 🔍 "если Армения сдаст Сюник, то они начнут боевые действия против Азербайджана"
    - *This is a conditional prediction attributed to Iran about starting military action against Azerbaijan if Armenia cedes Syunik — a verifiable future co*

**DeepSeek V3.1** — 3 claims, 1 missed
- ❌ `not_a_prediction` — "По некоторым данным, в Иране заявляют, что если Армения сдаст Сюник, то они начнут боевые действия против Азербайджана."
  - *This is a report of what Iran allegedly stated (a conditional threat attributed to Iran), not the author's own prediction about a future event. It describes a present claim/position, not a forecast.*
- ❌ `not_a_prediction` — "А это подразумевает угрозу региональной войны, в которую немедленно впишется Турция."
  - *This is a present-tense analytical assessment of what the Iranian position implies (a threat of regional war with Turkey's involvement). It's a conditional/hypothetical analysis, not a concrete predic*
- ✅ `faithful_paraphrase` — "Я думаю, что российская сторона попытается столкнуть Азербайджан и Турцию с Ираном, спровоцировать конфликт и затем выступить миротворцем."
  - *This is a genuine forward-looking prediction about Russia's future strategy — attempting to provoke a conflict between Azerbaijan/Turkey and Iran and then acting as peacemaker. It is verifiable and su*
  *Opus каже missed:*
  - 🔍 "так или иначе россияне согласны на обустройство Зангезурского коридора"
    - *This is a prediction that Russia has agreed to the establishment of the Zangezur corridor, which is a verifiable future geopolitical outcome regarding*

**Sonnet 4.6** — 0 claims, 3 missed
  *Opus каже missed:*
  - 🔍 "если Армения сдаст Сюник, то они начнут боевые действия против Азербайджана"
    - *This is a conditional prediction about Iran starting military action against Azerbaijan if Armenia cedes Syunik — a verifiable future contingency with*
  - 🔍 "россияне согласны на обустройство Зангезурского коридора"
    - *This is a prediction that Russia has agreed to the establishment of the Zangezur corridor, which is a verifiable future geopolitical outcome.*
  - 🔍 "российская сторона попытается столкнуть Азербайджан и Турцию с Ираном, спровоцировать конфликт и затем выступить миротворцем"
    - *This is a prediction about Russia's future strategy to provoke an Azerbaijan-Turkey-Iran conflict and then act as peacemaker — a verifiable geopolitic*

---


## NO gold-пости — тільки ті де хтось щось витягнув

На цих постах НЕ повинно бути валідних claims. Якщо є — це false positive.

### `O_Arestovich_official_3333` — gold `NO` — 2023-03-07

> - Я не мав сумніву, що грузинський народ скаже своє слово.  Кожному «беспрєделу» одного часу наступає свій «прєдел».   Перемога грузинського народу стане черговою поразкою РФ, що намагалась контролювати рух колишніх радянських республік до ЄС та НАТО через ручні корумповані еліти.   Перед тим була У…

**Pro Preview** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "Перемога грузинського народу стане черговою поразкою РФ, що намагалась контролювати рух колишніх радянських республік до ЄС та НАТО через ручні корумповані еліти."
    - *This predicts that the Georgian people's victory (in the context of the protests leading to withdrawal of the foreign agents law) will become another *
  - 🔍 "Сподіваюсь також на звільнення Михаїла Саакашвілі"
    - *This expresses an expectation/hope that Saakashvili will be freed — a concrete, verifiable future event concerning an external political figure.*

**Flash Lite** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "Перемога грузинського народу стане черговою поразкою РФ, що намагалась контролювати рух колишніх радянських республік до ЄС та НАТО через ручні корумповані еліти."
    - *This predicts that the Georgian people's victory (in the context of the protests leading to withdrawal of the foreign agents law) will become another *
  - 🔍 "Сподіваюсь також на звільнення Михаїла Саакашвілі"
    - *This expresses an expectation/hope that Saakashvili will be freed — a concrete, verifiable future event. However, it is framed as a hope ('сподіваюсь'*

**DeepSeek V3.1** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "Перемога грузинського народу стане черговою поразкою РФ, що намагалась контролювати рух колишніх радянських республік до ЄС та НАТО через ручні корумповані еліти."
    - *This predicts that the Georgian people's victory (in the context of the protests against the foreign agents law) will become another defeat for Russia*

**Sonnet 4.6** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "Перемога грузинського народу стане черговою поразкою РФ, що намагалась контролювати рух колишніх радянських республік до ЄС та НАТО через ручні корумповані еліти."
    - *This predicts that the Georgian people's victory (in the context of the protests against the foreign agents law) will become another defeat for Russia*

---

### `O_Arestovich_official_5315` — gold `NO` — 2024-03-26

> Российское руководство сделало террор инструментом внешней и внутренней политики.  Начиная с 1994-го года РФ воюет с представителями исламского мира. Если брать советский период, то с 1979-го (с ввода войск в Афганистан).  В российских СМИ потерялись сообщения о ещё относительно недавней войне с Исл…

**Pro Preview** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "новый фактор в виде мести ИГ может быть таким же системным, как и российский террор"
    - *This is a forward-looking claim that ISIS retaliation against Russia could become systematic/ongoing, which is verifiable over time — however, the wor*

**Flash Lite** — 1 claims, 0 missed
- ❌ `not_a_prediction` — "новый фактор в виде мести ИГ может быть таким же системным, как и российский террор"
  - *This is a vague speculative statement hedged with 'может быть' (could be). It lacks a concrete verifiable outcome — there's no specific event or threshold that can be checked as true or false. It func*

**DeepSeek V3.1** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "новый фактор в виде мести ИГ может быть таким же системным, как и российский террор"
    - *This is a forward-looking claim that ISIS retaliation against Russia could become systematic/ongoing, which is verifiable over time — however, the wor*

**Sonnet 4.6** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "новый фактор в виде мести ИГ может быть таким же системным, как и российский террор"
    - *This is a forward-looking claim that ISIS retaliation against Russia could become systematic/ongoing, which is verifiable over time — however, the wor*

---

### `O_Arestovich_official_1234` — gold `NO` — 2021-07-05

> [​​](https://telegra.ph/file/d16cf60a318098a235907.jpg)- На фронте за несколько предыдущих дней участились случаи с применением противником вооружения, запрещённого Минскими  соглашениями.   Самое опасное - обстреливают населенные пункты, в частности, Авдеевку.  - Сегодня, в результате огня противни…

**Sonnet 4.6** — 2 claims, 0 missed
- ❌ `not_a_prediction` — "Украинская делегация в ТКГ начнёт своё завтрашнее заседание с этой темы, используя свои дипломатические возможности для возвращения к полному соблюдению режима прекращения огня."
  - *This is an announcement of the delegation's own planned activity — a procedural/logistical certainty about what the Ukrainian delegation intends to do at tomorrow's meeting. It fails criterion 4 (non-*
- ❌ `not_a_prediction` — "Так же этот вопрос будет поднят во время консультаций в рамках Нормандского формата."
  - *This is a statement about the author's side's own planned diplomatic action — raising the issue during Normandy format consultations. It is a procedural intention announcement, not a substantive predi*

---

### `O_Arestovich_official_5409` — gold `NO` — 2024-04-10

> Третья мировая, которую многие опасаются, уже давно идёт, но не в таком виде, как она представляется идеалистам.  Третья мировая идёт россыпью по всему миру, в виде горячей войны, когнитивной, информационной, экономической и спецслужбиской.   Идеалисты представляют войны, ведущиеся на полную мощност…

**Pro Preview** — 0 claims, 3 missed
  *Opus каже missed:*
  - 🔍 "Запад решительно занялся подтягиванием наземного военного компонента, что может сделать за 2-3 года"
    - *This predicts that the West will close the gap in ground military capabilities within 2-3 years, a verifiable future claim about military buildup with*
  - 🔍 "Пробьет – придет Китай, Иран, Северная Корея и другие противники Запада придут спрашивать за колониальную политику, требуя многополярности."
    - *This is a conditional prediction: if Russia breaks through the West's defenses, China, Iran, North Korea will aggressively challenge Western dominance*
  - 🔍 "Если Россия не пробьет ворота Запада, то страны Юга будут продолжать вести осторожную политику, широкую торговлю, заботясь о своей экономической стабильности."
    - *This is a conditional prediction: if Russia fails to break through, Global South countries will continue cautious policies and broad trade — a verifia*

**Flash Lite** — 3 claims, 0 missed
- ❌ `not_a_prediction` — "Запад решительно занялся подтягиванием наземного военного компонента, что может сделать за 2-3 года"
  - *The first part ('Запад решительно занялся') is a present-tense assessment of current policy. The '2-3 года' part is vague — 'может сделать' (can do) is a statement of capability, not a concrete predic*
- ❌ `not_a_prediction` — "Пробьет [Россия ворота Запада] – придет Китай, Иран, Северная Корея и другие противники Запада придут спрашивать за колониальную политику, требуя многополярности."
  - *This is a conditional/hypothetical scenario ('if Russia breaks through... then...') using vague metaphorical language ('пробьет ворота Запада', 'спрашивать за колониальную политику'). The trigger cond*
- ❌ `not_a_prediction` — "Если Россия не пробьет ворота Запада, то страны Юга будут продолжать вести осторожную политику, широкую торговлю, заботясь о своей экономической стабильности."
  - *Same issue as above — a conditional hypothetical with vague, metaphorical trigger ('не пробьет ворота Запада') and a vague outcome ('осторожную политику, широкую торговлю'). Neither the condition nor *

**DeepSeek V3.1** — 3 claims, 0 missed
- ❌ `not_a_prediction` — "Запад решительно занялся подтягиванием наземного военного компонента, что может сделать за 2-3 года"
  - *This is partly a present-tense assessment ('решительно занялся') combined with a vague capability estimate ('может сделать за 2-3 года'). The 'может' (can) framing describes a capability, not a concre*
- ❌ `not_a_prediction` — "Если Россия не пробьет ворота Запада, то страны Юга будут продолжать вести осторожную политику, широкую торговлю, заботясь о своей экономической стабильности."
  - *This is a conditional analytical statement with vague, metaphorical terms ('пробьет ворота Запада') and an equally vague outcome ('осторожную политику'). Neither the condition nor the outcome has a co*
- ❌ `not_a_prediction` — "Пробьет – придет Китай, Иран, Северная Корея и другие противники Запада придут спрашивать за колониальную политику, требуя многополярности."
  - *This is the other branch of the same conditional with metaphorical language ('пробьет ворота'). The condition is undefined and the outcome ('придут спрашивать за колониальную политику, требуя многопол*

**Sonnet 4.6** — 0 claims, 3 missed
  *Opus каже missed:*
  - 🔍 "Запад решительно занялся подтягиванием наземного военного компонента, что может сделать за 2-3 года"
    - *This predicts that the West will close the gap in ground military capabilities within 2-3 years (by ~2026-2027), which is a verifiable future claim ab*
  - 🔍 "Пробьет – придет Китай, Иран, Северная Корея и другие противники Запада придут спрашивать за колониальную политику, требуя многополярности."
    - *This is a conditional prediction: if Russia breaks through the West's defenses, China, Iran, North Korea and others will aggressively challenge Wester*
  - 🔍 "Если Россия не пробьет ворота Запада, то страны Юга будут продолжать вести осторожную политику, широкую торговлю, заботясь о своей экономической стабильности."
    - *This is a conditional prediction: if Russia fails to break through, Global South countries will continue cautious policies and broad trade — a verifia*

---

### `O_Arestovich_official_1585` — gold `NO` — 2022-01-27

> [​​](https://telegra.ph/file/ce67323900cfac842f55c.jpg)- Politeka-live с неотразимой Ингой Мезерей:   00:00 Куда пропал Алексей Арестович? 02:56 Сценарии развития военной угрозы на границе Украины. 14:58 Почему Украина не объявляет мобилизацию. 16:00 Плановые учения ВСУ. 16:37 Главная цель Путина. 2…

**Pro Preview** — 1 claims, 0 missed
- ❌ `not_a_prediction` — "На Украину не будут оказывать давление через Минский формат."
  - *This is a timestamp label from a video table of contents, not a prediction made in the post text itself. It describes a topic discussed in the video at 23:08. Without the actual video content, we cann*

**Flash Lite** — 1 claims, 0 missed
- ❌ `not_a_prediction` — "На Украину не будут оказывать давление через Минский формат."
  - *This is a timestamp label from a video table of contents, not a prediction made in the post text itself. It describes a topic discussed in the video at 23:08. Without the actual video content, we cann*

---

### `O_Arestovich_official_1076` — gold `NO` — 2021-03-09

> [​​](https://telegra.ph/file/a4f880efd277983c0a6f5.jpg)- РФ договорилась с КНР о совместном освоении Луны (создание базовой станции).  Космос - арена, на которой очень хорошо видны цели и мотивы сторон, именно поэтому на Марсе и возле Марса топчется сегодня десяток космических аппаратов разных стран…

**Pro Preview** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "Серия гонок, наметившихся в мире (от космической, до борьбы с пандемией, смены техноуклада, до новой гонки вооружений) которая продлится в активной фазе годов эдак до 2045"
    - *This is a prediction that the active phase of global competition (space race, arms race, pandemic response, technological shift) will last until appro*

**Flash Lite** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "Серия гонок, наметившихся в мире (от космической, до борьбы с пандемией, смены техноуклада, до новой гонки вооружений) которая продлится в активной фазе годов эдак до 2045"
    - *This is a concrete prediction that the active phase of global competition (space race, arms race, pandemic response, tech shifts) will last until appr*

**DeepSeek V3.1** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "Серия гонок, наметившихся в мире (от космической, до борьбы с пандемией, смены техноуклада, до новой гонки вооружений) которая продлится в активной фазе годов эдак до 2045"
    - *This is a concrete prediction that the active phase of global competition (space race, arms race, pandemic response, tech shifts) will last until appr*

**Sonnet 4.6** — 1 claims, 0 missed
- ❌ `not_a_prediction` — "Серия гонок, наметившихся в мире (от космической, до борьбы с пандемией, смены техноуклада, до новой гонки вооружений) которая продлится в активной фазе годов эдак до 2045, покажет нам очень много инт"
  - *This is a vague forward-looking statement without a concrete verifiable outcome. 'Will show us a lot of interesting, expected and unexpected things' has no measurable criterion that could be checked a*

---

### `O_Arestovich_official_2345` — gold `NO` — 2022-07-14

> - Пошла работа.  Есть первых три крупных накрытия.  Как раз за Харьков, Винницу, Николаев.  Но будет больше. Много больше.

**Pro Preview** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "Но будет больше. Много больше."
    - *This predicts that there will be significantly more large-scale strikes/attacks beyond the initial three mentioned, which is a future event with a ver*

**Flash Lite** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "Но будет больше. Много больше."
    - *This predicts that there will be significantly more large-scale strikes/attacks beyond the initial three mentioned, which is a future event with a ver*

**DeepSeek V3.1** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "Но будет больше. Много больше."
    - *This predicts that there will be significantly more large-scale strikes/attacks beyond the initial three mentioned, which is a future event with a ver*

**Sonnet 4.6** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "Но будет больше. Много больше."
    - *This predicts that there will be significantly more large-scale strikes/attacks beyond the initial three mentioned, which is a future event with a ver*

---

### `O_Arestovich_official_4260` — gold `NO` — 2023-08-27

> В эфире «Альфа Media» с Юрием Романенко и Николаем Фельдманом обсудили ситуацию на фронте и дискуссии по этому поводу на Западе, от которого мы практически полностью зависим.  В газете “The Guardian” была опубликована стать о тайной встрече Главнокомандующего  ВСУ генерала Залужного с высокопоставле…

**Pro Preview** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "Позиции дискутирующих будут меняться в зависимости от результатов на фронте."
    - *This is a forward-looking claim but it's vague — no concrete verifiable outcome. Actually fails criterion 2/4, so should NOT be included.*
  - 🔍 "Успешность этой операции будет означать стратегический перелом в войне по аналогии Битвы на Курской дуге в 1943-м."
    - *This is a conditional analytical statement ('if successful, then...') rather than a prediction of what WILL happen — it lacks a concrete verifiable cl*

**Flash Lite** — 2 claims, 0 missed
- ❌ `not_a_prediction` — "Позиции дискутирующих будут меняться в зависимости от результатов на фронте."
  - *This is a vague general statement about how Western debate positions will shift depending on front-line results. It lacks a concrete verifiable outcome — there's no specific claim about what position *
- ❌ `not_a_prediction` — "Успешность этой операции [освобождение юга и взятие Крыма под огневой контроль] будет означать стратегический перелом в войне по аналогии Битвы на Курской дуге в 1943-м."
  - *This is a conditional analytical statement: IF the southern operation succeeds, THEN it will mean a strategic turning point. It doesn't predict that the operation will succeed — it describes the signi*

**DeepSeek V3.1** — 0 claims, 2 missed
  *Opus каже missed:*
  - 🔍 "Позиции дискутирующих будут меняться в зависимости от результатов на фронте."
    - *This is a forward-looking claim but it's vague — no concrete verifiable outcome. Actually fails criterion 2/4, so should NOT be included.*
  - 🔍 "Успешность этой операции будет означать стратегический перелом в войне по аналогии Битвы на Курской дуге в 1943-м."
    - *This is a conditional analytical statement ('if successful, then...') rather than a prediction of what WILL happen — it lacks a concrete verifiable cl*

**Sonnet 4.6** — 0 claims, 1 missed
  *Opus каже missed:*
  - 🔍 "Позиции дискутирующих будут меняться в зависимости от результатов на фронте."
    - *This is vague and lacks a concrete verifiable outcome — it would be 'not_a_prediction' if extracted. Excluding.*

---
