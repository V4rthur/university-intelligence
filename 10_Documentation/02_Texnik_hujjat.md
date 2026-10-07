# Texnik hujjat

Aniq raqamlar (model ko'rsatkichlari, topilmalar) `04_Natijalar_va_topilmalar.md` faylida:
u ombordan avtomatik yaratiladi (`python 05_Analytics/facts.py`), shuning uchun har doim joriy ma'lumotga mos.

## 1. Qisqacha mazmun (Executive Summary)

Tizim universitetning tarqoq ma'lumotlarini yagona omborga yig'adi va rahbariyatga to'rt savolga
javob beradi: nima bo'ldi, nega bo'ldi, nima bo'ladi va nima qilish kerak. U Power BI dashboardi,
alohida Python skripti, alohida ML modeli yoki chatbot emas - bularning barchasi bitta ma'lumot
oqimiga ulangan: ETL omborni to'ldiradi, tahlil qatlami va model ombordan o'qiydi, dashboard va
AI agent esa aynan shu tahlil qatlamidan foydalanadi.

## 2. Ma'lumotlar arxitekturasi

| Qatlam | Joylashuvi | Mazmuni |
|---|---|---|
| Manba | `01_Data/raw` | 11 turdagi fayl: talabalar, fakultetlar (JSON), kafedralar (JSON), o'qituvchilar (Excel), fanlar, yozilishlar, baholar, davomat, to'lovlar, topshiriqlar, ogohlantirishlar |
| Staging | `stg.*` | Joriy ishga tushirishda tozalangan va turi to'g'rilangan yozuvlar |
| Ombor | `dw.*` | Yulduz sxemasi: 7 o'lchov, 6 fakt, 1 tahliliy snapshot |
| Nazorat | `etl.*` | Ishga tushirishlar, fayllar, sifat tekshiruvlari, rad etilgan yozuvlar, yuklash auditi |
| Model natijalari | `ml.*` | Talabalar xavfi, model ko'rsatkichlari, belgilar ahamiyati |

### Baholash tizimi (haqiqiy kredit-modul tizimiga mos)

Har bir fan 100 ballik tizimda baholanadi: joriy nazorat (20) + oraliq nazorat (30) + yakuniy
nazorat (50). Jami ball bahoga o'tkaziladi: 90-100 = 5, 70-89 = 4, 60-69 = 3, 60 dan past = 2
(akademik qarzdorlik). Sababsiz qoldirilgan darslar 25% dan oshsa, talaba yakuniy nazoratga
qo'yilmaydi. GPA - kreditlar bo'yicha vaznlangan o'rtacha baho (5 ballik shkala). Barcha
qiymatlar `config.py` da (`SCORE_MAX`, `PASS_MARK`, `GRADE_SCALE`, `MAX_UNEXCUSED_ABSENCE`).
Omborda jami ball va baho manbadan ko'chirilmaydi, balki nazorat ballaridan qayta hisoblanadi,
shuning uchun ular har doim bir-biriga mos.

### Sintetik ma'lumot

Ma'lumot tasodifiy sonlar emas, **xulq-atvor simulyatsiyasi** orqali yaratiladi. Har bir talabaning
yashirin xususiyatlari bor (qobiliyat, faollik, moliyaviy bosim). Davomat, topshiriq va imtihon
ballari shu xususiyatlar, fakultet, fan qiyinligi va o'qituvchi yuklamasidan kelib chiqadi; o'qishni
tark etish GPA, yiqilgan fanlar, davomat va qarzga bog'liq. Shu sababli ma'lumotda haqiqiy hayotga
o'xshash qonuniyatlar mavjud. Tekshirish uchun ataylab kiritilgan anomaliyalar `generate_data.py`
faylidagi `ANOMALIES` lug'atida hujjatlashtirilgan. Xom fayllar ataylab «iflos»: dublikatlar, bo'sh
qiymatlar, noto'g'ri formatlar, oraliqdan tashqari ballar va yetim kalitlar.

## 3. ETL arxitekturasi

`02_ETL/etl_pipeline.py`:

1. **Extract.** Fayl MD5 xeshi `etl.FileLog` bilan solishtiriladi; faqat yangi yoki o'zgargan fayllar o'qiladi.
2. **Clean.** Bo'shliqlarni kesish; toifalarni standart yozuvga keltirish (`KELDI`, ` keldi ` → `Keldi`);
   son va sana turlarini tuzatish (`8 000 000` → 8000000, `31.12.2005` → 2005-12-31);
   bo'sh qiymatlarni to'ldirish (jins → «Ko'rsatilmagan», oraliq nazorat bali → fan medianasi);
   birlamchi kalit bo'yicha dublikatlarni olib tashlash.
3. **Validate.** Oraliq qoidalari (ball 0-100, sana 2022-2033), chetlanishlarni belgilash (mediana ± 6 MAD),
   bog'lanish yaxlitligi (talaba, fan, o'qituvchi mavjudligi). Yaroqsiz yozuvlar `etl.RejectedRecords` ga
   sababi bilan karantinga olinadi.
4. **Stage.** Toza yozuvlar `stg.*` jadvallariga yuklanadi.
5. **Transform + Load.** `dw.usp_LoadDimensions` va `dw.usp_LoadFacts` staging'ni omborga `MERGE` qiladi.
   Hosila ustunlar shu yerda yaratiladi: semestr kaliti (yozilishdan yoki sanadan), jami ball, `IsFailed`,
   `IsPresent`, `IsLate`. So'ng `dw.usp_BuildStudentSemester` tahliliy snapshotni qayta quradi.
6. **Test.** Har ishga tushirishdan keyin: dublikat kalit yo'qligi, har bir bahoning yozilishi borligi,
   ballar oralig'i, `to'langan + qarz = kontrakt`, snapshot to'liqligi.

**Idempotentlik.** Har bir yuklash birlamchi kalit bo'yicha `MERGE`: yangi yozuv qo'shiladi, o'zgargani
yangilanadi, o'zgarmagani tegilmaydi. To'liq qayta yuklash 0 ta qo'shish va 0 ta yangilash beradi.

**Ma'lumotlar sifati bali** = 1 − (tuzatilgan va rad etilgan yozuvlar / o'qilgan yozuvlar).

## 4. Ma'lumotlar ombori dizayni

**Nega ombor kerak:** manba fayllar operatsion ish uchun tuzilgan, tahlil uchun emas. Ombor
tozalangan, bir xil ta'riflangan va tarixiy ma'lumotni saqlaydi; har bir KPI bir marta, bir joyda hisoblanadi.

| O'lchovlar | Kalit | | Faktlar | Donadorlik |
|---|---|---|---|---|
| `DimStudent` | StudentKey | | `FactEnrollments` | talaba × fan |
| `DimFaculty` | FacultyKey | | `FactGrades` | talaba × fan bahosi |
| `DimDepartment` | DepartmentKey | | `FactAttendance` | talaba × fan × sana |
| `DimTeacher` | TeacherKey | | `FactPayments` | talaba × semestr hisob-fakturasi |
| `DimCourse` | CourseKey | | `FactAssignments` | talaba × fan × topshiriq |
| `DimSemester` | SemesterKey | | `FactWarnings` | ogohlantirish |
| `DimDate` | DateKey (yyyymmdd) | | `FactStudentSemester` | talaba × semestr (snapshot) |

Bog'lanishlar: `DimDepartment → DimFaculty`; `DimTeacher, DimCourse → DimDepartment`;
`DimStudent → DimFaculty, DimDepartment`; `DimDate → DimSemester`; har bir fakt o'z o'lchovlariga
`FOREIGN KEY` bilan bog'langan (`04_Data_Warehouse/01_dimensions.sql`, `02_facts.sql`).

`FactStudentSemester` - dashboard, ML va agent uchun yagona manba: semestr va umumiy GPA, oldingi GPA,
davomat, yiqilgan fanlar, topshiriq ko'rsatkichlari, ogohlantirishlar, qarz ulushi, o'qituvchi yuklamasi.

## 5. Tahlil qatlami

`05_Analytics/metrics.py` barcha ko'rsatkichlarni ta'riflaydi. Dashboard va AI agent aynan shu
funksiyalarni chaqiradi, shuning uchun grafikdagi va agent javobidagi raqam hech qachon farq qilmaydi.

- **Imtihon tahlili:** oraliq va yakuniy nazorat natijalari har birining o'z maksimumiga nisbatan foizda
  solishtiriladi (30 va 50 ballni to'g'ridan-to'g'ri solishtirib bo'lmaydi). Ko'rsatkichlar: o'rtacha natija,
  o'tganlar ulushi (maksimumning 60% i), yakuniy va oraliq o'rtasidagi farq, yakuniyga qo'yilmaganlar,
  oraliqdan o'tib fandan yiqilganlar, baholar taqsimoti. Kesimlar: fakultet, guruh, fan, o'qituvchi, semestr.
  Yakuniy nazorat ko'rsatkichlari faqat qo'yilgan talabalar bo'yicha hisoblanadi.
- **Solishtirish:** joriy semestr o'tgan yilning shu semestri bilan solishtiriladi (Kuz va Bahorda fanlar turlicha).
- **Universitet salomatlik bali (0-100):** 7 komponent, har biri «eng yomon → eng yaxshi» mezon oralig'ida
  0-100 ga o'tkaziladi va vaznga ko'paytiriladi (`config.HEALTH_SCALES`, `HEALTH_WEIGHTS`).
  Fakultet balida o'qituvchi yuklamasi hisobga olinmaydi (umumta'lim o'qituvchilari barcha fakultetga xizmat qiladi).
- **Alertlar:** chegaralar `config.ALERTS` da sozlanadi (xavf ulushi, davomat pasayishi, fan yiqilishi, GPA trendi, to'lov).
- **Anomaliyalar:** semestrlararo o'zgarishning robast z-bali (mediana va MAD) ≥ 3; fan uchun - o'z tarixiga
  nisbatan binomial z-ball. Har biri uchun: nima, qayerda, qachon, qancha va tekshirish uchun ehtimoliy sabab.

## 6. Mashinali o'qitish metodologiyasi

**Vazifa:** talabaning *t* semestr oxiridagi ko'rsatkichlari asosida *t+1* semestrda xavf ostida bo'lishini
bashorat qilish: GPA < 3.0 (5 ballik shkala) **yoki** 2+ fandan yiqilish **yoki** o'qishni tark etish.

**Belgilar (14 ta):** joriy, oldingi va umumiy GPA, GPA o'zgarishi, davomat, yiqilgan fanlar (semestr va jami),
topshiriq bali, topshirish ulushi, ogohlantirishlar soni, qarz ulushi, o'qish semestri, kredit yuklamasi,
o'qituvchi yuklamasi.

**Kelajakdan «sizib chiqish» yo'q:** belgilar faqat *t* va undan oldingi, nishon faqat *t+1* dan olinadi.
Oxirgi semestr o'qitishdan chiqarilgan (uning natijasi hali noma'lum).

**Vaqt bo'yicha ajratish:** o'qitish - eski semestrlar, validatsiya - oxiridan ikkinchi, sinov - oxirgi
to'liq semestr. Model amalda qanday ishlatilsa, shunday sinaladi.

**Taqqoslangan modellar:** Logistic Regression, Decision Tree, Random Forest, Gradient Boosting.
G'olib validatsiyadagi ROC-AUC bo'yicha tanlanadi; sinov semestriga faqat bir marta, yakuniy baholash uchun murojaat qilinadi.

## 7. Modelni baholash

Accuracy, Precision, Recall, F1, ROC-AUC va xatolar matritsasi (`ml.ModelMetrics`).

**Nega faqat accuracy yetarli emas.** Talabalarning ko'pchiligi xavf ostida emas; hech kimni
belgilamaydigan model ham yuqori accuracy ko'rsatadi, lekin foydasiz.

**False Negative nega xavfli.** Bu - model «xavfsiz» degan, aslida qiynalayotgan talaba. Unga hech kim
murojaat qilmaydi va u o'qishni tashlashi mumkin. False Positive esa - ortiqcha bir suhbat. Shuning uchun
qaror chegarasi validatsiyada recall ≥ 80% bo'ladigan qilib tanlanadi (`config.TARGET_RECALL`).

Xavf darajalari ehtimollik bo'yicha: Past < 25%, O'rta < 50%, Yuqori < 75%, Kritik ≥ 75%.

## 8. Tushuntiriladigan AI (Explainable AI)

Har bir talaba va har bir omil guruhi uchun (GPA, davomat, yiqilgan fanlar, topshiriqlar, moliyaviy qarz,
akademik tarix, o'qituvchi yuklamasi): guruh qiymatlari xavf ostida bo'lmagan tipik talaba qiymatlari bilan
almashtiriladi va model qayta so'raladi. Bashorat qanchaga kamaysa, shu - guruhning hissasi (okklyuziya usuli).
Musbat hissalar 100% ga normallashtiriladi. Global daraja uchun sinov semestrida permutatsion ahamiyat hisoblanadi.

Bu tushuntirish *model nimaga tayanganini* ko'rsatadi; u *haqiqiy sababni* isbotlamaydi.

## 9. AI agent arxitekturasi

`07_AI_Agent/agent.py` - LLM (Claude) + tool calling. Model qaysi vositani chaqirishni o'zi tanlaydi,
JSON natijani o'qiydi va tuzilgan javob yozadi.

| Vosita | Vazifasi |
|---|---|
| `university_overview` | KPI, salomatlik bali, alertlar, anomaliyalar |
| `faculty_analytics` | Fakultetlar taqqoslamasi, trend, qiyin fanlar |
| `exam_analytics` | Oraliq va yakuniy nazorat natijalari, qo'yilmaganlar, baholar taqsimoti |
| `student_analytics` | Xavfi yuqori talabalar, profil, qidiruv |
| `course_analytics` | Fan ko'rsatkichlari va tarixi |
| `ml_prediction` | Xavf taqsimoti, talaba bashorati, model ko'rsatkichlari |
| `scenario_simulation` | «Agar...» ssenariylari |
| `sql_query` | Faqat o'qish uchun bitta SELECT |
| `generate_report` | Rahbariyat hisobotini Markdown faylga saqlash |

**Gallyutsinatsiyadan himoya:**
- tizim ko'rsatmasi: har bir raqam shu suhbatdagi vosita natijasidan olinishi shart; ma'lumot bo'lmasa - ochiq aytish;
- javob bilan birga foydalanilgan vositalar ro'yxati ko'rsatiladi (audit izi);
- ishonchlilik foiz bilan to'qib chiqarilmaydi - dalilga asoslangan sifat bahosi beriladi;
- `sql_query` faqat bitta `SELECT`/`WITH` ni qabul qiladi; yozuvchi buyruqlar, izohlar va `;` rad etiladi, 200 qator cheklovi.

**Rolga asoslangan kirish:** `rahbariyat` - to'liq; `dekan` - faqat o'z fakulteti; `oqituvchi` - faqat
umumlashtirilgan ko'rsatkichlar, talaba ismlari va erkin SQL yopiq. Cheklov vosita ichida qo'llanadi,
ya'ni modelni «ko'ndirish» orqali chetlab o'tib bo'lmaydi.

Kalit bo'lmaganda oflayn rejim: tayyor savollar bevosita vositalardan javob beradi.

## 10. Ssenariy simulyatsiyasi

`09_Simulation/scenarios.py`:

1. Har bir faol talabaning oxirgi semestr belgilari olinadi.
2. Ssenariy tutqichlari (davomat, topshirish ulushi, topshiriq bali, o'qituvchi yuklamasi) tanlangan talabalar uchun o'zgartiriladi.
3. O'zgarish shu semestr GPA va yiqilgan fanlarga talabaning o'z tarixidan baholangan bog'liqlik orqali o'tkaziladi
   (har bir talaba o'z o'rtachasi bilan solishtiriladi - bu talabalar orasidagi doimiy farqlarni chiqarib tashlaydi).
4. To'rtta model keyingi semestrni qayta bashorat qiladi: xavf, GPA, yiqilish ulushi, o'qishni tark etish.

Natijalar: bashorat qilingan GPA, xavf ostidagi talabalar, yiqilish darajasi, saqlanish, bitirish ehtimoli.

## 11. Cheklovlar

- **Sintetik ma'lumot.** Natijalar usulning ishlashini ko'rsatadi; haqiqiy universitetda raqamlar boshqacha bo'ladi.
- **Bog'liqlik ≠ sabab.** Model va simulyatsiya kuzatilgan bog'liqliklarga tayanadi. Dastur samarasini faqat tajriba (pilot) isbotlaydi.
- **Dasturlar ta'siri - faraz.** «Tyutorlik topshiriq balini 8 ballga oshiradi» kabi qiymatlar sozlanadigan taxmin.
- **Bitirish ehtimoli** har semestrdagi tark etish ehtimoli o'zgarmaydi degan soddalashtirishga tayanadi.
- **GPA ustunligi.** Model asosan GPA tarixiga tayanadi; davomat va qarzning mustaqil hissasi kichik, chunki ular GPA orqali allaqachon aks etgan.
- **Semestr boshida bashorat yo'q.** Model semestr yakunidagi ma'lumotga tayanadi; semestr ichidagi erta ogohlantirish alohida model talab qiladi.

## 12. Talaba maxfiyligi va ma'lumot xavfsizligi

- Talaba darajasidagi ma'lumot rolga qarab yopiladi (dashboard va agentda).
- Haqiqiy joriy etishda: SQL Server rollari va qator darajasidagi xavfsizlik (RLS), shifrlangan ulanish,
  kirish jurnali, shaxsiy ma'lumotlarni tashqi LLM xizmatiga yubormaslik yoki anonimlashtirish
  (agentga ism o'rniga identifikator berish), ma'lumot saqlash muddatlari.
- Xavf bahosi **jazolash vositasi emas** - u talabaga yordam ko'rsatish uchun; qarorni odam qabul qiladi.
- Modelni guruhlar bo'yicha adolatlilikka tekshirish (jins, to'lov shakli) haqiqiy ma'lumotda majburiy.

## 13. Kelajakdagi rivojlanish

- Haqiqiy universitet tizimlariga (LMS, kontingent, buxgalteriya) ulanish.
- Semestr ichidagi erta ogohlantirish (haftalik davomat va topshiriqlar asosida).
- Aralashuvlar samarasini o'lchash uchun pilot tajribalar va natijalarni simulyatsiyaga qaytarish.
- Konveyerni jadval bo'yicha avtomatik ishga tushirish (Windows Task Scheduler / SQL Agent).
- Dashboardni universitet ichki tarmog'ida joylashtirish va yagona kirish (SSO).
