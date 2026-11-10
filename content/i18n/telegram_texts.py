"""TulporGo Telegram texts, stage 1 of TELEGRAM-REJA.md. APPROVED by Saidakbar aka 2026-11-10 (decision 40);
any change needs his approval again (show via send_preview.py first).

Canonical Uzbek is written in the current Latin alphabet with plain ' (o', g', tutuq); build_texts.py derives
uz_new / uz_latn / uz_cyrl (alphabet.py). Use «» for quotations, never ASCII quotes.
Facts only from QARORLAR.md: passengers free (#9), drivers send offers and passenger chooses (#6), price can be
negotiated (#7), verified badge (#12), rating + trip sharing (#13), 7-day free trial for drivers (#10).

scope "bot":  localized by Telegram per language_code (profile: uz/ru/en) and inside the bot (5 languages).
scope "chat": channel/group texts are not localized by Telegram: uz_new main text + ru (decision 29).
Buttons: label without emoji; `icon` = pose whose custom emoji goes on the button (Premium owner, Bot API 9.4).
"""

TEXTS = {
    # ---------------- bot @tulporgobot ----------------
    "bot.name": dict(scope="bot", limit=64, uz="TulporGo", ru="TulporGo", en="TulporGo"),

    "bot.short_description": dict(scope="bot", limit=120,
        uz="Taksi Telegram ichida: yo'nalishni yozing, haydovchilar taklif yuboradi, siz tanlaysiz. Yo'lovchi uchun bepul.",
        ru="Такси прямо в Telegram: напишите маршрут, водители пришлют предложения, вы выберете. Для пассажиров бесплатно.",
        en="Taxi right in Telegram: send your route, drivers make offers, you choose. Free for passengers."),

    "bot.description": dict(scope="bot", limit=512,
        uz="TulporGo — taksini Telegram'dan chaqirish xizmati.\n\n"
           "🚕 Qayerdan va qayerga borishingizni yozing.\n"
           "💬 Haydovchilar narxi va mashinasi bilan taklif yuboradi.\n"
           "✅ Ma'qulini o'zingiz tanlaysiz, narxni kelishish ham mumkin.\n\n"
           "🛡 Reyting, tasdiqlangan haydovchilar belgisi va qatnovni yaqinlaringizga ulashish.\n\n"
           "Yo'lovchi uchun bepul. Boshlash uchun pastdagi tugmani bosing.",
        ru="TulporGo — сервис вызова такси прямо в Telegram.\n\n"
           "🚕 Напишите, откуда и куда вам нужно.\n"
           "💬 Водители пришлют предложения с ценой и машиной.\n"
           "✅ Выберите подходящее — о цене можно договориться.\n\n"
           "🛡 Рейтинг, отметка проверенных водителей и возможность поделиться поездкой с близкими.\n\n"
           "Для пассажиров бесплатно. Чтобы начать, нажмите кнопку внизу.",
        en="TulporGo is a taxi service right inside Telegram.\n\n"
           "🚕 Tell us where you are and where you're going.\n"
           "💬 Drivers send offers with their price and car.\n"
           "✅ Pick the one you like — you can also agree on the price.\n\n"
           "🛡 Ratings, a verified-driver badge and trip sharing with your family.\n\n"
           "Free for passengers. Tap the button below to start."),

    "bot.menu_button": dict(scope="bot", limit=24, uz="Taksi chaqirish", ru="Вызвать такси", en="Order a taxi"),

    # command -> description (1-256); passenger menu, drivers get the extra two via a per-chat scope
    "bot.cmd.start": dict(scope="bot", limit=256, command="start",
        uz="Boshlash va taksi chaqirish", ru="Начать и вызвать такси", en="Start and order a taxi"),
    "bot.cmd.qatnovlarim": dict(scope="bot", limit=256, command="qatnovlarim",
        uz="Mening qatnovlarim", ru="Мои поездки", en="My trips"),
    "bot.cmd.til": dict(scope="bot", limit=256, command="til",
        uz="Tilni o'zgartirish", ru="Сменить язык", en="Change language"),
    "bot.cmd.yordam": dict(scope="bot", limit=256, command="yordam",
        uz="Yordam va savollar", ru="Помощь и вопросы", en="Help and questions"),
    "bot.cmd.elon": dict(scope="bot", limit=256, command="elon", drivers=True,
        uz="E'lon berish (haydovchilar uchun)", ru="Разместить объявление (для водителей)", en="Post a ride offer (drivers)"),
    "bot.cmd.obuna": dict(scope="bot", limit=256, command="obuna", drivers=True,
        uz="Obuna va tariflar", ru="Подписка и тарифы", en="Subscription and plans"),

    "bot.start": dict(scope="bot", limit=4096,
        uz="Xush kelibsiz! 👋\n"
           "Qayerga borasiz? «Taksi chaqirish» tugmasini bosing yoki yo'nalishni yozing, masalan: "
           "Qo'shrabot → Samarqand.\n"
           "Haydovchilarning takliflari shu yerga keladi.",
        ru="Добро пожаловать! 👋\n"
           "Куда едем? Нажмите «Вызвать такси» или напишите маршрут, например: Кошрабад → Самарканд.\n"
           "Предложения водителей придут сюда.",
        en="Welcome! 👋\n"
           "Where are you going? Tap «Order a taxi» or type your route, e.g. Qoshrabot → Samarkand.\n"
           "Drivers' offers will arrive here.",
        buttons=[dict(style="primary", icon="09-19-rulda", fallback="🚕",
                      uz="Taksi chaqirish", ru="Вызвать такси", en="Order a taxi"),
                 dict(icon="09-07-qol-berishyapti", fallback="🤝",
                      uz="Haydovchiman", ru="Я водитель", en="I'm a driver")]),

    "bot.coming_soon": dict(scope="bot", limit=4096,
        uz="TulporGo tez orada ishga tushadi 🚀\nBirinchilardan bo'lib bilish uchun kanalimizga obuna bo'ling.",
        ru="TulporGo скоро запустится 🚀\nПодпишитесь на канал, чтобы узнать об этом первыми.",
        en="TulporGo is launching soon 🚀\nFollow our channel to be the first to know.",
        buttons=[dict(url="https://t.me/tulporgo", icon="09-03-uchib-ketyapti", fallback="📢",
                      uz="Kanalga o'tish", ru="Перейти в канал", en="Open the channel")]),

    # ---------------- channel @tulporgo ----------------
    "channel.description": dict(scope="chat", limit=255,
        uz="TulporGo — taksini Telegram'dan chaqirish xizmati. Yangiliklar va yo'nalishlar.\n"
           "Taksi: @tulporgobot · Savollar: @tulporgo_chat",
        ru="Вызов такси в Telegram. Новости и маршруты."),

    "channel.welcome": dict(scope="chat", limit=1024, photo="09-01-salomlashadi",
        uz="Xush kelibsiz! 👋\n"
           "TulporGo — taksini Telegram'dan chaqirish:\n"
           "1️⃣ Botga yo'nalishingizni yozasiz.\n"
           "2️⃣ Haydovchilar narx va mashina bilan taklif yuboradi.\n"
           "3️⃣ Ma'qulini o'zingiz tanlaysiz.\n"
           "Bu kanalda — yangiliklar, yo'nalishlar va foydali maslahatlar.",
        ru="Добро пожаловать! TulporGo — вызов такси в Telegram: напишите маршрут боту, водители пришлют "
           "предложения, выберите подходящее. В канале — новости, маршруты и полезные советы.",
        buttons=[dict(url="https://t.me/tulporgobot", style="primary", icon="09-19-rulda", fallback="🚕",
                      uz="Taksi chaqirish", ru="Вызвать такси"),
                 dict(url="https://t.me/tulporgobot?start=driver", icon="09-07-qol-berishyapti", fallback="🤝",
                      uz="Haydovchi bo'lish", ru="Стать водителем")]),

    "channel.pinned": dict(scope="chat", limit=1024,
        uz="Bu yerdan boshlang 👇\nTulporGo qanday ishlaydi — 3 qadamda. Rasmlarni suring.",
        ru="Начните отсюда: как работает TulporGo — в 3 шага. Листайте картинки."),

    # ---------------- Q&A group @tulporgo_chat ----------------
    "chat.description": dict(scope="chat", limit=255,
        uz="TulporGo bo'yicha savol-javob: yo'lovchilar va haydovchilar uchun.\nTaksi chaqirish: @tulporgobot",
        ru="Вопросы и ответы о TulporGo."),

    "chat.rules": dict(scope="chat", limit=4096,
        uz="Guruh qoidalari:\n"
           "1. Bir-birimizni hurmat qilamiz: haqorat, siyosiy va diniy bahslar yo'q.\n"
           "2. Reklama va boshqa xizmatlar havolalari o'chiriladi.\n"
           "3. Taksi e'lonlari bu yerda emas — @tulporgobot orqali.\n"
           "4. Telefon raqami va karta ma'lumotlarini ochiq yozmang.\n"
           "5. Shikoyat bo'lsa — botda /yordam yoki adminga yozing.",
        ru="Правила: уважаем друг друга, без оскорблений, политических и религиозных споров; реклама и "
           "ссылки на другие сервисы удаляются; объявления такси — только через @tulporgobot; не публикуйте "
           "телефон и данные карты; жалобы — /yordam в боте или админу."),

    "chat.welcome": dict(scope="chat", limit=1024,
        uz="Xush kelibsiz! 👋\nBu yerda TulporGo haqida savol berishingiz mumkin. "
           "Avval qoidalar va tez-tez so'raladigan savollarni ko'ring.",
        ru="Добро пожаловать! Здесь можно задать вопрос о TulporGo. Сначала посмотрите правила и частые вопросы.",
        buttons=[dict(url="https://t.me/tulporgobot?start=faq", icon="09-09-oylanyapti", fallback="❓",
                      uz="Savol-javoblar", ru="Частые вопросы"),
                 dict(url="https://t.me/tulporgobot", style="primary", icon="09-19-rulda", fallback="🚕",
                      uz="Taksi chaqirish", ru="Вызвать такси")]),

    # ---------------- drivers' group (no username, Hidden in the Community) ----------------
    "drivers.description": dict(scope="chat", limit=255,
        uz="TulporGo haydovchilari uchun yopiq guruh. Faqat tasdiqlangan haydovchilar.",
        ru="Закрытая группа водителей TulporGo."),

    "drivers.welcome": dict(scope="chat", limit=1024,
        uz="Xush kelibsiz, hamkasb! 🚕\n"
           "Bu guruh — faqat TulporGo haydovchilari uchun.\n"
           "• Yangiliklar va qoidalar shu yerda e'lon qilinadi.\n"
           "• E'lon berish va obuna — @tulporgobot orqali: /elon, /obuna.\n"
           "• Yo'lovchilar ma'lumotlarini guruhda ulashmang.\n"
           "Birinchi 7 kun — bepul sinov.",
        ru="Добро пожаловать, коллега! Группа только для водителей TulporGo. Объявления и подписка — через "
           "@tulporgobot (/elon, /obuna). Не публикуйте данные пассажиров. Первые 7 дней — бесплатно.",
        buttons=[dict(url="https://t.me/tulporgobot?start=elon", style="success", icon="09-02-ongga-korsatadi",
                      fallback="📣", uz="E'lon berish", ru="Объявление"),
                 dict(url="https://t.me/tulporgobot?start=obuna", icon="09-49-kalkulyator", fallback="💳",
                      uz="Obuna va tariflar", ru="Подписка и тарифы")]),
}

# shown before the user's language is known; fixed, not converted
LANGUAGE_PICKER = dict(
    text="Tilni tanlang · Выберите язык · Choose language",
    buttons=[("uz_new", "Özbekça"), ("uz_latn", "Oʻzbekcha"), ("uz_cyrl", "Ўзбекча"),
             ("ru", "Русский"), ("en", "English")])
