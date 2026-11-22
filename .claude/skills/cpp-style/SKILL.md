---
name: cpp-style
description: Alex2772's C++ code style (author of AUI). Load before writing, refactoring or reviewing any C++ code in any project — beautiful readable code, declarative macros/DSLs, designated initializers as named args, AUI types (AString/AStringView/AOptional/AArc/AVector), std::variant as Rust enums with exhaustive match, no raw pointers or out-params, std::array/std::size, single source of truth, constexpr, if constexpr/requires instead of enable_if, early returns, RAII and narrow scopes, careful ownership (std::move/std::exchange), C++20 coroutines, "{}"_format / fmt::format / std::format instead of printf-family.
---

# C++ style

Alex (автор AUI) пишет C++20 и ждёт того же в любом C++-проекте; AUI-типы (п. 3) — там, где проект на AUI. Примеры взяты из i-love-kuni и AUI.

1. **Красота и читаемость.** Код должен быть приятен глазу: короткие строки-фразы, без шума. Named arguments — через C++20 aggregate/designated initialization:
   ```cpp
   struct ChapterArgs {
       AString title;
       AString subtitle;
       Pov pov = Pov::PAPIK;
   };

   panel({ .rect = { 0.5f, 0, 0.5f, 0.35f }, .bg = img::prologue::call_him, .focus = { 0.5f, 0.45f } });
   co_await papik(Say { .text = "Не читал.", .kind = BubbleKind::THOUGHT, .at = Point { 0.14f, 0.11f } });
   co_await ch3({ .agency = KuniAgency::OWN });
   ```
2. **Декларативщина.** Описывать «что», а не «как»; регистрация/бойлерплейт прячется за макросом, который читается как ключевое слово.
   - gtest-style песочница: макрос объявляет функцию и статически её регистрирует.
     ```cpp
     #define KN_SANDBOX(name)                                                        \
         static ::kn::Scene<> kn_sandbox_##name();                                   \
         [[maybe_unused]] static const bool kn_sandbox_registered_##name =           \
             ::kn::detail::registerSandbox(#name, &kn_sandbox_##name);               \
         static ::kn::Scene<> kn_sandbox_##name()

     KN_SANDBOX(pr_nika_call) { co_await story::prNikaCall(); }
     ```
   - Точка входа без платформенных main/WinMain:
     ```cpp
     AUI_ENTRY {
         _new<CounterWindow>()->show();
         return 0;
     }
     ```
   - Declarative UI в AUI, `AProperty` + `AUI_REACT` для биндингов, `AUI_OVERRIDE_STYLE` для стилей на месте:
     ```cpp
     class CounterWindow : public AWindow {
     public:
         CounterWindow() : AWindow("AUI - 7GUIs - Counter", 200_dp, 100_dp) {
             setContents(Centered {
               Horizontal {
                 Label { AUI_REACT("Count: {}"_format(mCounter)) },
                 Button { Label { "Count" }, [this] { mCounter += 1; } },
               } AUI_OVERRIDE_STYLE { LayoutSpacing { 4_dp } },
             });
         }

     private:
         AProperty<int> mCounter;
     };
     ```
   - Того же духа:
     ```cpp
     auto tf = _new<ATextField>() AUI_LET { it->setText("Hello!"); };
     AUI_DEFER { mHud->setVisibility(Visibility::VISIBLE); };
     jobs.emplace_back(k, AUI_THREADPOOL { return decode(k); });

     // сценарий читается как пьеса
     co_await narrate("Следующий вечер. Созвон. Восемь.");
     co_await nika("Погоди. Погоди, он сейчас скажет «я не такой, как все».");
     co_await he("Не скажет.");
     ```
