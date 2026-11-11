# Places dataset: sources

All sources were retrieved on 2026-11-10. None of the pages or files states a licence unless noted below.

## regions_districts.csv (206 rows: 175 tuman + 31 shahar, 14 regions)

| Source | Date | Terms | Used for |
|---|---|---|---|
| https://stat.uz/uploads/docs/soato(mhobt)_2020.xlsx (State Statistics Committee, order no. 59 of 2020-07-22, annex 1, MHOBT/SOATO classifier) | July 2020 | none stated | Region and district codes, names, tuman/shahar split (all rows except Ko'kdala) |
| https://samarkand.uz/uploads/opendata/klassifikator.pdf (Samarqand regional khokimiyat open data) | undated | none stated | Cross-check of the 16 Samarqand codes: identical to the xlsx |
| https://raw.githubusercontent.com/MIMAXUZ/uzbekistan-regions-data/master/JSON/districts.json | 2025-04-09 | GPL-3.0 (repo licence) | Only the code 1710240 for Ko'kdala (created after 2020, absent from the xlsx) |
| https://en.wikipedia.org/wiki/Districts_of_Uzbekistan (raw wikitext) | accessed 2026-11 | CC BY-SA | Cross-check: 175 tumans, Ko'kdala listed, Davlatobod and Yangi Namangan not listed |
| https://data.egov.uz/apiClient/Main/GetMainData?GuidId=6117ad2496188a0f14ac91cd (dataset 2-001-1804, "Ma'muriy-hududiy birliklar soni", updated 2025-08-01) | 2025-08-01 | none stated | Cross-check of totals: 206 units, Samarqand 16 units and 1102 mahallas |

Name changes against the 2020 xlsx (current Uzbek Latin spelling): Marxamat to Marhamat, Shaxrixon to Shahrixon, Tayloq to Toyloq, Pskent to Piskent, Shayxontoxur to Shayxontohur, Ellikkala to Ellikqal'a. Cities are written as "<name> shahri" so they do not collide with a tuman of the same name (Andijon, Samarqand, Kattaqo'rg'on and others).

Coverage: Qoraqalpog'iston 17, Andijon 16, Buxoro 13, Jizzax 13, Qashqadaryo 16, Navoiy 11, Namangan 12, Samarqand 16, Surxondaryo 15, Sirdaryo 11, Toshkent viloyati 22, Farg'ona 19, Xorazm 13, Toshkent shahri 12.

## samarqand_mahallas.csv (1080 rows, 16 districts)

| Source | Date | Terms | Coverage |
|---|---|---|---|
| https://data.egov.uz/apiClient/Main/GetById?id=61135273db32b99538e08527 (dataset 6-008-0010 of Samarqand viloyati hokimiyati, "Fuqarolarning o'zini o'zi boshqarish organlari to'g'risida ma'lumot"; rows via POST `apiClient/Main/GetMainData?GuidId=61135273db32b99538e08527`) | updated 2026-10-21 | none stated | Official, Cyrillic, transliterated by us. Bulung'ur 49, Jomboy 38, Kattaqo'rg'on tumani 68, Samarqand shahri 197, Toyloq 50, Urgut 116 (518 rows) |
| https://github.com/kenjebaev/regions/blob/master/regions.json (community file, 10 035 quarters) | repo last pushed 2025-04-16, data older | no licence file | Unofficial, older vintage. Ishtixon 62, Narpay 55, Nurobod 34, Oqdaryo 33, Pastdarg'om 105, Paxtachi 63, Payariq 64, Qo'shrabot 38, Samarqand tumani 73, Kattaqo'rg'on shahri 35 (562 rows) |

Excluded on purpose:
- egov: 787 rows exist, but the block labelled "Paxtachi t" (261 rows) mixes several districts, and 7 single rows carry unreliable labels (for example "Bahrin" is under Ishtixon but is an Urgut mahalla elsewhere). These 268 rows were dropped.
- kenjebaev: 124 QFY, 13 SHFY, rows without an MFY suffix (6 names), 2 rows with corrupted characters ("?"), 4 duplicates.
- The MHOBT xlsx lists only qishloq fuqarolar yig'inlari and shaharchalar (about 250 in Samarqand), not mahallas, so it was not used here.

Official reference counts (stat agency via egov dataset 2-001-1804, 2025-08-01): Samarqand viloyati has 1102 mahallas. The file has 1080 (98 percent).

Spelling (2026-11-11): the kenjebaev rows often drop Uzbek letters (Kurgon, Kushrabot, Jush ota). 53 of the 562 names
were restored from the official egov list above (Cyrillic, all 787 rows, district labels ignored): a name is replaced
only when the official one is the same word with letters restored (o'/g', q, h) and loses none, so egov's own lossy
forms (Dustlik, Urikzor) never replace a correct name. 262 kenjebaev names are not in the egov list and stay as they
are; Qovunchi and 8 more Qo'shrabot names (Buloq, Chinoq, Qo'shtamg'ali, Oqchopsoy, O'rtasoy, Yuqori Jo'sh, Yuqori
Saroy, Qo'rolos; Novkat stays) were confirmed by the owner. `renames.csv` lists the owner's renames that no key can
link (Yu.Saroy -> Yuqori Saroy), so an existing database renames the place instead of adding a second one. Seed renames such places in place (same id), and matching folds o/u, so
"Kurgon" still finds Qo'rg'on.

## Not retrievable

- mahalla.uz and api.mahalla.uz: no connection from this network.
- stat.uz returned 403 for the front page; the xlsx under /uploads/ downloaded normally.
- A full Samarqand mahalla list on lex.uz or samarkand.uz was not found.
