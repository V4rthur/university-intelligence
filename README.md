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
| Xavf ostidagi talabalar | Kimga yordam kerak va nima uchun? |
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

Dashboard qulflangan ekran bilan ochiladi: login va parol so'raladi. Hisob
`.streamlit/secrets.toml` faylida saqlanadi (parolning o'zi emas, faqat tuzlangan xeshi).
Login yoki parolni o'zgartirish:

```bash
.venv\Scripts\python 08_Dashboard\set_password.py
```

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
| `03_SQL` | Sxemalar, ETL nazorat jadvallari, staging jadvallari |
| `04_Data_Warehouse` | Yulduz sxemasi: o'lchovlar, faktlar, yuklash protseduralari |
| `05_Analytics` | Barcha KPI, salomatlik bali, alert va anomaliyalarning yagona ta'rifi |
| `06_ML` | Xavf modeli: o'qitish, baholash, tushuntirish, talabalarni baholash |
| `07_AI_Agent` | AI agent va uning 9 ta vositasi, rolga asoslangan cheklovlar |
| `08_Dashboard` | Streamlit dashboard (7 sahifa) |
| `09_Simulation` | «Agar...» ssenariylari |
| `10_Documentation` | Hujjatlar, yo'l xaritasi, demo ssenariysi, AI hisobotlari |
| `11_Presentation` | Taqdimot (PowerPoint) va uni yaratuvchi skript |
| `tests` | Vositalar, rol cheklovlari, SQL himoyasi va ssenariylar testi |

`config.py` - ulanish, baholash shkalasi, xavf ta'rifi, alert chegaralari va salomatlik bali
vaznlari bitta joyda.

## Tekshirish

```bash
.venv\Scripts\python tests\smoke_agent.py
```

ETL har ishga tushganda o'z testlarini bajaradi (dublikat kalitlar, yetim yozuvlar, ball
oraliqlari, to'lov balansi) va natijani `etl.RunLog` jadvaliga yozadi.
