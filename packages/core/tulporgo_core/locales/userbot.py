"""Userbot texts (workstream W2). "uz" is current Latin with plain '; other Uzbek scripts are derived.
Bot messages use HTML parse mode — only simple tags (<b>, <code>) without attributes, so the alphabet converter is safe.
Group post templates (userbot.post.*) are plain text: they are sent from the driver's own account."""
TEXTS = {
    # --- risk / consent (decision 8) ---
    "userbot.risk": {
        "uz": "<b>⚠️ Avto-e'lon: rozilik</b>\n\n"
              "1. Siz o'z Telegram hisobingizni ulaysiz. TulporGo siz tanlagan guruhlarga qatnov e'loningizni sizning "
              "nomingizdan yuboradi. TulporGo — Telegram API orqali ishlaydigan mustaqil xizmat, Telegramning rasmiy "
              "ilovasi emas.\n"
              "2. Xavf: Telegram avtomatik e'lonlar uchun hisobingizni vaqtincha cheklashi yoki bloklashi mumkin. Bu "
              "Telegramning qarori: TulporGo uni bekor qila olmaydi va javobgar emas.\n"
              "3. TulporGo FloodWait va PEER_FLOOD cheklovlarini hech qachon chetlab o'tmaydi: kutadi yoki to'xtaydi va "
              "sizga xabar beradi.\n"
              "4. Standart: har guruhga 30–60 daqiqada bittadan ko'p emas, tasodifiy pauza bilan (hozir: {min} daqiqa). "
              "Tez-tez yuborish xavfni oshiradi va alohida tasdiqni talab qiladi.\n"
              "5. Faqat siz tanlagan guruhlar bilan ishlaydi. Hisobingiz shu guruhlardagi yangi xabarlarni TulporGo "
              "haydovchilari uchun kuzatishi mumkin (yo'lovchi so'rovlarini topish uchun): faqat o'qiydi, hech kim "
              "nomidan hech narsa yozmaydi, xabarlar saqlanmaydi. Shaxsiy chatlar hech qachon o'qilmaydi.\n"
              "6. Sessiya O'zbekistondagi serverda shifrlangan holda saqlanadi. Telegram kodi va 2FA paroli hech qachon "
              "saqlanmaydi (ular faqat Mini App formasida kiritiladi).\n"
              "7. Faqat o'zingiz a'zo bo'lgan va yozish mumkin bo'lgan guruhlarni tanlang va ularning qoidalariga "
              "amal qiling.\n"
              "8. To'xtatish: \"Hisobni uzish\" TulporGo sessiyasini tugatadi va saqlangan sessiyani darhol o'chiradi. "
              "Sessiyani Telegramda ham yopish mumkin: Sozlamalar → Qurilmalar → \"TulporGo (driver)\".\n\n"
              "Rozimisiz?",
        "ru": "<b>⚠️ Автообъявления: согласие</b>\n\n"
              "1. Вы подключаете свой аккаунт Telegram. TulporGo публикует ваше объявление о поездке в выбранных вами "
              "группах от вашего имени. TulporGo — независимый сервис, работающий через Telegram API, а не официальное "
              "приложение Telegram.\n"
              "2. Риск: Telegram может временно ограничить или заблокировать аккаунт за автоматические публикации. "
              "Это решение Telegram: TulporGo не может его отменить и не несёт ответственности.\n"
              "3. TulporGo никогда не обходит ограничения FloodWait и PEER_FLOOD: ждёт или останавливается и сообщает "
              "вам.\n"
              "4. По умолчанию: не чаще одного поста в группу раз в 30–60 минут со случайной паузой (сейчас: {min} мин). "
              "Более частые публикации повышают риск и требуют отдельного подтверждения.\n"
              "5. Работает только с выбранными группами. Ваш аккаунт может следить за новыми сообщениями в этих "
              "группах для водителей TulporGo (чтобы находить запросы пассажиров): только читает, ничего не пишет "
              "ни от чьего имени, сообщения не сохраняются. Личные чаты никогда не читаются.\n"
              "6. Сессия хранится в зашифрованном виде на сервере в Узбекистане. Код Telegram и пароль 2FA никогда не "
              "сохраняются (они вводятся только в форме Mini App).\n"
              "7. Выбирайте только группы, в которых вы состоите и где можно писать, и соблюдайте их правила.\n"
              "8. Остановка: «Отключить аккаунт» завершает сессию TulporGo и сразу удаляет сохранённую сессию. "
              "Сессию можно закрыть и в Telegram: Настройки → Устройства → «TulporGo (driver)».\n\n"
              "Вы согласны?",
        "en": "<b>⚠️ Auto-posting: consent</b>\n\n"
              "1. You connect your own Telegram account. TulporGo posts your ride announcement in the groups you "
              "selected, in your name. TulporGo is an independent service built on the Telegram API, not an official "
              "Telegram app.\n"
              "2. Risk: Telegram may temporarily limit or ban the account for automatic posts. That is Telegram's "
              "decision: TulporGo cannot undo it and is not liable.\n"
              "3. TulporGo never bypasses FloodWait or PEER_FLOOD: it waits or stops and tells you.\n"
              "4. Default: at most one post per group every 30-60 minutes with a random pause (now: {min} min). Posting "
              "more often raises the risk and needs a separate confirmation.\n"
              "5. Works only with the selected groups. Your account may watch new messages in these groups for "
              "TulporGo drivers (to find passenger requests): it only reads, never writes for anyone, and messages "
              "are not stored. Private chats are never read.\n"
              "6. The session is stored encrypted on a server in Uzbekistan. The login code and the 2FA password are "
              "never stored (they are entered only in the Mini App form).\n"
              "7. Pick only groups you belong to where posting is allowed, and follow their rules.\n"
              "8. Stop: \"Disconnect account\" logs the TulporGo session out and deletes the stored session "
              "immediately. You can also close it in Telegram: Settings → Devices → \"TulporGo (driver)\".\n\n"
              "Do you agree?",
    },
    "userbot.btn.consent": {"uz": "Roziman", "ru": "Согласен", "en": "I agree"},
    "userbot.consent.ok": {
        "uz": "✅ Rozilik qabul qilindi. Endi hisobni ulashingiz mumkin.",
        "ru": "✅ Согласие принято. Теперь можно подключить аккаунт.",
        "en": "✅ Consent recorded. You can now connect your account.",
    },
    # --- menu / status ---
    "userbot.menu": {
        "uz": "<b>📣 Avto-e'lon</b>\n\n{status}",
        "ru": "<b>📣 Автообъявления</b>\n\n{status}",
        "en": "<b>📣 Auto-posting</b>\n\n{status}",
    },
    "userbot.status.needs_login": {"uz": "Holat: hisob ulanmagan", "ru": "Статус: аккаунт не подключён",
                                   "en": "Status: account not connected"},
    "userbot.status.connected": {"uz": "Holat: ishlayapti ✅", "ru": "Статус: работает ✅", "en": "Status: running ✅"},
    "userbot.status.paused": {"uz": "Holat: to'xtatilgan ⏸", "ru": "Статус: приостановлено ⏸",
                              "en": "Status: paused ⏸"},
    "userbot.status.flood_wait": {
        "uz": "Holat: Telegram kutishni so'radi ⏳ ({until} gacha)",
        "ru": "Статус: Telegram просит подождать ⏳ (до {until})",
        "en": "Status: Telegram asked to wait ⏳ (until {until})",
    },
    "userbot.status.stopped": {"uz": "Holat: to'xtagan ⛔ ({reason})", "ru": "Статус: остановлено ⛔ ({reason})",
                               "en": "Status: stopped ⛔ ({reason})"},
    "userbot.status.details": {
        "uz": "Guruhlar: {groups} ta yoqilgan\nInterval: {interval} daqiqa (+ tasodifiy {jitter} daqiqagacha)\n"
              "Kunlik chegara: {cap}",
        "ru": "Группы: {groups} включено\nИнтервал: {interval} мин (+ случайно до {jitter} мин)\n"
              "Дневной лимит: {cap}",
        "en": "Groups: {groups} enabled\nInterval: {interval} min (+ random up to {jitter} min)\nDaily cap: {cap}",
    },
    "userbot.cap.none": {"uz": "yo'q", "ru": "нет", "en": "none"},
    "userbot.btn.connect": {"uz": "Hisobni ulash", "ru": "Подключить аккаунт", "en": "Connect account"},
    "userbot.btn.status": {"uz": "Holat", "ru": "Статус", "en": "Status"},
    "userbot.btn.groups": {"uz": "Guruhlar", "ru": "Группы", "en": "Groups"},
    "userbot.btn.interval": {"uz": "Interval", "ru": "Интервал", "en": "Interval"},
    "userbot.btn.template": {"uz": "E'lon matni", "ru": "Текст объявления", "en": "Post text"},
    "userbot.btn.pause": {"uz": "To'xtatish", "ru": "Приостановить", "en": "Pause"},
    "userbot.btn.resume": {"uz": "Davom ettirish", "ru": "Продолжить", "en": "Resume"},
    "userbot.btn.logout": {"uz": "Hisobni uzish", "ru": "Отключить аккаунт", "en": "Disconnect account"},
    "userbot.btn.sync": {"uz": "Ro'yxatni yangilash", "ru": "Обновить список", "en": "Refresh list"},
    "userbot.btn.edit_template": {"uz": "Matnni o'zgartirish", "ru": "Изменить текст", "en": "Edit text"},
    "userbot.btn.back": {"uz": "Orqaga", "ru": "Назад", "en": "Back"},
    "userbot.btn.confirm_logout": {"uz": "Ha, uzish", "ru": "Да, отключить", "en": "Yes, disconnect"},
    "userbot.btn.ack": {"uz": "Xavfni tushundim", "ru": "Я понимаю риск", "en": "I understand the risk"},
    "userbot.connect.open": {
        "uz": "Telegram hisobini ulash uchun Mini App'ni oching. Kod va parol faqat o'sha formada kiritiladi, "
              "xabarga yozmang.",
        "ru": "Чтобы подключить аккаунт, откройте Mini App. Код и пароль вводятся только в этой форме, "
              "не отправляйте их сообщением.",
        "en": "Open the Mini App to connect your Telegram account. The code and password are entered only in that "
              "form: never send them in a message.",
    },
    # --- groups ---
    "userbot.groups.title": {
        "uz": "<b>Guruhlar</b>\nYoqilgan: {enabled} / {limit}\nE'lon yuboriladigan guruhlarni belgilang.",
        "ru": "<b>Группы</b>\nВключено: {enabled} / {limit}\nОтметьте группы для объявлений.",
        "en": "<b>Groups</b>\nEnabled: {enabled} / {limit}\nChoose the groups to post in.",
    },
    "userbot.groups.empty": {
        "uz": "Guruhlar ro'yxati bo'sh. \"Ro'yxatni yangilash\" tugmasini bosing.",
        "ru": "Список групп пуст. Нажмите «Обновить список».",
        "en": "The group list is empty. Tap \"Refresh list\".",
    },
    "userbot.groups.synced": {"uz": "Ro'yxat yangilandi: {n} ta guruh.", "ru": "Список обновлён: {n} групп.",
                              "en": "List refreshed: {n} groups."},
    "userbot.limit.unlimited": {"uz": "cheksiz", "ru": "без лимита", "en": "unlimited"},
    # --- interval ---
    "userbot.interval.title": {
        "uz": "<b>Interval</b>\nHozir: {interval} daqiqa. Xavfsiz standart — {min} daqiqa va undan ko'p.",
        "ru": "<b>Интервал</b>\nСейчас: {interval} мин. Безопасный стандарт — {min} мин и больше.",
        "en": "<b>Interval</b>\nCurrent: {interval} min. The safe default is {min} min or more.",
    },
    "userbot.interval.warn": {
        "uz": "<b>⚠️ Ogohlantirish</b>\n{minutes} daqiqa xavfsiz chegaradan ({min} daqiqa) past. Bu hisobingizning "
              "cheklanishi yoki bloklanishi ehtimolini oshiradi. Telegram to'xtatsa, TulporGo to'xtaydi.",
        "ru": "<b>⚠️ Предупреждение</b>\n{minutes} мин ниже безопасного порога ({min} мин). Это повышает риск "
              "ограничения или блокировки аккаунта. Если Telegram остановит, TulporGo остановится.",
        "en": "<b>⚠️ Warning</b>\n{minutes} min is below the safe threshold ({min} min). This raises the risk of your "
              "account being limited or banned. If Telegram stops it, TulporGo stops.",
    },
    "userbot.interval.set": {"uz": "✅ Interval: {minutes} daqiqa.", "ru": "✅ Интервал: {minutes} мин.",
                             "en": "✅ Interval: {minutes} min."},
    # --- template ---
    "userbot.template.none": {
        "uz": "E'lon matni hali yozilmagan. Matn yo'nalish, vaqt, joy va narxdan tuziladi.",
        "ru": "Текст объявления ещё не задан. Он собирается из маршрута, времени, мест и цены.",
        "en": "No post text yet. It is built from the route, time, seats and price.",
    },
    "userbot.template.preview": {
        "uz": "<b>E'lon ko'rinishi</b>\n\n{text}", "ru": "<b>Так будет выглядеть объявление</b>\n\n{text}",
        "en": "<b>Post preview</b>\n\n{text}",
    },
    "userbot.template.ask_from": {"uz": "Qayerdan? (masalan: Samarqand)", "ru": "Откуда? (например: Самарканд)",
                                  "en": "From where? (e.g. Samarkand)"},
    "userbot.template.ask_to": {"uz": "Qayerga?", "ru": "Куда?", "en": "To where?"},
    "userbot.template.ask_time": {"uz": "Qachon? (masalan: 08:00 yoki ertaga 6:30)",
                                  "ru": "Когда? (например: 08:00 или завтра 6:30)",
                                  "en": "When? (e.g. 08:00 or tomorrow 6:30)"},
    "userbot.template.ask_seats": {"uz": "Nechta bo'sh joy? (1–8)", "ru": "Сколько свободных мест? (1–8)",
                                   "en": "How many free seats? (1-8)"},
    "userbot.template.ask_price": {"uz": "Narx (so'm), yoki \"-\" agar kelishilsa",
                                   "ru": "Цена (сум) или «-», если договорная",
                                   "en": "Price (UZS), or \"-\" if negotiable"},
    "userbot.template.saved": {"uz": "✅ E'lon matni saqlandi.", "ru": "✅ Текст объявления сохранён.",
                               "en": "✅ Post text saved."},
    "userbot.template.bad": {
        "uz": "Bu qiymat yaroqsiz (havola, @ belgisi yoki juda uzun matn mumkin emas). Qayta kiriting.",
        "ru": "Это значение недопустимо (ссылки, @ и слишком длинный текст нельзя). Введите ещё раз.",
        "en": "That value is not allowed (no links, @ or very long text). Please enter it again.",
    },
    # --- pause / resume / logout ---
    "userbot.paused": {"uz": "⏸ Avto-e'lon to'xtatildi.", "ru": "⏸ Автообъявления приостановлены.",
                       "en": "⏸ Auto-posting paused."},
    "userbot.resumed": {"uz": "▶️ Avto-e'lon davom etadi.", "ru": "▶️ Автообъявления продолжаются.",
                        "en": "▶️ Auto-posting resumed."},
    "userbot.logout.ask": {
        "uz": "Hisobni uzsangiz, Telegram sessiyasi tugatiladi va bizdagi nusxa o'chiriladi. Guruhlar ro'yxati ham "
              "o'chadi. Davom etamizmi?",
        "ru": "При отключении сессия Telegram завершается, а наша копия удаляется. Список групп тоже удаляется. "
              "Продолжить?",
        "en": "Disconnecting ends the Telegram session and deletes our copy. The group list is deleted too. Continue?",
    },
    "userbot.logout.done": {"uz": "✅ Hisob uzildi, sessiya o'chirildi.", "ru": "✅ Аккаунт отключён, сессия удалена.",
                            "en": "✅ Account disconnected, session deleted."},
    # --- errors (domain error codes → text) ---
    "userbot.err.consent_required": {"uz": "Avval rozilik ekranida \"Roziman\" ni bosing.",
                                     "ru": "Сначала нажмите «Согласен» на экране риска.",
                                     "en": "Please tap \"I agree\" on the risk screen first."},
    "userbot.err.not_driver": {"uz": "Bu funksiya faqat haydovchilar uchun.", "ru": "Функция только для водителей.",
                               "en": "This feature is for drivers only."},
    "userbot.err.plan_required": {
        "uz": "Avto-e'lon Pro yoki Biznes tarifida mavjud.", "ru": "Автообъявления доступны на тарифах Pro и Бизнес.",
        "en": "Auto-posting is available on the Pro and Business plans.",
    },
    "userbot.err.group_limit": {"uz": "Tarifingizdagi guruhlar chegarasiga yetdingiz.",
                                "ru": "Достигнут лимит групп вашего тарифа.", "en": "You reached your plan's group limit."},
    "userbot.err.not_connected": {"uz": "Avval hisobni ulang.", "ru": "Сначала подключите аккаунт.",
                                  "en": "Connect your account first."},
    "userbot.err.risk_ack_required": {
        "uz": "Xavfsiz chegaradan pastga tushish uchun xavfni tan olish kerak.",
        "ru": "Чтобы опуститься ниже безопасного порога, нужно подтвердить риск.",
        "en": "You must acknowledge the risk to go below the safe threshold.",
    },
    "userbot.err.flood_wait": {"uz": "Telegram kutishni so'radi. Keyinroq urinib ko'ring.",
                               "ru": "Telegram просит подождать. Попробуйте позже.",
                               "en": "Telegram asked to wait. Try again later."},
    "userbot.err.generic": {"uz": "Xatolik yuz berdi. Qayta urinib ko'ring.", "ru": "Произошла ошибка. Попробуйте ещё раз.",
                            "en": "Something went wrong. Please try again."},
    # --- driver notifications from the worker ---
    "userbot.notify.flood_wait": {
        "uz": "⏳ Telegram avto-e'longa kutishni so'radi. E'lonlar {until} gacha to'xtatildi, keyin o'zi davom etadi.",
        "ru": "⏳ Telegram попросил подождать. Объявления приостановлены до {until}, затем продолжатся сами.",
        "en": "⏳ Telegram asked to wait. Posting is paused until {until} and will then resume by itself.",
    },
    "userbot.notify.peer_flood": {
        "uz": "⛔ Telegram hisobingizga cheklov qo'ydi (PEER_FLOOD). Avto-e'lon to'xtatildi. Telegram cheklovini "
              "chetlab o'tmaymiz. @SpamBot orqali hisobingiz holatini tekshiring, keyin /elon orqali qayta ulang.",
        "ru": "⛔ Telegram ограничил ваш аккаунт (PEER_FLOOD). Автообъявления остановлены. Мы не обходим ограничения "
              "Telegram. Проверьте статус аккаунта через @SpamBot и подключите заново через /elon.",
        "en": "⛔ Telegram limited your account (PEER_FLOOD). Auto-posting is stopped. We never bypass Telegram "
              "limits. Check your account in @SpamBot, then reconnect via /elon.",
    },
    "userbot.notify.group_stopped": {
        "uz": "⛔ \"{title}\" guruhiga e'lon yuborish to'xtatildi ({reason}). Boshqa guruhlar ishlashda davom etadi.",
        "ru": "⛔ Публикация в группе «{title}» остановлена ({reason}). Остальные группы продолжают работать.",
        "en": "⛔ Posting to \"{title}\" stopped ({reason}). Your other groups keep working.",
    },
    "userbot.notify.account_stopped": {
        "uz": "⛔ Avto-e'lon to'xtatildi ({reason}). Hisobingizni /elon orqali qayta ulang.",
        "ru": "⛔ Автообъявления остановлены ({reason}). Подключите аккаунт заново через /elon.",
        "en": "⛔ Auto-posting stopped ({reason}). Reconnect your account via /elon.",
    },
    # --- text posted into groups (plain text, from the driver's own account) ---
    "userbot.post.route": {"uz": "🚕 {from_} → {to}", "ru": "🚕 {from_} → {to}", "en": "🚕 {from_} → {to}"},
    "userbot.post.time": {"uz": "🕒 {time}", "ru": "🕒 {time}", "en": "🕒 {time}"},
    "userbot.post.seats": {"uz": "💺 Bo'sh joy: {seats}", "ru": "💺 Свободных мест: {seats}",
                           "en": "💺 Free seats: {seats}"},
    "userbot.post.price": {"uz": "💰 {price} so'm", "ru": "💰 {price} сум", "en": "💰 {price} UZS"},
    "userbot.post.contact": {"uz": "📲 @{bot} orqali bog'laning", "ru": "📲 Свяжитесь через @{bot}",
                             "en": "📲 Contact via @{bot}"},

    # --- group feed cards (decision 73): sent by @tulporgobot to the driver's channel or chat ---
    "feed.kind.passenger": {"uz": "🚕 Yo'lovchi", "ru": "🚕 Пассажир", "en": "🚕 Passenger"},
    "feed.kind.parcel": {"uz": "📦 Pochta", "ru": "📦 Посылка", "en": "📦 Parcel"},
    "feed.kind.cargo": {"uz": "🚚 Yuk", "ru": "🚚 Груз", "en": "🚚 Cargo"},
    "feed.kind.delivery": {"uz": "🛍 Dostavka", "ru": "🛍 Доставка", "en": "🛍 Delivery"},
    "feed.kind.bazaar": {"uz": "🧺 Bozor", "ru": "🧺 Базар", "en": "🧺 Bazaar"},
    "feed.when.now": {"uz": "hozir", "ru": "сейчас", "en": "now"},
    "feed.when.today": {"uz": "bugun {hm}", "ru": "сегодня {hm}", "en": "today {hm}"},
    "feed.when.tomorrow": {"uz": "ertaga {hm}", "ru": "завтра {hm}", "en": "tomorrow {hm}"},
    "feed.when.date": {"uz": "{date} {hm}", "ru": "{date} {hm}", "en": "{date} {hm}"},
    "feed.seats": {"uz": "{n} kishi", "ru": "{n} чел.", "en": "{n} people"},
    "feed.cargo": {"uz": "yuk bilan", "ru": "с грузом", "en": "with luggage"},
    "feed.unknown_place": {"uz": "?", "ru": "?", "en": "?"},
    "feed.groups": {"uz": "Guruh: {titles}", "ru": "Группа: {titles}", "en": "Group: {titles}"},
    "feed.filter": {"uz": "Filtr: {name}", "ru": "Фильтр: {name}", "en": "Filter: {name}"},
    "feed.open": {"uz": "💬 {title}", "ru": "💬 {title}", "en": "💬 {title}"},
    "feed.taken": {"uz": "✅ Olindi", "ru": "✅ Взял", "en": "✅ Taken"},
    "feed.pause": {"uz": "⏸ Pauza", "ru": "⏸ Пауза", "en": "⏸ Pause"},
    "feed.gone": {
        "uz": "🚫 Yo'lovchi e'lonni o'chirdi — taksi topgan bo'lishi mumkin. Kartochka 10 daqiqadan keyin o'chadi.",
        "ru": "🚫 Пассажир удалил объявление — возможно, уже нашёл такси. Карточка исчезнет через 10 минут.",
        "en": "🚫 The passenger deleted the post — they have probably found a taxi. This card disappears in 10 minutes.",
    },
    "feed.menu": {
        "uz": "<b>🔎 Yo'lovchi qidirish</b>\n\nGuruhlaringizdagi so'rovlar filtrlaringiz bo'yicha sizga keladi.\n"
              "Holat: {state}\nKartochkalar: {channel}\nFiltrlar: {count}",
        "ru": "<b>🔎 Поиск пассажиров</b>\n\nЗапросы из ваших групп приходят вам по вашим фильтрам.\n"
              "Статус: {state}\nКарточки: {channel}\nФильтры: {count}",
        "en": "<b>🔎 Passenger search</b>\n\nRequests from your groups come to you by your filters.\n"
              "Status: {state}\nCards: {channel}\nFilters: {count}",
    },
    "feed.state.on": {"uz": "yoqilgan", "ru": "включён", "en": "on"},
    "feed.state.paused": {"uz": "pauzada", "ru": "на паузе", "en": "paused"},
    "feed.channel.linked": {"uz": "o'z kanalingizga", "ru": "в ваш канал", "en": "to your channel"},
    "feed.channel.none": {
        "uz": "shu chatga. O'z kanalingizga olish uchun @{bot} ni kanalingizga admin qiling",
        "ru": "в этот чат. Чтобы получать в свой канал, сделайте @{bot} админом канала",
        "en": "to this chat. To get them in your channel, make @{bot} an admin there",
    },
    "feed.channel.ok": {
        "uz": "✅ TulporGo: yo'lovchi so'rovlari shu yerga keladi.",
        "ru": "✅ TulporGo: запросы пассажиров будут приходить сюда.",
        "en": "✅ TulporGo: passenger requests will arrive here.",
    },
    "feed.btn.menu": {"uz": "🔎 Yo'lovchi qidirish", "ru": "🔎 Поиск пассажиров", "en": "🔎 Passenger search"},
    "feed.btn.edit": {"uz": "Filtrlarni sozlash", "ru": "Настроить фильтры", "en": "Edit filters"},
    "feed.btn.pause_all": {"uz": "⏸ Hammasini pauza", "ru": "⏸ Пауза для всех", "en": "⏸ Pause all"},
    "feed.btn.resume_all": {"uz": "▶️ Davom ettirish", "ru": "▶️ Продолжить", "en": "▶️ Resume"},
    "feed.btn.back": {"uz": "⬅️ Orqaga", "ru": "⬅️ Назад", "en": "⬅️ Back"},
    "feed.not_driver": {"uz": "Bu bo'lim haydovchilar uchun.", "ru": "Раздел для водителей.",
                        "en": "This is for drivers."},
    "feed.not_yours": {"uz": "Bu sizning kartochkangiz emas.", "ru": "Это не ваша карточка.",
                       "en": "This is not your card."},
    "feed.taken.ok": {"uz": "Olindi ✅", "ru": "Взято ✅", "en": "Taken ✅"},
    "feed.paused.ok": {
        "uz": "Yo'lovchi qidirish pauzada. /elon → «Yo'lovchi qidirish» dan davom ettiring.",
        "ru": "Поиск пассажиров на паузе. Продолжить: /elon → «Поиск пассажиров».",
        "en": "Passenger search is paused. Resume in /elon → «Passenger search».",
    },
}
