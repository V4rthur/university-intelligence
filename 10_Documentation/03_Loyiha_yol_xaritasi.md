# Loyiha yo'l xaritasi: 14 bosqich

Har bir bosqich oldingisining natijasiga tayanadi. «O'tish sharti» bajarilmaguncha keyingi bosqich boshlanmaydi.

| # | Bosqich | Maqsad | Texnologiya | Fayllar | Kutilgan natija | Test | O'tish sharti |
|---|---|---|---|---|---|---|---|
| 1 | Biznes muammosi va talablar | Muammo, foydalanuvchilar, mezonlarni aniqlash | - | `10_Documentation/01_Biznes_talablar.md` | Kelishilgan talablar | Har bir talabga tekshirish usuli bor | Muvaffaqiyat mezonlari yozilgan |
| 2 | Ma'lumot yaratish | Real qonuniyatli sintetik ma'lumot | Python, NumPy, Pandas | `01_Data/generate_data.py`, `reference_uz.py`, `profile_raw.py` | 10 000+ talaba, 160 fan, 132 o'qituvchi, 2,6 mln+ yozuv | `profile_raw.py`: GPA, davomat, yiqilish taqsimoti | Ko'rsatkichlar real oraliqda; fakultetlar va fanlar farqlanadi |
| 3 | SQL baza | Sxemalar, staging va nazorat jadvallari | SQL Server, T-SQL | `03_SQL/*.sql` | `stg`, `dw`, `etl`, `ml` sxemalari | Skriptlar qayta ishga tushganda xato bermaydi | Barcha obyektlar yaratilgan |
| 4 | ETL konveyeri | Tozalash, tekshirish, yuklash | Python, Pandas, SQLAlchemy | `02_ETL/etl_pipeline.py` | Toza staging, sifat jurnali, karantin | Konveyer ichidagi post-load testlar | Barcha testlar PASS |
| 5 | Ma'lumotlar ombori | Yulduz sxemasi va MERGE yuklash | T-SQL | `04_Data_Warehouse/*.sql` | 7 o'lchov, 6 fakt, snapshot | To'liq qayta yuklash: 0 qo'shish, 0 yangilash | Idempotentlik isbotlangan |
| 6 | Tahlil va dashboard | KPI va boshqaruv paneli | Pandas, Streamlit, Plotly | `05_Analytics/metrics.py`, `08_Dashboard/*` | 7 sahifa (jumladan imtihon natijalari), alertlar, anomaliyalar | Har bir sahifa xatosiz ochiladi | Raqamlar ombor so'rovlari bilan mos |
| 7 | ML xavf bashorati | Keyingi semestr xavfini bashorat qilish | Scikit-learn | `06_ML/train_model.py`, `risk_model.py` | 4 model taqqoslangan, eng yaxshisi tanlangan | Vaqt bo'yicha sinov semestri | Validatsiyada recall ≥ 80% (sinovda taxminan 80%), ROC-AUC hisobotda |
| 8 | Tushuntiriladigan AI | Har bir bashorat sababini ko'rsatish | Okklyuziya, permutatsion ahamiyat | `06_ML/risk_model.py` (`explain`) | Har bir talaba uchun omillar ulushi | Ulushlar yig'indisi 100% | Dashboardda tushuntirish ko'rinadi |
| 9 | Ssenariy simulyatsiyasi | Qaror ta'sirini oldindan baholash | Pandas, o'qitilgan modellar | `09_Simulation/scenarios.py` | 5 tayyor + maxsus ssenariy | `tests/smoke_agent.py` | Har bir ssenariy 6 natija qaytaradi |
| 10 | AI agent | Tabiiy tilda savol-javob | Claude API, tool calling | `07_AI_Agent/agent.py`, `agent_tools.py` | 9 vosita, rol cheklovlari, oflayn rejim | Vositalar, SQL himoyasi, rollar testi | Barcha tekshiruvlar PASS |
| 11 | Integratsiya | Bitta buyruq bilan yangilash | Python | `run_pipeline.py` | ETL → ML → dashboard zanjiri | `--new-semester`: yangi semestr dashboardda ko'rinadi | Yangilanish avtomatik |
| 12 | Testlash | Butun tizimni tekshirish | Python | `tests/smoke_agent.py`, ETL testlari | Test hisoboti | Noldan qayta qurish (`--rebuild`) | Hammasi PASS |
| 13 | Hujjatlashtirish | Texnik va boshqaruv hujjatlari | Markdown | `10_Documentation/*`, `README.md` | To'liq hujjatlar to'plami | Buyruqlar hujjatdagidek ishlaydi | Cheklovlar va maxfiylik yoritilgan |
| 14 | Taqdimot va demo | Himoyaga tayyorlik | python-pptx | `11_Presentation/*`, `05_Demo_ssenariy.md` | 16 slayd, 5-7 daqiqalik demo | Demo boshidan oxirigacha bir marta o'tkazilgan | Vaqt 10 daqiqadan oshmaydi |
