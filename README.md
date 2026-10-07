# University Intelligence & AI Decision System

Universitet boshqaruvi uchun ma'lumotlarga asoslangan qarorlarni qo'llab-quvvatlash tizimi
(Data-Driven Decision Support System). Data Engineering, Data Analytics, Machine Learning va
AI Agent bitta biznes muammosi atrofida birlashtirilgan: **qaysi talabalar va yo'nalishlar
xavf ostida, nima sababdan va rahbariyat nima qilishi kerak?**

> **Muhim.** Barcha ma'lumotlar **sintetik** (sun'iy yaratilgan) - bu haqiqiy universitet
> ma'lumoti emas. Bashoratlar ehtimollik bo'lib, kafolat emas.

## Haqiqiy universitet tizimiga moslik

Talabalar sintetik, lekin tuzilma va qoidalar O'zbekiston oliy ta'limidagi kredit-modul
tizimiga mos:

| Qoida | Tizimda |
|---|---|
| 100 ballik baholash | Joriy nazorat 20 + oraliq nazorat 30 + yakuniy nazorat 50 |
| Baholar | 90-100 = 5 (a'lo), 70-89 = 4 (yaxshi), 60-69 = 3 (qoniqarli), 60 dan past = 2 (qoniqarsiz) |
| O'tish bali | 60; undan past natija - akademik qarzdorlik |
| Davomat qoidasi | Sababsiz qoldirilgan darslar 25% dan oshsa, talaba yakuniy nazoratga qo'yilmaydi |
| GPA | Kreditlar bo'yicha vaznlangan o'rtacha baho (5 ballik shkala) |
| Tuzilma | Fakultet → kafedra → akademik guruh (masalan `IQ-23-04`) → talaba; Kuz va Bahor semestrlari |
| To'lov shakli | Davlat granti yoki to'lov-kontrakt, semestr bo'yicha hisob |

Nazoratlar o'rtasidagi ball taqsimoti universitetlarda farq qiladi: `config.py` dagi
`SCORE_MAX` ni o'z universitetingiz nizomiga moslang. Haqiqiy ma'lumotga o'tish uchun kod
o'zgarmaydi - universitet tizimidan (masalan HEMIS) olingan eksport fayllari shu ustunlar bilan
`01_Data/raw` papkasiga qo'yiladi.

## Dashboard sahifalari

| Sahifa | Javob beradigan savol |
|---|---|
| Umumiy ko'rinish | Hozir nima bo'lyapti va nimaga e'tibor berish kerak? |
| Fakultetlar | Qaysi fakultet yaxshi, qaysi birida muammo bor? |
| Imtihon natijalari | Oraliq va yakuniy nazorat qanday o'tdi, kimlar qo'yilmadi, qayerda pasayish bor? |
| Xavf ostidagi talabalar | Kimga yordam kerak, nima uchun, va u uchun nima qilindi (choralar qaydi)? |
| «Agar...» ssenariylari | Qaror qabul qilsak, natija qanday o'zgaradi? |
| AI yordamchi | Savolni oddiy tilda berish |
| Boshqa | Moliya, o'qituvchilar, ma'lumotlar sifati va yangilash |

## Arxitektura

```
Xom fayllar (CSV / Excel / JSON)           01_Data/raw
        │  Python ETL: tozalash, tekshirish, transformatsiya        02_ETL
        ▼
SQL Server: stg (staging) → dw (yulduz sxemasi) → etl (nazorat) → ml     03_SQL, 04_Data_Warehouse
        │
        ├── Tahlil qatlami: KPI, salomatlik bali, alert, anomaliya        05_Analytics
        ├── ML: xavf bashorati + tushuntirish                              06_ML
        ├── Simulyatsiya: «agar...» ssenariylari                           09_Simulation
        ▼
Dashboard (Streamlit, sof Python)  +  AI Agent (LLM + tool calling)       08_Dashboard, 07_AI_Agent
        ▼
Rahbariyat qarori
```

Power BI ishlatilmaydi: uning o'rnida **Streamlit** dashboard (HTML/CSS/JavaScript yozilmaydi,
faqat Python). U brauzerda sayt sifatida ochiladi va ombor yangilanganda o'zi yangilanadi.

## Ishga tushirish