3. **AUI-типы, если проект на AUI:** `AStringView` вместо `std::string`/`const char*`/`std::string_view` в параметрах, `AString` для владеющей строки; `AOptional` вместо `std::optional`; `AArc`/`AWeakArc` (и `_<T>`/`_new<T>`) вместо `std::shared_ptr`/`std::weak_ptr`; `AVector` вместо `std::vector`; `AFuture` вместо std::future.
   ```cpp
   void achievement(AStringView id);
   AOptional<AString> music;   // changed music; empty string = stop
   ```
4. **`std::span`** вместо пары указатель + размер:
   ```cpp
   void upload(const char* data, size_t size);   // нет
   void upload(std::span<const std::byte> data); // да
   ```
5. **Без сырых указателей.** Владение — умные указатели / контейнеры; не-владеющий доступ — ссылки. `new`/`delete` — только там, где без них никак.
6. **Без мутабельных out-параметров.** Результат возвращается значением (структурой, если полей несколько):
   ```cpp
   bool tryParse(AStringView s, int& result);   // нет
   AOptional<int> tryParse(AStringView s);       // да
   ```
7. **Современный C++20:** корутины, designated initializers, `enum class`, лямбды, ranges.
   ```cpp
   struct promise_type : detail::PromiseValue<T> {
       Scene get_return_object() { return Scene { std::coroutine_handle<promise_type>::from_promise(*this) }; }
   };
   ```
8. **`std::variant` как Rust-енум с полями.** Альтернативы — отдельные структуры (с данными, если нужны), сумма — `std::variant`; разбор — исчерпывающий `match` через overload-set, так что забытая ветка = ошибка компиляции. Флаг-enum + разрозненные поля — не его стиль.
   ```cpp
   struct ChoosePerfect { static constexpr auto remembers = &he; };
   struct ChoosePeek {};
   struct ChooseForget {};
   using Choice = std::variant<ChoosePerfect, ChoosePeek, ChooseForget>;

   template <typename... Fs>
   struct Overloaded : Fs... {
       using Fs::operator()...;
   };

   template <typename V, typename... Fs>
   decltype(auto) match(V&& variant, Fs&&... fs) {
       return std::visit(Overloaded<std::decay_t<Fs>...> { std::forward<Fs>(fs)... }, std::forward<V>(variant));
   }

   auto c = co_await choose<ch5::Cover>(L, {
       { .text = "«Да, извини. Уснул»", .pick = ch5::CoverHer {} },
       { .text = "«Это не я»", .pick = ch5::CoverNotMe {} },
   });
   co_await match(c, [](ch5::CoverHer) { return coverHer(); }, [](ch5::CoverNotMe) { return notMe(); });
   ```
9. **Ownership-модель продумана:** `std::move` при передаче владения, `std::exchange` для «забрать и обнулить», `std::swap`, `std::forward` в шаблонах. Move-конструкторы `noexcept`, копирование явно `delete`, если владение уникально.
   ```cpp
   Scene(Scene&& o) noexcept : mHandle(std::exchange(o.mHandle, {})) {}
   Scene& operator=(Scene&& o) noexcept {
       if (this != &o) {
           reset();
           mHandle = std::exchange(o.mHandle, {});
       }
       return *this;
   }
   Scene(const Scene&) = delete;

   bubbles.push_back(std::move(b));
   std::exchange(mResume, {}).resume();
   StepResult result = std::exchange(mPending, {});
   ```
10. **Без C-style массивов, размеры не хардкодятся.**
    ```cpp
    int arr[5];                                    // нет
    std::array<int, 5> arr;                        // да
    for (size_t i = 0; i < sizeof(arr) / sizeof(arr[0]); ++i)  // нет
    for (size_t i = 0; i < std::size(arr); ++i)                // да

    constexpr std::array<const char*, 64> CP1251_HIGH = { ... };
    ```
