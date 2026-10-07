# Jonli demo ssenariysi (5-7 daqiqa)

## Tayyorgarlik (demodan oldin)

1. SQL Server ishlab turganini tekshiring.
2. `start_dashboard.bat` ni ishga tushiring; brauzerda http://localhost:8610 ochiladi.
3. AI yordamchi to'liq ishlashi uchun `ANTHROPIC_API_KEY` o'rnatilgan bo'lsin. Bo'lmasa - «tayyor savollar» ishlatiladi.
4. Chap paneldagi rol: **Universitet rahbariyati**.
5. Zaxira: internet uzilsa, 7-9 qadamlarda tayyor savol tugmalaridan foydalaning (ular internetsiz ishlaydi).

## Qadamlar

| # | Vaqt | Sahifa | Nima qilinadi | Nima deyiladi | Qaysi texnologiya ishlayapti |
|---|---|---|---|---|---|
| 1 | 0:00-0:40 | Umumiy ko'rinish | Oltita ko'rsatkich va salomatlik balini ko'rsating; «qanday hisoblangan» bo'limini oching | «Universitet holati bir qarashda. Salomatlik bali 7 komponentdan, ochiq formula bilan hisoblanadi.» | SQL Server ombori → tahlil qatlami (Pandas) |
| 2 | 0:40-1:10 | Umumiy ko'rinish | «Nimaga e'tibor berish kerak» xabarlarini o'qing | «Tizim muammolarni o'zi ajratib ko'rsatadi: chegaralar sozlanadi.» | Alertlar, anomaliyalarni aniqlash |
| 3 | 1:10-1:50 | Fakultetlar | Reyting jadvali, so'ng GPA chizig'i | «Fakultetlar bir xil emas. Bittasining chizig'i uch yildan beri pastga ketmoqda.» | Yulduz sxemasi, `FactStudentSemester` |
| 4 | 1:50-2:50 | Imtihon natijalari | To'rt ko'rsatkich, taqsimot grafigi, «oraliqdan yakuniygacha» jadvali | «Baholash haqiqiy tizimdagidek: 20 + 30 + 50 ball. Oraliq nazoratda past olganlarning ko'pchiligi yakuniydan ham o'tmaydi - demak, oraliq nazorat erta ogohlantirish.» | `FactGrades`, imtihon ko'rsatkichlari |
| 5 | 2:50-3:20 | Imtihon natijalari | «Yakuniy nazorat eng ko'p pasaygan fanlar» grafigi | «Bitta fanda yakuniy nazorat keskin tushgan, oraliq esa odatdagidek. Bu - imtihonni ko'rib chiqish uchun signal.» | Anomaliya, fan kesimi |
| 6 | 3:20-4:10 | Xavf ostidagi talabalar | Ro'yxat, bitta qatorni tanlang → omillar va baholar | «Bu o'tmish emas, keyingi semestr bashorati. Model nima uchunligini ham ko'rsatadi.» | ML modeli + Explainable AI |
| 7 | 4:10-5:00 | «Agar...» ssenariylari | Avval «Davomat 5 f.p. pasaysa», so'ng «Tyutorlik dasturi» | «Qaror qabul qilishdan oldin uning ta'sirini sinaymiz. Farazlar ekranda yozilgan.» | Simulyatsiya + 4 ta ML modeli |
| 8 | 5:00-5:50 | AI yordamchi | Savol: «Nega Iqtisodiyot fakulteti natijalari pasaymoqda?» | «Yordamchi javobni yoddan aytmaydi: u ombor va modelga murojaat qiladi. Mana foydalanilgan vositalar.» | LLM + tool calling |
| 9 | 5:50-6:30 | AI yordamchi | Savol: «Dekan uchun qisqa hisobot tayyorla» | «Hisobot fayl sifatida saqlandi: `10_Documentation/reports`.» | Agent → `generate_report` |
| 10 | 6:30-7:00 | Boshqa → Ma'lumotlar sifati | Sifat balini ko'rsating; (ixtiyoriy) yangi semestrni simulyatsiya qiling | «Yangi ma'lumot kelganda konveyer uni tozalaydi, yuklaydi, xavfni qayta hisoblaydi - dashboard o'zi yangilanadi.» | Python ETL, MERGE, idempotent yuklash |

## Rol almashtirish (30 soniya, vaqt qolsa)

Chap panelda rolni **Professor-o'qituvchi** ga o'zgartiring va «Xavf ostidagi talabalar» sahifasini oching:
talabalar ro'yxati yopiladi. AI yordamchidan talabalar ro'yxatini so'rang - u ruxsat yo'qligini aytadi.
«Maxfiylik kodga qurilgan: cheklov vosita ichida, shuning uchun uni savol bilan chetlab o'tib bo'lmaydi.»

## Ehtimoliy savollarga javoblar

- **«Bu haqiqiy ma'lumotmi?»** - Yo'q, talabalar sintetik va bu ochiq yozilgan. Lekin tuzilma va qoidalar haqiqiy tizimdagidek: 100 ballik baholash, 5/4/3/2 baholar, o'tish bali 60, davomat qoidasi. Haqiqiy ma'lumotga o'tishda faqat manba fayllar almashadi.
- **«Bizda ball taqsimoti boshqacha»** - `config.py` dagi `SCORE_MAX` bitta qatorda o'zgartiriladi, qolgani o'zi moslashadi.
- **«Model qanchalik ishonchli?»** - Keyingi semestrda sinalgan; ko'rsatkichlar «Xavf ostidagi talabalar» sahifasida «Model qanchalik ishonchli» bo'limida. Xavf ostidagilarning taxminan beshdan to'rt qismini topadi.
- **«Davomat xavfda nega kichik ulushga ega?»** - Davomat ta'siri GPA va yakuniyga qo'yilmaslik orqali allaqachon aks etgan; model GPA tarixiga tayanadi.
- **«Simulyatsiya natijasi kafolatmi?»** - Yo'q. U kuzatilgan bog'liqlikka asoslangan baho. Haqiqiy samarani pilot tajriba ko'rsatadi.
- **«Nega Power BI emas?»** - Yechim to'liq Pythonda: bir xil kod dashboard, model va agentga xizmat qiladi, litsenziya talab qilmaydi va brauzerda sayt sifatida ochiladi.