Talablar: Windows, Python 3.12+, SQL Server (lokal, Windows autentifikatsiya),
«ODBC Driver 17 for SQL Server».

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python 01_Data\generate_data.py --reset
.venv\Scripts\python run_pipeline.py --rebuild
.venv\Scripts\python -m streamlit run 08_Dashboard\app.py
```

Oxirgi buyruq o'rniga `start_dashboard.bat` faylini ikki marta bosish ham mumkin.
Dashboard manzili: http://localhost:8610

### Kirish va rollar

Dashboard qulflangan ekran bilan ochiladi: login va parol so'raladi. Har bir hisobning roli bor,
va foydalanuvchi nimani ko'rishini shu rol belgilaydi (rolni dashboard ichida almashtirib bo'lmaydi):

| Rol | Nimani ko'radi |
|---|---|
| `rahbariyat` | Hamma narsa: barcha fakultetlar, talabalar ro'yxati, konveyerni ishga tushirish, erkin SQL |
| `dekan` | Faqat hisobga biriktirilgan fakultet va uning talabalari |
| `oqituvchi` | Faqat umumlashtirilgan ko'rsatkichlar, talabalar ismisiz |

```bash
.venv\Scripts\python 08_Dashboard\set_password.py            # hisob yaratish yoki parol/rolni o'zgartirish
.venv\Scripts\python 08_Dashboard\set_password.py --list     # hisoblar ro'yxati
.venv\Scripts\python 08_Dashboard\set_password.py --delete LOGIN
```

Hisoblar `.streamlit/secrets.toml` faylida saqlanadi (parolning o'zi emas, faqat tuzlangan xeshi);
bu fayl git'ga kirmaydi. Kirgandan so'ng sahifani yangilash tizimdan chiqarmaydi: brauzerda 12 soat
amal qiladigan imzolangan sessiya saqlanadi (parol o'zgarsa yoki «Chiqish» bosilsa, u bekor bo'ladi).
Yorug'/tungi rejim tugmasi faqat shu brauzer uchun amal qiladi.

Xavf ostidagi talaba uchun ko'rilgan choralar (suhbat, tyutorlik, ...) va ularning natijasi
`app.Intervention` jadvaliga yoziladi. Bu - fayllardan qayta tiklab bo'lmaydigan yagona ma'lumot,
shuning uchun `--rebuild` uni avval faylga saqlab, qayta qurilgach tiklaydi.

### Internetda ulashish

- **Vaqtincha havola** (kompyuter yoniq bo'lganda): avval `start_dashboard.bat`, so'ng
  `share_dashboard.bat` - u `https://....trycloudflare.com` manzilini chiqaradi.
- **Doimiy namoyish** (kompyuter o'chiq bo'lsa ham ishlaydi): Streamlit Community Cloud'da.
  U yerdan SQL Server ko'rinmaydi, shuning uchun dashboard *oflayn nusxa* rejimida ishlaydi:
  omborning saqlangan nusxasini (`01_Data/offline`, Parquet) o'qiydi. Barcha sahifalar ishlaydi;
  konveyerni ishga tushirish, erkin SQL va choralarni saqlash u yerda o'chirilgan.

  ```bash
  .venv\Scripts\python 05_Analytics\offline.py      # nusxani yangilash, so'ng commit va push
  ```

  Joylashtirish: repozitoriy GitHub'da bo'lishi kerak; share.streamlit.io'da yangi ilova,
  asosiy fayl `08_Dashboard/app.py`; *Secrets* maydoniga `.streamlit/secrets.toml` mazmuni
  ko'chiriladi (hisoblar shu yerdan o'qiladi). Linux'da oflayn rejim o'zi yoqiladi; Windows'da
  sinab ko'rish uchun `UIS_OFFLINE=1` o'rnating.

SQL Server boshqa nomda bo'lsa: `UIS_SQL_SERVER` muhit o'zgaruvchisini o'rnating
(masalan `localhost\SQLEXPRESS`).

### AI yordamchi uchun kalit

AI yordamchi Claude API orqali ishlaydi. Kalit kodga yozilmaydi - muhit o'zgaruvchisi sifatida beriladi:

```bash
setx ANTHROPIC_API_KEY "sizning-kalitingiz"
```