11. **Один source of truth** (вытекает из п. 10). Размер, список, имя, соответствие задаются ровно в одном месте, остальное из него выводится (`std::size`, CTAD, `constexpr`-таблица, макрос-регистрация вроде `KN_SANDBOX`). Не дублировать одно знание в двух местах, которые надо синхронизировать руками.
12. **`constexpr` везде, где можно** — функции в хедерах помечаются `constexpr` по возможности.
13. **Шаблоны — да, SFINAE-каскады — нет.** Шаблоны любит, но читаемость важнее: `if constexpr` и `requires`/концепты вместо `std::enable_if_t`, `void_t`-трюков и вложенных traits-лестниц.
    ```cpp
    template <typename T>
    concept Remembered = requires { T::remembers; };

    template <typename T>
    void rememberEvent() {
        if constexpr (Remembered<T>) {
            using R = std::remove_cvref_t<decltype(T::remembers)>;
            if constexpr (std::is_pointer_v<R>) {
                remember(*T::remembers);
            } else {
                for (const Character* c : T::remembers) remember(*c);
            }
        }
    }
    ```
14. **Плоский код через ранние return.** Никакой лесенки `if` в `if`; если ранним return не распрямить — распилить функцию на мелкие (декомпозиция/композиция).
    ```cpp
    int bad(int a, int b) {
      if (a > 5) {
        if (b < 3) {
          return a;
        }
      }
      return b;
    }
    int good(int a, int b) {
      if (a <= 5) {
        return b;
      }
      if (b >= 3) {
        return b;
      }
      return a;
    }
    ```
    Исключение — тип, неявно приводимый к bool (указатель, `AOptional`, `std::optional`): тут вложение с объявлением в условии нормально, оно ограничивает область видимости:
    ```cpp
    if (auto result = tryParse(...)) {
      ...
    }
    ```
15. **RAII повсеместно.** Любой парный захват/освобождение (мьютекс, глобальное состояние, ресурс, флаг видимости) — через объект с деструктором, а не ручные пары вызовов; `std::unique_lock`/`std::scoped_lock`, свои guard-структуры, `AUI_DEFER`.
    ```cpp
    struct CurrentGuard {
        Director* previous;
        explicit CurrentGuard(Director* d) : previous(std::exchange(gCurrent, d)) {}
        ~CurrentGuard() { gCurrent = previous; }
    };

    void Director::step() {
        CurrentGuard guard(this);
        ...
    }   // gCurrent восстановлен на любом выходе, включая исключения

    AUI_DEFER { mHud->setVisibility(Visibility::VISIBLE); };
    ```
16. **Минимальная область видимости — если это элегантно.** Объект живёт ровно столько, сколько нужен: объявление в условии `if`/`for`, вложенный блок `{ }` под lock, лямбда/IIFE для инициализации `const`-значения. Без искусственных блоков ради блоков.
    ```cpp
    {
        std::unique_lock lock(mMutex);
        mQueue.push_back(std::move(job));
    }   // lock отпущен до notify
    mCv.notify_one();

    if (auto result = tryParse(text)) {
        use(*result);
    }   // result дальше не виден

    const auto size = [&] {
        if (compact) return 16_dp;
        return 24_dp;
    }();
    ```
17. **Без `printf`/`sprintf`/`snprintf`/`fprintf`.** Форматирование строк: `"Counter: {}"_format(i)` в проектах на AUI, `fmt::format("Counter: {}", i)`, если подключён fmt, в крайнем случае `std::format`. Вывод — через логгер проекта (`ALogger::info(LOG_TAG) << ...`) или поток, не через C-шный printf.
    ```cpp
    std::snprintf(number, sizeof(number), "%04d", ++index);   // нет
    fprintf(stderr, "frame ms=%.2f\n", ms);                    // нет
    auto number = "{:04}"_format(++index);                     // да
    ALogger::info(LOG_TAG) << "frame ms={:.2f}"_format(ms);    // да
    ```

**How to apply:** пиши новый код сразу в этом стиле и подтягивай к нему код, который трогаешь; если API заставляет писать out-параметр или сырой указатель — оберни в функцию, возвращающую значение/AOptional. Если просится новая сущность-регистрация, предпочти декларативный макрос/aggregate-аргументы императивной цепочке вызовов.