Kalit bo'lmasa ham tizim ishlaydi: AI sahifasida «tayyor savollar» oflayn rejimda bevosita
vositalar natijasidan javob beradi.

## Ma'lumot yangilanishi

Eng oson yo'l: `update_data.bat` faylini ikki marta bosing (istalgan papkadan ishlaydi).
Quyidagi buyruqlar esa **loyiha papkasi ichidan** ishga tushiriladi
(`cd "D:\new project\University_Intelligence_System"`), aks holda `.venv` topilmaydi;
`python` o'rniga `.venv\Scripts\python` yozing.

| Buyruq | Nima qiladi |
|---|---|
| `python run_pipeline.py` | Yangi yoki o'zgargan fayllarni yuklaydi, talabalar xavfini qayta hisoblaydi |
| `python run_pipeline.py --new-semester` | Yangi semestr kelishini simulyatsiya qiladi, so'ng yuklaydi |
| `python run_pipeline.py --retrain` | Yuklaydi va ML modellarini qayta o'qitadi |
| `python run_pipeline.py --rebuild` | Bazani o'chirib, hammasini noldan quradi |

Yangi fayl (`grades_<nom>.csv` kabi) `01_Data/raw` papkasiga qo'yilsa, konveyer uni fayl
xeshi bo'yicha taniydi. Omborga yuklash `MERGE` orqali bajariladi, shuning uchun konveyerni
qayta ishga tushirish dublikat yaratmaydi. Dashboard yangi versiyani 30 soniya ichida o'zi ko'rsatadi.

## Papkalar

| Papka | Vazifasi |
|---|---|
| `01_Data` | Sintetik ma'lumot generatori, o'zbekcha ma'lumotnomalar, `raw/` xom fayllar |
| `02_ETL` | ETL konveyeri: extract → clean → validate → stage → merge → test |
| `03_SQL` | Sxemalar, ETL nazorat jadvallari, staging jadvallari, AI agent uchun faqat-o'qish foydalanuvchisi, choralar jadvali |
| `04_Data_Warehouse` | Yulduz sxemasi: o'lchovlar, faktlar, yuklash protseduralari |
| `05_Analytics` | Barcha KPI, salomatlik bali, alert va anomaliyalarning yagona ta'rifi; choralar qaydi |
| `06_ML` | Xavf modeli: o'qitish, baholash, tushuntirish, talabalarni baholash |
| `07_AI_Agent` | AI agent va uning 9 ta vositasi, rolga asoslangan cheklovlar |
| `08_Dashboard` | Streamlit dashboard (7 sahifa) |
| `09_Simulation` | «Agar...» ssenariylari |
| `10_Documentation` | Hujjatlar, yo'l xaritasi, demo ssenariysi, AI hisobotlari |
| `11_Presentation` | Taqdimot (PowerPoint) va uni yaratuvchi skript |
| `tests` | KPI hisob-kitoblari, hisoblar va sessiya, SQL himoyasi (unit testlar); agent vositalari (smoke test) |

`config.py` - ulanish, baholash shkalasi, xavf ta'rifi, alert chegaralari va salomatlik bali
vaznlari bitta joyda.

## Tekshirish

```bash
.venv\Scripts\python -m unittest discover tests     # 57 ta unit test, bir necha soniya
.venv\Scripts\python tests\smoke_agent.py           # AI agent vositalari, jonli ombor bilan
```

Unit testlar salomatlik bali, imtihon ko'rsatkichlari, xavf darajalari, hisoblar/rollar va sessiya
tokenini qo'lda tuzilgan ma'lumotda tekshiradi; beshtasi jonli omborda ishlaydi va SQL Server
bo'lmasa o'tkazib yuboriladi.

AI yordamchining erkin SQL vositasi ikki qavat himoyalangan: matn filtri (faqat bitta `SELECT`) va
ma'lumotlar bazasining o'zi - so'rov faqat o'qish huquqiga ega `uis_agent_reader` foydalanuvchisi
nomidan bajariladi (`03_SQL/03_agent_reader.sql`).

ETL har ishga tushganda o'z testlarini bajaradi (dublikat kalitlar, yetim yozuvlar, ball
oraliqlari, to'lov balansi) va natijani `etl.RunLog` jadvaliga yozadi.
